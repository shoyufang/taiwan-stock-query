"""全球市場（Yahoo）：主要指數、原物料與匯率、台灣 ADR 溢價。純函式＋抓取組裝。

ADR 換算比例（1 單位 ADR＝幾股台股）：TSM 5、UMC 5、ASX 2。
2026-10-17 以實價驗算：ASX 用 2 得溢價 +0.9%，用 5 會變成不合理的 −59.6%（舊站 adr_query.py 一律用 5 是錯的）。
"""

from __future__ import annotations

import asyncio
import logging

from app.sources import yahoo

log = logging.getLogger("global")

GROUPS = [
    ("美股", [("^GSPC", "標普 500"), ("^IXIC", "那斯達克"), ("^DJI", "道瓊工業"), ("^SOX", "費城半導體"),
             ("^RUT", "羅素 2000"), ("^VIX", "VIX 恐慌指數")]),
    ("亞洲", [("^N225", "日經 225"), ("^HSI", "恒生指數"), ("000001.SS", "上證指數"), ("399001.SZ", "深證成指"),
             ("^KS11", "韓國綜合"), ("^AXJO", "澳洲 ASX 200"), ("^BSESN", "印度 SENSEX"), ("^STI", "新加坡海峽時報")]),
    ("歐洲", [("^GDAXI", "德國 DAX"), ("^FTSE", "英國富時 100")]),
    ("原物料・利率", [("CL=F", "WTI 原油"), ("GC=F", "黃金"), ("HG=F", "銅"), ("^TNX", "美國 10 年債殖利率")]),
    ("匯率", [("TWD=X", "美元／台幣"), ("DX-Y.NYB", "美元指數"), ("JPY=X", "美元／日圓"), ("CNY=X", "美元／人民幣")]),
]
YAHOO_CONCURRENCY = 8  # 代號變多後限制同時連線數，避免被 Yahoo 限流

ADRS = [("TSM", "2330.TW", "台積電", 5), ("UMC", "2303.TW", "聯電", 5), ("ASX", "3711.TW", "日月光投控", 2)]


def summarize(symbol: str, name: str, bars: list[dict]) -> dict | None:
    if len(bars) < 2:
        return None
    last, prev = bars[-1], bars[-2]
    return {"symbol": symbol, "name": name, "date": last["date"].isoformat(), "close": round(last["close"], 4),
            "change": round(last["close"] - prev["close"], 4),
            "change_pct": round((last["close"] - prev["close"]) / prev["close"] * 100, 2),
            "spark": [round(b["close"], 4) for b in bars[-22:]]}


def adr_premium(adr: dict, local: dict, fx: dict, ratio: int) -> dict:
    """溢價＝ADR 換算台幣每股價格 ÷ 台股收盤 − 1。"""
    implied = adr["close"] * fx["close"] / ratio
    return {"adr": adr["symbol"], "local": local["symbol"], "ratio": ratio,
            "adr_close": adr["close"], "adr_date": adr["date"], "local_close": local["close"], "local_date": local["date"],
            "fx": fx["close"], "fx_date": fx["date"], "implied_twd": round(implied, 2),
            "premium_pct": round((implied / local["close"] - 1) * 100, 2)}


async def _bars(client, symbol: str, range_: str = "3mo") -> list[dict]:
    return yahoo.parse_bars(await yahoo.daily_bars(client, symbol, range_))


async def build(generated_at: str) -> dict:
    async with yahoo.make_client() as client:
        symbols = [s for _, items in GROUPS for s, _ in items] + [a for a, _, _, _ in ADRS] + [t for _, t, _, _ in ADRS]
        sem = asyncio.Semaphore(YAHOO_CONCURRENCY)

        async def one(s: str) -> list[dict]:
            async with sem:
                return await _bars(client, s)

        results = await asyncio.gather(*[one(s) for s in symbols], return_exceptions=True)
    bars = {}
    for s, r in zip(symbols, results):
        if isinstance(r, Exception):
            log.warning("Yahoo %s 失敗：%s", s, r)
        else:
            bars[s] = r

    groups = []
    for title, items in GROUPS:
        rows = [x for s, n in items if (x := summarize(s, n, bars.get(s, [])))]
        groups.append({"title": title, "items": rows})

    fx = summarize("TWD=X", "美元／台幣", bars.get("TWD=X", []))
    adrs = []
    for adr_sym, tw_sym, name, ratio in ADRS:
        a, t = summarize(adr_sym, name, bars.get(adr_sym, [])), summarize(tw_sym, name, bars.get(tw_sym, []))
        if a and t and fx:
            adrs.append({"name": name, **adr_premium(a, t, fx, ratio), "adr_change_pct": a["change_pct"]})
    return {"generated_at": generated_at, "groups": groups, "adrs": adrs,
            "sources": ["Yahoo Finance"], "note": "各市場收盤日不同，請看每列的日期。"}
