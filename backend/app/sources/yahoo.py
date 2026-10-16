"""Yahoo Finance chart API（國際指數、ADR、匯率）。直接打 JSON，不依賴 yfinance。"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
CRUMB_COOKIE_URL = "https://fc.yahoo.com"
CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
QUOTE_URL = "https://query2.finance.yahoo.com/v7/finance/quote"


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers={"User-Agent": "Mozilla/5.0"})


async def quotes(client: httpx.AsyncClient, symbols: list[str]) -> list[dict]:
    """Yahoo v7 批次報價（含本益比、市值、52 週高低、財報日、華爾街評等）。"""
    await client.get(CRUMB_COOKIE_URL, follow_redirects=True)
    cr = await client.get(CRUMB_URL, follow_redirects=True)
    cr.raise_for_status()
    r = await client.get(QUOTE_URL, params={"symbols": ",".join(symbols), "crumb": cr.text.strip()})
    r.raise_for_status()
    return r.json().get("quoteResponse", {}).get("result") or []


async def daily_bars(client: httpx.AsyncClient, symbol: str, range_: str = "1mo") -> dict:
    r = await client.get(URL.format(symbol=symbol), params={"range": range_, "interval": "1d"})
    r.raise_for_status()
    return r.json()


def parse_bars(raw: dict) -> list[dict]:
    """→ [{'date': date（交易所當地日期）, 'close': float}]，略過收盤價為空的列。"""
    res = raw["chart"]["result"][0]
    tz = ZoneInfo(res["meta"].get("exchangeTimezoneName") or "UTC")
    closes = res["indicators"]["quote"][0]["close"]
    out = []
    for ts, c in zip(res.get("timestamp") or [], closes):
        if c is None:
            continue
        out.append({"date": datetime.fromtimestamp(ts, tz).date(), "close": float(c)})
    return out


def parse_ohlc(raw: dict) -> dict:
    """→ {meta: {...}, bars: [{date, open, high, low, close, volume, value}]}（日期為交易所當地）。"""
    res = raw["chart"]["result"][0]
    meta = res["meta"]
    tz = ZoneInfo(meta.get("exchangeTimezoneName") or "UTC")
    q = res["indicators"]["quote"][0]
    bars = []
    for i, ts in enumerate(res.get("timestamp") or []):
        o, h, lo, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (o, h, lo, c):
            continue
        bars.append({"date": datetime.fromtimestamp(ts, tz).date().isoformat(), "open": round(o, 4), "high": round(h, 4),
                     "low": round(lo, 4), "close": round(c, 4), "volume": int(v or 0), "value": 0.0})
    info = {"symbol": meta.get("symbol"), "name": meta.get("longName") or meta.get("shortName") or meta.get("symbol"),
            "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName") or meta.get("exchangeName")}
    return {"meta": info, "bars": bars}


def last_before(bars: list[dict], d: date, inclusive: bool = False) -> tuple[dict, dict] | None:
    """取日期在 d 之前（或含 d）的最後一根與前一根，用來算漲跌。"""
    eligible = [b for b in bars if (b["date"] <= d if inclusive else b["date"] < d)]
    if len(eligible) < 2:
        return None
    return eligible[-1], eligible[-2]
