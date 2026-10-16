"""個股資料載入：先查本地快取，缺的才向 FinMind 抓（多個資料集並行）。"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services import fundamentals as fu
from app.services import stock as st
from app.sources import finmind
from app.store import Store

TZ = ZoneInfo("Asia/Taipei")
HOUR = 3600


class StockNotFound(LookupError):
    pass


async def _cached(store: Store, key: str, ttl: float, fetcher):
    hit = await asyncio.to_thread(store.kv_get, key, ttl)
    if hit is not None:
        return hit
    data = await fetcher()
    await asyncio.to_thread(store.kv_put, key, data)
    return data


async def stock_info(store: Store, client) -> list[dict]:
    return await _cached(store, "finmind:info", 24 * HOUR,
                         lambda: finmind.fetch(client, "TaiwanStockInfo"))


async def ensure_bars(store: Store, client, code: str, today: date) -> None:
    """日 K 增量更新：沒有就抓全部歷史；有的話每小時最多檢查一次是否有新的交易日。"""
    last = await asyncio.to_thread(store.last_bar_date, code)
    if last and await asyncio.to_thread(store.kv_get, f"bars_checked:{code}", HOUR) is not None:
        return
    start = last or "1994-01-01"
    rows = await finmind.fetch(client, "TaiwanStockPrice", code, start, today.isoformat())
    bars = st.bars_from_finmind(rows)
    if bars:
        await asyncio.to_thread(store.upsert_bars, code, bars)
    await asyncio.to_thread(store.kv_put, f"bars_checked:{code}", True)


async def dividends(store: Store, client, code: str, today: date) -> list[dict]:
    return await _cached(store, f"finmind:div:{code}", 24 * HOUR,
                         lambda: finmind.fetch(client, "TaiwanStockDividendResult", code, "1994-01-01", today.isoformat()))


async def load_page(store: Store, client, rds, code: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    today = now.date()
    info = await stock_info(store, client)
    profile = st.pick_profile(info, code)
    if not profile:
        raise StockNotFound(code)

    def ds(name: str, days: int, ttl: float):
        start = (today - timedelta(days=days)).isoformat()
        return _cached(store, f"finmind:{name}:{code}", ttl,
                       lambda: finmind.fetch(client, name, code, start, today.isoformat()))

    _, inst_raw, margin_raw, per_raw, rev_raw = await asyncio.gather(
        ensure_bars(store, client, code, today),
        ds("TaiwanStockInstitutionalInvestorsBuySell", 45, 3 * HOUR),
        ds("TaiwanStockMarginPurchaseShortSale", 30, 3 * HOUR),
        ds("TaiwanStockPER", 5 * 366, 12 * HOUR),
        ds("TaiwanStockMonthRevenue", 15 * 31, 12 * HOUR),
    )
    bars = await asyncio.to_thread(store.get_bars, code, (today - timedelta(days=400)).isoformat())

    taiex_pct = None
    if rds is not None:
        raw = await rds.get("overview:latest")
        if raw:
            ov = json.loads(raw)
            if bars and ov.get("asof") == bars[-1]["date"]:
                taiex_pct = ov["taiex"]["change_pct"]

    return st.build_stock_page(profile, bars, st.institutional_daily(inst_raw), st.margin_daily(margin_raw),
                               st.revenue_monthly(rev_raw), st.pe_position(per_raw), taiex_pct,
                               now.isoformat(timespec="seconds"))


async def load_kbar(store: Store, client, code: str, adjusted: bool, years: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    today = now.date()
    await ensure_bars(store, client, code, today)
    since = None if years <= 0 else (today - timedelta(days=366 * years)).isoformat()
    bars = await asyncio.to_thread(store.get_bars, code, since)
    if adjusted:
        divs = await dividends(store, client, code, today)
        # 還原必須用完整歷史算因子，再截取區間
        full = await asyncio.to_thread(store.get_bars, code, None) if since else bars
        adj = st.adjust_bars(full, divs)
        bars = [b for b in adj if since is None or b["date"] >= since]
    return {"code": code, "adjusted": adjusted, "bars": bars}


async def load_fundamentals(store: Store, client, rds, code: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    today = now.date()
    info = await stock_info(store, client)
    profile = st.pick_profile(info, code)
    if not profile:
        raise StockNotFound(code)

    def ds(name: str, days: int):
        start = (today - timedelta(days=days)).isoformat()
        return _cached(store, f"finmind:{name}:{code}", 12 * HOUR,
                       lambda: finmind.fetch(client, name, code, start, today.isoformat()))

    _, inc_raw, bal_raw, div_raw, per_raw = await asyncio.gather(
        ensure_bars(store, client, code, today),
        ds("TaiwanStockFinancialStatements", 10 * 366),
        ds("TaiwanStockBalanceSheet", 3 * 366),
        ds("TaiwanStockDividend", 12 * 366),
        ds("TaiwanStockPER", 5 * 366),
    )
    bars = await asyncio.to_thread(store.get_bars, code, (today - timedelta(days=5 * 366)).isoformat())
    raw_base = await rds.get("screener:base") if rds is not None else None
    base = json.loads(raw_base) if raw_base else None
    return fu.build(code, inc_raw, bal_raw, div_raw, per_raw, bars, base, profile.get("industry"),
                    now.isoformat(timespec="seconds"))
