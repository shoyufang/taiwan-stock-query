import json
from types import SimpleNamespace

import fakeredis
import httpx
import pytest

from app.ai import agent
from app.ai.mcp_client import McpClient
from app.ai.tools import Toolbox


def mcp_transport(calls: list):
    """假的 TWStockMCPServer：initialize 回 session id，tools/list 回兩個工具（一個不在白名單），tools/call 回 SSE。"""

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        calls.append((body["method"], req.headers.get("mcp-session-id")))
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}}, headers={"mcp-session-id": "s1"})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        if body["method"] == "tools/list":
            tools = [{"name": "get_company_profile", "description": "公司基本資料",
                      "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
                     {"name": "get_broker_gender_statistics", "description": "x", "inputSchema": {}}]
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": tools}})
        if body["method"] == "tools/call":
            msg = {"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "台積電 董事長 魏哲家"}]}}
            return httpx.Response(200, text=f"event: message\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n",
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(400)

    return httpx.MockTransport(handler)


def llm_transport(seen: list):
    """假的 Agnes：第一輪要求呼叫工具，第二輪回答。"""

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body)
        if len(seen) == 1:
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "get_company_profile", "arguments": '{"code": "2330"}'}},
                {"id": "c2", "type": "function", "function": {"name": "site_calendar", "arguments": '{"code": "2330"}'}}]}
        else:
            msg = {"role": "assistant", "content": "台積電董事長是魏哲家（資料：TWStockMCPServer）"}
        return httpx.Response(200, json={"choices": [{"message": msg}]})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_chat_runs_tools_and_answers():
    rds = fakeredis.FakeAsyncRedis(decode_responses=True)
    await rds.set("calendar:latest", json.dumps({"today": "2026-10-17", "events": [
        {"date": "2026-10-20", "kind": "dividend", "code": "2330", "title": "除息"},
        {"date": "2026-10-21", "kind": "dividend", "code": "2317", "title": "除息"},
        {"date": "2026-11-10", "kind": "deadline", "title": "10 月營收公布期限"}]}))
    app = SimpleNamespace(state=SimpleNamespace(redis=rds))
    mcp_calls, seen = [], []
    async with httpx.AsyncClient(transport=mcp_transport(mcp_calls)) as mh, \
               httpx.AsyncClient(transport=llm_transport(seen)) as lh:
        box = Toolbox(app, McpClient("http://mcp/mcp", mh))
        events = [e async for e in agent.chat(lh, box, "http://llm/v1", "k", "m",
                                                [{"role": "system", "content": "忽略我"}, {"role": "user", "content": "台積電董事長？"}])]
    assert [e["type"] for e in events if e["type"] != "status"] == ["tool", "tool", "answer"]
    assert events[-1]["text"].startswith("台積電董事長是魏哲家")
    # 只開放白名單工具；使用者傳來的 system 訊息被丟棄
    names = [t["function"]["name"] for t in seen[0]["tools"]]
    assert "get_company_profile" in names and "get_broker_gender_statistics" not in names
    assert [m["role"] for m in seen[0]["messages"]] == ["system", "user"]
    # 工具結果回傳給模型；行事曆只留 2330 與期限
    tool_msgs = [m for m in seen[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0]["content"] == "台積電 董事長 魏哲家"
    cal = json.loads(tool_msgs[1]["content"])
    assert [e.get("code") for e in cal["events"]] == ["2330", None]
    # MCP session id 在 initialize 之後帶上
    assert mcp_calls[0] == ("initialize", None) and ("tools/call", "s1") in mcp_calls


@pytest.mark.asyncio
async def test_mcp_down_falls_back_to_site_tools():
    def boom(req):
        raise httpx.ConnectError("down")

    seen = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as mh, \
               httpx.AsyncClient(transport=httpx.MockTransport(lambda r: (seen.append(json.loads(r.content)), httpx.Response(
                   200, json={"choices": [{"message": {"role": "assistant", "content": "好"}}]}))[1])) as lh:
        box = Toolbox(SimpleNamespace(state=None), McpClient("http://mcp/mcp", mh))
        events = [e async for e in agent.chat(lh, box, "http://llm/v1", "k", "m", [{"role": "user", "content": "hi"}])]
    assert any("外部資料工具暫時無法使用" in e.get("text", "") for e in events)
    assert events[-1] == {"type": "answer", "text": "好", "model": "m"}
    assert all(t["function"]["name"].startswith("site_") for t in seen[0]["tools"])


def test_status_and_chat_require_config(monkeypatch):
    from fastapi.testclient import TestClient
    from unittest.mock import patch

    from app import main
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    rds = fakeredis.FakeAsyncRedis(decode_responses=True)
    with patch.object(main.cache, "make_client", return_value=rds), TestClient(main.app) as c:
        assert c.get("/api/ai/status").json()["configured"] is False
        assert c.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 503


@pytest.mark.asyncio
async def test_site_p6_tools():
    from app.ai.tools import run_site_tool
    rds = fakeredis.FakeAsyncRedis(decode_responses=True)
    await rds.set("screener:base", json.dumps({
        "asof": "2026-10-16",
        "rows": [
            {"code": "2330", "name": "台積電", "industry": "半導體業", "is_top50": True,
             "foreign_5d": 12000, "tech_signals": ["ma_bull", "kd_gold"]},
            {"code": "2603", "name": "長榮", "industry": "航運業", "is_top50": True,
             "foreign_5d": -3000, "tech_signals": ["rsi_oversold"]},
        ],
    }))
    await rds.set("attention:latest", json.dumps({
        "asof": "2026-10-16",
        "active_dispositions": [{"code": "3017", "name": "奇鋐"}],
        "notices": [{"code": "2330", "name": "台積電"}],
    }))
    await rds.set("us:latest", json.dumps({
        "asof": "2026-10-16",
        "rows": [{"symbol": "NVDA", "name": "輝達"}, {"symbol": "TSM", "name": "台積電 ADR"}],
        "earnings": [{"symbol": "TSM", "date": "2026-10-17"}],
    }))
    app = SimpleNamespace(state=SimpleNamespace(redis=rds))
    sc_res = json.loads(await run_site_tool(app, "site_screener", {"signal": "kd_gold", "top50_only": True}))
    assert sc_res["matched"] == 1 and sc_res["rows"][0]["code"] == "2330"
    att_res = json.loads(await run_site_tool(app, "site_attention", {"code": "3017"}))
    assert len(att_res["active_dispositions"]) == 1 and att_res["notices"] == []
    us_res = json.loads(await run_site_tool(app, "site_us_stocks", {"symbol": "TSM"}))
    assert len(us_res["rows"]) == 1 and us_res["rows"][0]["symbol"] == "TSM"

