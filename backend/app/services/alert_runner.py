"""警示執行（在 API 程序內的背景工作）。

- intraday_loop：訂閱 Redis 上的個股推播（q:*），即時評估盤中規則
- close_loop：平日 14:30 後每 15 分鐘評估收盤規則（日 K、外資連續買賣超），並通知新處置股、自選股被列注意
- sync_pinned：把自選股與有盤中警示的代號寫進 quote:pinned，讓行情服務常駐訂閱
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from app.services import alerts as al
from app.services import attention_notify
from app.services import notify
from app.services import stock as st
from app.services import stock_loader as loader

log = logging.getLogger("alerts")
TZ = ZoneInfo("Asia/Taipei")
DEFAULT_WATCHLIST = ["2330", "2317", "2454", "2308", "2382"]


async def names(store, finmind_client) -> dict[str, str]:
    try:
        info = await loader.stock_info(store, finmind_client)
        return {r["stock_id"]: r["stock_name"].strip() for r in info}
    except Exception:
        return {}


async def fire(app, rule: dict, message: str, day: str, now: datetime, name_map: dict) -> bool:
    s = app.state
    at = now.isoformat(timespec="seconds")
    name = name_map.get(rule["code"], rule["code"])
    title = f"{name} {rule['code']}"
    new = await asyncio.to_thread(s.store.mark_triggered, rule["id"], day, rule["code"], rule["type"],
                                  f"{title}：{message}", at)
    if new:
        await notify.send(s.redis, s.http, title=title, message=message, code=rule["code"], at=at)
        log.info("警示觸發 #%s %s %s", rule["id"], title, message)
    return new


async def sync_pinned(app) -> None:
    s = app.state
    wl = await asyncio.to_thread(s.store.get_watchlist)
    rules = await asyncio.to_thread(s.store.list_rules)
    codes = set(wl if wl is not None else DEFAULT_WATCHLIST) | al.intraday_codes(rules)
    pipe = s.redis.pipeline()
    pipe.delete("quote:pinned")
    if codes:
        pipe.sadd("quote:pinned", *sorted(codes))
    await pipe.execute()


async def intraday_loop(app) -> None:
    s = app.state
    pubsub = s.redis.pubsub()
    await pubsub.psubscribe("q:*")
    rules: list[dict] = []
    name_map: dict = {}
    last_reload = 0.0
    try:
        while True:
            loop_now = asyncio.get_running_loop().time()
            if loop_now - last_reload > 15:
                rules = [r for r in await asyncio.to_thread(s.store.list_rules)
                         if r["enabled"] and al.RULES[r["type"]][1] == "intraday"]
                if not name_map:
                    name_map = await names(s.store, s.finmind)
                last_reload = loop_now
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not msg or msg.get("type") != "pmessage":
                continue
            try:
                q = json.loads(msg["data"])
            except ValueError:
                continue
            if q.get("kind") != "stock" or q.get("close") is None:
                continue
            now = datetime.now(TZ)
            if not (q.get("time") or "").startswith(now.date().isoformat()):
                continue  # 只用今天的推播
            for r in rules:
                if r["code"] == q["code"]:
                    m = al.eval_price(r, q["close"], q.get("change_pct", 0.0), "現價")
                    if m:
                        await fire(app, r, m, now.date().isoformat(), now, name_map)
    finally:
        await pubsub.aclose()


async def evaluate_close(app, now: datetime) -> int:
    """對所有收盤類（含價格類補判）規則評估一次；回傳新觸發數。"""
    s = app.state
    rules = [r for r in await asyncio.to_thread(s.store.list_rules) if r["enabled"]]
    if not rules:
        return 0
    name_map = await names(s.store, s.finmind)
    fired = 0
    for code in sorted({r["code"] for r in rules}):
        await loader.ensure_bars(s.store, s.finmind, code, now.date())
        bars = await asyncio.to_thread(s.store.get_bars, code, None)
        bars = bars[-60:]
        if not bars or bars[-1]["date"] != now.date().isoformat():
            continue  # 今天的日 K 還沒出來
        day = bars[-1]["date"]
        foreign: list[int] = []
        code_rules = [r for r in rules if r["code"] == code]
        if any(r["type"].startswith("foreign_") for r in code_rules):
            raw = await loader.finmind.fetch(s.finmind, "TaiwanStockInstitutionalInvestorsBuySell", code,
                                             bars[-40]["date"] if len(bars) >= 40 else bars[0]["date"], day)
            inst = st.institutional_daily(raw)
            if inst and inst[-1]["date"] == day:
                foreign = [d["foreign"] for d in inst]
        for r in code_rules:
            if r["type"].startswith("foreign_") and not foreign:
                continue
            m = al.eval_close(r, bars, foreign)
            if m and await fire(app, r, m, day, now, name_map):
                fired += 1
    return fired


async def close_loop(app) -> None:
    while True:
        now = datetime.now(TZ)
        if now.weekday() < 5 and now.time() >= dtime(14, 30):
            try:
                await evaluate_close(app, now)
            except Exception:
                log.exception("收盤警示評估失敗")
            try:
                await attention_notify.run_once(app, now, DEFAULT_WATCHLIST)
            except Exception:
                log.exception("處置／注意股通知失敗")
        await asyncio.sleep(900)


async def run(app) -> None:
    await sync_pinned(app)
    await asyncio.gather(intraday_loop(app), close_loop(app))
