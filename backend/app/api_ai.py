"""AI 助理 API：/api/ai/status、/api/ai/chat（SSE 串流事件）。

金鑰只在伺服器端（deploy/.env 的 AGNES_API_KEY，由 deploy/set-agnes.sh 讓使用者自行輸入），不會送到瀏覽器。
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai import agent
from app.ai.mcp_client import McpClient
from app.ai.tools import Toolbox

router = APIRouter()
log = logging.getLogger("ai")
DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"


def ai_config() -> dict:
    return {"api_key": os.getenv("AGNES_API_KEY", "").strip(),
            "model": os.getenv("AGNES_MODEL", "").strip(),
            "base_url": os.getenv("AGNES_BASE_URL", "").strip() or DEFAULT_BASE_URL,
            "mcp_url": os.getenv("MCP_URL", "").strip()}


class ChatIn(BaseModel):
    messages: list[dict]


@router.get("/api/ai/status")
async def status():
    c = ai_config()
    return {"configured": bool(c["api_key"] and c["model"]), "model": c["model"] or None, "tools": bool(c["mcp_url"])}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/api/ai/chat")
async def chat(body: ChatIn, request: Request):
    c = ai_config()
    if not (c["api_key"] and c["model"]):
        raise HTTPException(503, "AI 助理尚未設定金鑰與模型")

    async def events():
        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as http, httpx.AsyncClient(timeout=timeout) as mcp_http:
            mcp = McpClient(c["mcp_url"], mcp_http) if c["mcp_url"] else None
            try:
                async for ev in agent.chat(http, Toolbox(request.app, mcp), c["base_url"], c["api_key"], c["model"],
                                           body.messages):
                    yield _sse(ev)
            except Exception as e:  # noqa: BLE001
                log.exception("AI 對話失敗")
                yield _sse({"type": "error", "text": str(e)[:300]})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
