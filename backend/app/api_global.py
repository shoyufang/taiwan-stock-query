"""全球市場 API：/api/global、/api/global/us（美股選股＋財報日曆）、/api/global/kbar（港美股等個股日 K，Yahoo）、
/api/global/fundamentals（港美股基本面，Yahoo quoteSummary）。"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services import global_fundamentals as gf
from app.services import us_stocks
from app.sources import yahoo

router = APIRouter()
TZ = ZoneInfo("Asia/Taipei")
SYMBOL_RE = re.compile(r"^[A-Za-z0-9.^=\-]{1,15}$")
RANGES = {"6mo", "1y", "2y", "5y", "max"}


@router.get("/api/global")
async def global_overview(request: Request):
    raw = await request.app.state.redis.get("global:latest")
    if not raw:
        return JSONResponse({"status": "preparing"}, status_code=503)
    return JSONResponse(json.loads(raw), headers={"Cache-Control": "no-cache"})


@router.get("/api/global/us")
async def global_us(request: Request):
    rds = request.app.state.redis
    raw = await rds.get("us:latest")
    if raw:
        return JSONResponse(json.loads(raw), headers={"Cache-Control": "no-cache"})
    now = datetime.now(TZ)
    try:
        data = await us_stocks.fetch_and_build(now.date(), now.isoformat(timespec="seconds"))
    except Exception as e:
        raise HTTPException(502, f"Yahoo 美股資料暫時無法使用：{e}")
    if data["rows"]:
        await rds.set("us:latest", json.dumps(data, ensure_ascii=False))
    return JSONResponse(data, headers={"Cache-Control": "no-cache"})


@router.get("/api/global/fundamentals")
async def global_fundamentals(symbol: str, request: Request):
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise HTTPException(400, "代號格式不正確")
    s = request.app.state
    key = f"yahoo:fund:{symbol}"
    cached = await asyncio.to_thread(s.store.kv_get, key, 6 * 3600)
    if cached is not None:
        return cached
    try:
        async with yahoo.make_client() as client:
            raw = await yahoo.quote_summary(client, symbol)
    except httpx.HTTPStatusError as e:
        raise HTTPException(404 if e.response.status_code == 404 else 502, f"找不到 {symbol}" if e.response.status_code == 404 else "Yahoo 暫時無法使用")
    except httpx.HTTPError:
        raise HTTPException(502, "Yahoo 暫時無法使用")
    data = gf.build(symbol, raw, datetime.now(TZ).isoformat(timespec="seconds"))
    await asyncio.to_thread(s.store.kv_put, key, data)
    return data


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
