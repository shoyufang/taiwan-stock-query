"""AI 助理對話迴圈（OpenAI 相容 Chat Completions＋工具呼叫），供應商為 Agnes。

產生一連串事件給前端（SSE）：status、tool、answer、error。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.ai.tools import Toolbox

log = logging.getLogger("ai")
TZ = ZoneInfo("Asia/Taipei")
MAX_ROUNDS = 6
MAX_HISTORY = 12
MAX_MESSAGE_CHARS = 4000

SYSTEM = """你是「台股看盤」網站的研究助理，使用者是在台灣投資的個人投資人，偏好白話、繁體中文。
今天是 {today}（台北時間 {now}）。

規則：
1. 數字一律來自工具結果，不可憑記憶或推測編造；查不到就直說查不到。
2. 回答時註明資料日期與來源（例如「證交所 10/16 收盤」）。盤中即時價與收盤價要分清楚。
3. 先用本站工具（site_ 開頭，較快且與網站畫面一致），不足再用其他工具。
4. 單位要寫清楚：張（1 張 = 1,000 股）、元、億元、%。台股紅漲綠跌。
5. 可以整理、比較、解釋指標意義，但不要給買賣指令；涉及投資決策時提醒「僅供參考，不構成投資建議」。
6. 回答用 Markdown，重點在前，必要時用小表格；不要冗長。"""


def _clean_history(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages[-MAX_HISTORY:]:
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip():
            out.append({"role": m["role"], "content": m["content"][:MAX_MESSAGE_CHARS]})
    return out


async def _complete(http: httpx.AsyncClient, base_url: str, api_key: str, model: str, messages: list[dict],
                    tools: list[dict]) -> dict:
    r = await http.post(f"{base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model, "messages": messages, "tools": tools, "temperature": 0.3})
    if r.status_code >= 400:
        detail = r.text[:200]
        raise RuntimeError(f"AI 服務回應 {r.status_code}：{detail}")
    return r.json()["choices"][0]["message"]


async def chat(http: httpx.AsyncClient, toolbox: Toolbox, base_url: str, api_key: str, model: str,
               history: list[dict]) -> AsyncIterator[dict]:
    now = datetime.now(TZ)
    convo = _clean_history(history)
    if not convo or convo[-1]["role"] != "user":
        yield {"type": "error", "text": "沒有收到問題"}
        return
    yield {"type": "status", "text": "準備資料工具…"}
    await toolbox.load()
    if toolbox.note:
        yield {"type": "status", "text": toolbox.note}
    messages = [{"role": "system", "content": SYSTEM.format(today=now.date().isoformat(), now=now.strftime("%H:%M"))},
                *convo]
    for _ in range(MAX_ROUNDS):
        yield {"type": "status", "text": "思考中…"}
        msg = await _complete(http, base_url, api_key, model, messages, toolbox.schemas)
        calls = msg.get("tool_calls") or []
        if not calls:
            yield {"type": "answer", "text": msg.get("content") or "（沒有回覆內容）", "model": model}
            return
        messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls", "reasoning_content")})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool", "name": name, "args": args}
            try:
                result = await toolbox.call(name, args)
            except Exception as e:  # noqa: BLE001
                log.warning("工具 %s 失敗：%s", name, e)
                result = f"工具執行失敗：{e}"
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    yield {"type": "error", "text": f"查詢步驟超過 {MAX_ROUNDS} 輪，請把問題拆小一點再問"}
