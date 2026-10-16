"""Yahoo Finance chart API（國際指數、ADR、匯率）。直接打 JSON，不依賴 yfinance。"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers={"User-Agent": "Mozilla/5.0"})


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


def last_before(bars: list[dict], d: date, inclusive: bool = False) -> tuple[dict, dict] | None:
    """取日期在 d 之前（或含 d）的最後一根與前一根，用來算漲跌。"""
    eligible = [b for b in bars if (b["date"] <= d if inclusive else b["date"] < d)]
    if len(eligible) < 2:
        return None
    return eligible[-1], eligible[-2]
