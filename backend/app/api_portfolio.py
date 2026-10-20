"""投資組合 API：手動輸入持股（每筆一次買進），報價沿用自選股的最近收盤。

損益計算放在前端（盤中要用即時成交價覆蓋收盤價），後端只負責存取與收盤價。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.api_watchlist import _row, _valid_codes
from app.services import portfolio_risk as pr
from app.services import stock as st
from app.services import stock_loader as loader
from app.sources.finmind import FinMindError

router = APIRouter()
TZ = ZoneInfo("Asia/Taipei")
MAX_HOLDINGS = 200


class HoldingIn(BaseModel):
    code: str
    shares: int = Field(gt=0, le=100_000_000)  # 股數（1 張 = 1,000 股，零股直接填股數）
    cost: float = Field(gt=0, le=1_000_000)  # 每股成本（含手續費與否由使用者決定，頁面上有說明）
    bought_on: date | None = None
    note: str = Field(default="", max_length=100)

    @field_validator("bought_on")
    @classmethod
    def not_future(cls, v: date | None) -> date | None:
        if v and v > datetime.now(TZ).date():
            raise ValueError("買進日期不能是未來")
        return v


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


@router.get("/api/portfolio")
async def get_portfolio(request: Request):
    s = request.app.state
    holdings = await asyncio.to_thread(s.store.list_holdings)
    codes = list(dict.fromkeys(h["code"] for h in holdings))
    info = await loader.stock_info(s.store, s.finmind)
    today = datetime.now(TZ).date()
    quotes = await asyncio.gather(*[_row(request, c, info, today) for c in codes])
    return {"holdings": holdings, "quotes": {q["code"]: q for q in quotes}}


@router.get("/api/portfolio/risk")
async def portfolio_risk(request: Request):
    """風險分析：以目前股數回推近一年（還原權值）組合淨值，算波動度、回撤、VaR、Beta、風險貢獻、相關性。"""
    s = request.app.state
    holdings = await asyncio.to_thread(s.store.list_holdings)
    positions: dict[str, int] = {}
    for h in holdings:  # 同一檔多筆買進合併
        positions[h["code"]] = positions.get(h["code"], 0) + int(h["shares"])
    now = datetime.now(TZ)
    today = now.date()
    key = "risk:" + hashlib.sha1(json.dumps(sorted(positions.items())).encode()).hexdigest()[:16] + f":{today}"
    cached = await asyncio.to_thread(s.store.kv_get, key, 3600)
    if cached is not None:
        return cached

    since = (today - timedelta(days=400)).isoformat()
    sem = asyncio.Semaphore(4)  # 控制 FinMind 並行數，避免持股多時燒光額度

    async def adjusted(code: str) -> list[dict] | None:
        """抓不到（FinMind 錯誤、額度用盡）回 None，與「歷史太短」分開標示。"""
        async with sem:
            try:
                await loader.ensure_bars(s.store, s.finmind, code, today)
                divs = await loader.dividends(s.store, s.finmind, code, today)
            except FinMindError:
                return None
        return st.adjust_bars(await asyncio.to_thread(s.store.get_bars, code, since), divs)

    async def index_bars() -> list[dict]:
        try:
            await loader.ensure_bars(s.store, s.finmind, "TAIEX", today)
        except FinMindError:
            return []
        return await asyncio.to_thread(s.store.get_bars, "TAIEX", since)

    info = await loader.stock_info(s.store, s.finmind)
    codes = list(positions)
    *adj, idx = await asyncio.gather(*[adjusted(c) for c in codes], index_bars())
    profiles = {c: (st.pick_profile(info, c) or {"code": c, "name": c}) for c in codes}
    failed = {c for c, a in zip(codes, adj) if a is None}
    data = pr.build(positions, {c: a for c, a in zip(codes, adj) if a is not None}, idx, profiles,
                    now.isoformat(timespec="seconds"), failed=failed)
    if data["status"] in ("ok", "empty") and not failed:  # 有抓失敗的就不快取，下次重試
        await asyncio.to_thread(s.store.kv_put, key, data)
    return data


@router.post("/api/portfolio")
async def add_holding(body: HoldingIn, request: Request):
    s = request.app.state
    (code,) = await _valid_codes(request, [body.code])
    if len(await asyncio.to_thread(s.store.list_holdings)) >= MAX_HOLDINGS:
        raise HTTPException(400, f"最多 {MAX_HOLDINGS} 筆")
    hid = await asyncio.to_thread(s.store.add_holding, code, body.shares, body.cost, _iso(body.bought_on),
                                  body.note.strip(), datetime.now(TZ).isoformat(timespec="seconds"))
    return {"id": hid}


@router.put("/api/portfolio/{holding_id}")
async def update_holding(holding_id: int, body: HoldingIn, request: Request):
    ok = await asyncio.to_thread(request.app.state.store.update_holding, holding_id, body.shares, body.cost,
                                 _iso(body.bought_on), body.note.strip())
    if not ok:
        raise HTTPException(404, "找不到這筆持股")
    return {"ok": True}


@router.delete("/api/portfolio/{holding_id}")
async def delete_holding(holding_id: int, request: Request):
    if not await asyncio.to_thread(request.app.state.store.delete_holding, holding_id):
        raise HTTPException(404, "找不到這筆持股")
    return {"ok": True}
