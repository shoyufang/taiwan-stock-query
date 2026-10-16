"""自選股與警示 API。"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services import alert_runner as runner
from app.services import alerts as al
from app.services import notify
from app.services import stock as st
from app.services import stock_loader as loader

router = APIRouter()
TZ = ZoneInfo("Asia/Taipei")
CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")
MAX_WATCHLIST = 60


class WatchlistIn(BaseModel):
    codes: list[str]


class RuleIn(BaseModel):
    code: str
    type: str
    value: float = 0


class RulePatch(BaseModel):
    enabled: bool


async def _valid_codes(request: Request, codes: list[str]) -> list[str]:
    s = request.app.state
    info = await loader.stock_info(s.store, s.finmind)
    known = {r["stock_id"] for r in info}
    out = []
    for c in codes:
        c = c.strip().upper()
        if not CODE_RE.match(c) or c not in known:
            raise HTTPException(400, f"找不到股票 {c}")
        if c not in out:
            out.append(c)
    return out


async def _row(request: Request, code: str, profiles: list[dict], today) -> dict:
    s = request.app.state
    p = st.pick_profile(profiles, code) or {"code": code, "name": code}
    try:
        await loader.ensure_bars(s.store, s.finmind, code, today)
        bars = (await asyncio.to_thread(s.store.get_bars, code, None))[-2:]
    except Exception:
        bars = []
    if len(bars) < 2:
        return {"code": code, "name": p["name"], "date": None}
    prev, last = bars  # get_bars 由舊到新
    change = round(last["close"] - prev["close"], 2)
    return {"code": code, "name": p["name"], "date": last["date"], "close": last["close"], "change": change,
            "change_pct": round(change / prev["close"] * 100, 2), "volume": last["volume"],
            "high": last["high"], "low": last["low"]}


@router.get("/api/watchlist")
async def get_watchlist(request: Request):
    s = request.app.state
    saved = await asyncio.to_thread(s.store.get_watchlist)
    codes = saved if saved is not None else runner.DEFAULT_WATCHLIST
    info = await loader.stock_info(s.store, s.finmind)
    today = datetime.now(TZ).date()
    rows = await asyncio.gather(*[_row(request, c, info, today) for c in codes])
    return {"codes": codes, "is_default": saved is None, "rows": rows}


@router.put("/api/watchlist")
async def put_watchlist(body: WatchlistIn, request: Request):
    if len(body.codes) > MAX_WATCHLIST:
        raise HTTPException(400, f"自選股最多 {MAX_WATCHLIST} 檔")
    codes = await _valid_codes(request, body.codes)
    await asyncio.to_thread(request.app.state.store.set_watchlist, codes)
    await runner.sync_pinned(request.app)
    return {"codes": codes}


@router.get("/api/alerts")
async def list_alerts(request: Request):
    rules = await asyncio.to_thread(request.app.state.store.list_rules)
    types = {k: {"label": v[0], "when": v[1], "unit": v[2], "range": v[3]} for k, v in al.RULES.items()}
    return {"rules": rules, "types": types, "channels": notify.channels()}


@router.post("/api/alerts")
async def add_alert(body: RuleIn, request: Request):
    err = al.validate(body.type, body.value)
    if err:
        raise HTTPException(400, err)
    (code,) = await _valid_codes(request, [body.code])
    now = datetime.now(TZ).isoformat(timespec="seconds")
    rid = await asyncio.to_thread(request.app.state.store.add_rule, code, body.type, body.value, now)
    await runner.sync_pinned(request.app)
    return {"id": rid}


@router.patch("/api/alerts/{rule_id}")
async def patch_alert(rule_id: int, body: RulePatch, request: Request):
    if not await asyncio.to_thread(request.app.state.store.update_rule, rule_id, body.enabled):
        raise HTTPException(404, "找不到警示")
    await runner.sync_pinned(request.app)
    return {"ok": True}


@router.delete("/api/alerts/{rule_id}")
async def delete_alert(rule_id: int, request: Request):
    if not await asyncio.to_thread(request.app.state.store.delete_rule, rule_id):
        raise HTTPException(404, "找不到警示")
    await runner.sync_pinned(request.app)
    return {"ok": True}


@router.get("/api/alerts/events")
async def alert_events(request: Request, limit: int = 50):
    return {"events": await asyncio.to_thread(request.app.state.store.list_events, max(1, min(limit, 200)))}


@router.post("/api/alerts/test")
async def test_notify(request: Request):
    s = request.app.state
    now = datetime.now(TZ).isoformat(timespec="seconds")
    result = await notify.send(s.redis, s.http, title="測試通知", message="台股看盤的警示通知設定成功。",
                               code=None, at=now)
    return {"result": result}
