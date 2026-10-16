"""全球市場 API：/api/global（預先計算）、/api/global/kbar（港美股等個股日 K，Yahoo）。"""

from __future__ import annotations

import asyncio
import json
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.sources import yahoo

router = APIRouter()
SYMBOL_RE = re.compile(r"^[A-Za-z0-9.^=\-]{1,15}$")
RANGES = {"6mo", "1y", "2y", "5y", "max"}


@router.get("/api/global")
async def global_overview(request: Request):
    raw = await request.app.state.redis.get("global:latest")
    if not raw:
        return JSONResponse({"status": "preparing"}, status_code=503)
    return JSONResponse(json.loads(raw), headers={"Cache-Control": "no-cache"})


@router.get("/api/global/kbar")
async def global_kbar(symbol: str, request: Request, range: str = "1y"):  # noqa: A002
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol) or range not in RANGES:
        raise HTTPException(400, "代號或期間格式不正確")
    s = request.app.state
    key = f"yahoo:kbar:{symbol}:{range}"
    cached = await asyncio.to_thread(s.store.kv_get, key, 30 * 60)
    if cached is not None:
        return cached
    try:
        async with yahoo.make_client() as client:
            data = yahoo.parse_ohlc(await yahoo.daily_bars(client, symbol, range))
    except httpx.HTTPStatusError as e:
        raise HTTPException(404 if e.response.status_code == 404 else 502, f"找不到 {symbol}" if e.response.status_code == 404 else "Yahoo 暫時無法使用")
    except (KeyError, IndexError, TypeError):
        raise HTTPException(404, f"找不到 {symbol}")
    if not data["bars"]:
        raise HTTPException(404, f"{symbol} 沒有資料")
    await asyncio.to_thread(s.store.kv_put, key, data)
    return data
