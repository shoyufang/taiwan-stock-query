"""處置股／注意股通知（在 API 程序內，由 alert_runner.close_loop 呼叫）。

- 新公告的處置股（上市＋上櫃普通股）：一則彙整通知；自選股或持股會標 ★
- 自選股或持股被列入注意股：每檔每天一則
第一次執行只記錄現況、不通知，避免一啟用就把現有的十幾檔全推一次。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from app.services import attention as att
from app.services import notify

log = logging.getLogger("alerts")
SEEN_KEY = "attention:notified"
SEEN_TTL = 90 * 86400


def _md(iso: str) -> str:
    return f"{int(iso[5:7])}/{int(iso[8:10])}"


def disposition_message(items: list[dict], mine: set[str]) -> str:
    lines = []
    for d in items:
        star = "★" if d["code"] in mine else ""
        extra = f"，{d['match']}" if d["match"] else ""
        lines.append(f"{star}{d['code']} {d['name']}（{d['market']}）{_md(d['start'])}～{_md(d['end'])}{extra}")
    return "\n".join(lines)


async def my_codes(store, default: list[str]) -> set[str]:
    wl = await asyncio.to_thread(store.get_watchlist)
    holdings = await asyncio.to_thread(store.list_holdings)
    return set(wl if wl is not None else default) | {h["code"] for h in holdings}


async def run_once(app, now: datetime, default_watchlist: list[str]) -> int:
    s = app.state
    raw = await s.redis.get("attention:latest")
    if not raw:
        return 0
    data = json.loads(raw)
    mine = await my_codes(s.store, default_watchlist)
    disp_keys = {att.disposition_key(d) for d in data["disposition"]}
    notice_mine = [n for n in data["notice"] if n["code"] in mine]
    notice_keys = {f"notice|{data['asof']}|{n['code']}" for n in notice_mine}

    if not await s.redis.exists(SEEN_KEY):
        await s.redis.sadd(SEEN_KEY, "init", *disp_keys, *notice_keys)
        await s.redis.expire(SEEN_KEY, SEEN_TTL)
        log.info("處置／注意股通知初始化：記錄現有 %d 筆，不通知", len(disp_keys) + len(notice_keys))
        return 0

    seen = await s.redis.smembers(SEEN_KEY)
    at = now.isoformat(timespec="seconds")
    sent = 0
    new_disp = att.new_dispositions(data, seen)
    if new_disp:
        title = f"新增處置股 {len(new_disp)} 檔"
        msg = disposition_message(new_disp, mine)
        first_mine = next((d["code"] for d in new_disp if d["code"] in mine), None)
        await notify.send(s.redis, s.http, title=title, message=msg, code=first_mine, at=at)
        await asyncio.to_thread(s.store.add_event, first_mine or "", "disposition", f"{title}：{msg}", at)
        sent += 1
    for n in notice_mine:
        key = f"notice|{data['asof']}|{n['code']}"
        if key in seen:
            continue
        title = f"{n['name']} {n['code']} 被列注意股"
        await notify.send(s.redis, s.http, title=title, message=n["reason"], code=n["code"], at=at)
        await asyncio.to_thread(s.store.add_event, n["code"], "notice", f"{title}：{n['reason']}", at)
        sent += 1
    new_keys = {att.disposition_key(d) for d in new_disp} | (notice_keys - seen)
    if new_keys:
        await s.redis.sadd(SEEN_KEY, *new_keys)
        await s.redis.expire(SEEN_KEY, SEEN_TTL)
    return sent
