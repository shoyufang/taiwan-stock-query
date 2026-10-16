"""最小的 MCP（Streamable HTTP）客戶端：initialize、tools/list、tools/call。

只用到 JSON-RPC 的三個方法，不需要整套 SDK。伺服器可能回 application/json 或 text/event-stream，
兩種都處理。對象是同一個 compose 內自架的 TWStockMCPServer（http://twse-mcp:8000/mcp）。
"""

from __future__ import annotations

import itertools
import json

import httpx

PROTOCOL = "2025-06-18"


class McpError(RuntimeError):
    pass


def _parse(resp: httpx.Response, req_id: int) -> dict:
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                msg = json.loads(line[5:].strip())
                if msg.get("id") == req_id:
                    return msg
        raise McpError("MCP 回應中沒有對應的結果")
    return resp.json()


class McpClient:
    def __init__(self, url: str, client: httpx.AsyncClient):
        self.url, self.http, self.session, self._ids = url, client, None, itertools.count(1)

    async def _rpc(self, method: str, params: dict | None = None) -> dict:
        req_id = next(self._ids)
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        r = await self.http.post(self.url, headers=headers,
                                 json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        r.raise_for_status()
        self.session = r.headers.get("mcp-session-id", self.session)
        msg = _parse(r, req_id)
        if "error" in msg:
            raise McpError(msg["error"].get("message", "MCP 錯誤"))
        return msg["result"]

    async def initialize(self) -> None:
        await self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                       "clientInfo": {"name": "twstock", "version": "1"}})
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        await self.http.post(self.url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def list_tools(self) -> list[dict]:
        tools, cursor = [], None
        while True:
            res = await self._rpc("tools/list", {"cursor": cursor} if cursor else {})
            tools += res.get("tools", [])
            cursor = res.get("nextCursor")
            if not cursor:
                return tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        res = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if res.get("isError"):
            raise McpError(text or "工具執行失敗")
        return text
