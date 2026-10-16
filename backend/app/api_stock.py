"""個股 API：/api/stock/{code}、/api/stock/{code}/kbar、/api/stock/{code}/fundamentals、/api/search。"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from app.services import stock as st
from app.services import stock_loader as loader
from app.sources.finmind import FinMindError

router = APIRouter()
CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")


def _check(code: str) -> str:
    code = code.upper()
    if not CODE_RE.match(code):
        raise HTTPException(400, "代號格式不正確")
    return code


@router.get("/api/stock/{code}")
async def stock_page(code: str, request: Request):
    s = request.app.state
    try:
        return await loader.load_page(s.store, s.finmind, s.redis, _check(code))
    except loader.StockNotFound:
        raise HTTPException(404, f"找不到股票 {code}")
    except FinMindError as e:
        raise HTTPException(502, f"資料來源暫時無法使用：{e}")


@router.get("/api/stock/{code}/kbar")
async def stock_kbar(code: str, request: Request, adjusted: bool = False, years: int = 5):
    s = request.app.state
    try:
        return await loader.load_kbar(s.store, s.finmind, _check(code), adjusted, max(min(years, 40), 0))
    except FinMindError as e:
        raise HTTPException(502, f"資料來源暫時無法使用：{e}")


@router.get("/api/stock/{code}/fundamentals")
async def stock_fundamentals(code: str, request: Request):
    s = request.app.state
    try:
        return await loader.load_fundamentals(s.store, s.finmind, s.redis, _check(code))
    except loader.StockNotFound:
        raise HTTPException(404, f"找不到股票 {code}")
    except FinMindError as e:
        raise HTTPException(502, f"資料來源暫時無法使用：{e}")


@router.get("/api/search")
async def search(q: str, request: Request):
    s = request.app.state
    info = await loader.stock_info(s.store, s.finmind)
    return {"results": st.search(info, q[:20])}
