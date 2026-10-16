"""/ws：把 Redis 上的即時行情轉送給瀏覽器。

客戶端送 {"op": "subscribe", "codes": ["2330", "IX0001", "SCANNER"]}／{"op": "unsubscribe", ...}；
伺服器先回每檔最新一筆，之後即時轉送。關注的代號寫進 quote:interest，讓行情服務訂閱。
"""

from __future__ import annotations

import asyncio
import json
import re
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
CODE_RE = re.compile(r"^[A-Z0-9]{2,10}$")
MAX_CODES = 60
INTEREST_REFRESH_SEC = 60


async def _touch_interest(rds, codes: set[str]) -> None:
    real = [c for c in codes if c != "SCANNER"]
    if real:
        now = time.time()
        await rds.zadd("quote:interest", {c: now for c in real})


async def _send_last(ws: WebSocket, rds, codes: list[str]) -> None:
    keys = ["q:scanner" if c == "SCANNER" else f"q:last:{c}" for c in codes]
    for data in await rds.mget(keys):
        if data:
            await ws.send_text(data)


@router.websocket("/ws")
async def quotes_ws(ws: WebSocket):
    rds = ws.app.state.redis
    await ws.accept()
    pubsub = rds.pubsub()
    codes: set[str] = set()

    async def forward():
        last_touch = 0.0
        while True:
            if codes:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    await ws.send_text(msg["data"])
                if time.time() - last_touch > INTEREST_REFRESH_SEC:
                    await _touch_interest(rds, codes)
                    last_touch = time.time()
            else:
                await asyncio.sleep(0.2)

    task = asyncio.create_task(forward())
    try:
        while True:
            try:
                req = json.loads(await ws.receive_text())
            except (ValueError, TypeError):
                continue
            op = req.get("op")
            wanted = [c for c in (req.get("codes") or []) if isinstance(c, str) and CODE_RE.match(c)]
            if op == "subscribe":
                new = [c for c in wanted if c not in codes][: max(MAX_CODES - len(codes), 0)]
                if new:
                    await pubsub.subscribe(*[f"q:{c}" for c in new])
                    codes.update(new)
                    await _touch_interest(rds, set(new))
                    await _send_last(ws, rds, new)
            elif op == "unsubscribe":
                gone = [c for c in wanted if c in codes]
                if gone:
                    await pubsub.unsubscribe(*[f"q:{c}" for c in gone])
                    codes.difference_update(gone)
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        try:
            await pubsub.aclose()
        except Exception:
            pass
