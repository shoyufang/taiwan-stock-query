"""投資組合 API：手動輸入持股（每筆一次買進），報價沿用自選股的最近收盤。

損益計算放在前端（盤中要用即時成交價覆蓋收盤價），後端只負責存取與收盤價。
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.api_watchlist import _row, _valid_codes
from app.services import stock_loader as loader

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
