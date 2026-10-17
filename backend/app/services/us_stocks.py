"""美股權值 50 選股與財報日曆（Yahoo Finance v7 批次報價，純函式＋組裝）。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.sources import yahoo

NY_TZ = ZoneInfo("America/New_York")

# (Yahoo 代號, 中文名稱, 板塊)：對應舊站 stock_pools.US_TOP50 全數 50 檔
US_POOL: list[tuple[str, str, str]] = [
    # 科技巨頭 M7
    ("AAPL", "蘋果", "科技巨頭"),
    ("MSFT", "微軟", "科技巨頭"),
    ("GOOGL", "Alphabet", "科技巨頭"),
    ("AMZN", "亞馬遜", "科技巨頭"),
    ("META", "Meta", "科技巨頭"),
    ("NVDA", "輝達", "科技巨頭"),
    ("TSLA", "特斯拉", "科技巨頭"),
    # 半導體
    ("TSM", "台積電 ADR", "半導體"),
    ("AMD", "超微", "半導體"),
    ("INTC", "英特爾", "半導體"),
    ("ASML", "艾司摩爾", "半導體"),
    ("QCOM", "高通", "半導體"),
    ("AVGO", "博通", "半導體"),
    ("MU", "美光", "半導體"),
    ("TXN", "德州儀器", "半導體"),
    # 軟體與網路
    ("NFLX", "Netflix", "軟體與網路"),
    ("CRM", "Salesforce", "軟體與網路"),
    ("ADBE", "Adobe", "軟體與網路"),
    ("ORCL", "甲骨文", "軟體與網路"),
    ("CSCO", "思科", "軟體與網路"),
    ("ACN", "埃森哲", "軟體與網路"),
    # 消費與零售
    ("KO", "可口可樂", "消費與零售"),
    ("PEP", "百事", "消費與零售"),
    ("WMT", "沃爾瑪", "消費與零售"),
    ("COST", "好市多", "消費與零售"),
    ("PG", "寶僑", "消費與零售"),
    ("NKE", "Nike", "消費與零售"),
    ("MCD", "麥當勞", "消費與零售"),
    ("SBUX", "星巴克", "消費與零售"),
    # 金融與支付
    ("JPM", "摩根大通", "金融與支付"),
    ("BAC", "美國銀行", "金融與支付"),
    ("MS", "摩根士丹利", "金融與支付"),
    ("GS", "高盛", "金融與支付"),
    ("WFC", "富國銀行", "金融與支付"),
    ("V", "Visa", "金融與支付"),
    ("MA", "萬事達卡", "金融與支付"),
    ("BRK-B", "波克夏", "金融與支付"),
    # 生技與醫藥
    ("LLY", "禮來", "生技與醫藥"),
    ("JNJ", "嬌生", "生技與醫藥"),
    ("PFE", "輝瑞", "生技與醫藥"),
    ("MRK", "默克", "生技與醫藥"),
    ("UNH", "聯合健康", "生技與醫藥"),
    ("ABBV", "艾伯維", "生技與醫藥"),
    # 能源與工業
    ("XOM", "埃克森美孚", "能源與工業"),
    ("CVX", "雪佛龍", "能源與工業"),
    ("CAT", "卡特彼勒", "能源與工業"),
    ("GE", "奇異航太", "能源與工業"),
    ("HON", "漢威聯合", "能源與工業"),
    ("BA", "波音", "能源與工業"),
    ("DIS", "迪士尼", "能源與工業"),
]

POOL_MAP: dict[str, tuple[str, str]] = {sym: (name, sec) for sym, name, sec in US_POOL}
SECTORS: list[str] = list(dict.fromkeys(sec for _, _, sec in US_POOL))

_RATING_RE = re.compile(r"^\s*([0-9.]+)\s*-\s*(.+?)\s*$")
_RATING_ZH = {
    "strong buy": "強力買進",
    "buy": "買進",
    "hold": "持有",
    "underperform": "表現落後",
    "sell": "賣出",
    "strong sell": "強力賣出",
}


def parse_rating(raw: str | None) -> tuple[float | None, str | None]:
    """'2.2 - Buy' → (2.2, '買進')；分數愈接近 1 代表愈偏向買進。"""
    if not raw:
        return None, None
    m = _RATING_RE.match(str(raw))
    if not m:
        return None, _RATING_ZH.get(str(raw).strip().lower(), str(raw).strip())
    score = round(float(m[1]), 2)
    key = m[2].strip().lower()
    return score, _RATING_ZH.get(key, m[2].strip())


def _pos(v: float | None) -> float | None:
    return round(float(v), 2) if v is not None and v > 0 else None


def _num(v: float | None, digits: int = 2) -> float | None:
    return round(float(v), digits) if v is not None else None


def _ny_date(ts: int | float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), NY_TZ).date().isoformat()


def parse_quote(q: dict) -> dict | None:
    sym = q.get("symbol")
    price = q.get("regularMarketPrice")
    if not sym or price is None:
        return None
    zh_name, sector = POOL_MAP.get(sym, (q.get("shortName") or sym, "其他"))
    close = round(float(price), 2)
    high_52w = _pos(q.get("fiftyTwoWeekHigh")) or close
    low_52w = _pos(q.get("fiftyTwoWeekLow")) or close
    pullback = round((close - high_52w) / high_52w * 100, 2) if high_52w else 0.0
    mcap = q.get("marketCap")
    div_y = q.get("dividendYield")
    if div_y is None and q.get("trailingAnnualDividendYield") is not None:
        div_y = float(q["trailingAnnualDividendYield"]) * 100
    score, label = parse_rating(q.get("averageAnalystRating"))
    earn_ts = q.get("earningsTimestampStart") or q.get("earningsTimestamp")
    ma50 = q.get("fiftyDayAverage")
    ma200 = q.get("twoHundredDayAverage")
    if ma200 is None and q.get("twoHundredDayAverageChange") is not None:
        ma200 = close - float(q["twoHundredDayAverageChange"])

    return {
        "symbol": sym,
        "name": zh_name,
        "en_name": q.get("shortName") or q.get("longName") or sym,
        "sector": sector,
        "date": _ny_date(q.get("regularMarketTime")),
        "close": close,
        "change": _num(q.get("regularMarketChange")) or 0.0,
        "change_pct": _num(q.get("regularMarketChangePercent")) or 0.0,
        "market_cap_b": round(float(mcap) / 1e9, 1) if mcap else None,
        "pe": _pos(q.get("trailingPE")),
        "forward_pe": _pos(q.get("forwardPE")),
        "pb": _pos(q.get("priceToBook")),
        "dividend_yield": round(float(div_y), 2) if div_y is not None else 0.0,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pullback_pct": pullback,
        "above_ma50": bool(close >= float(ma50)) if ma50 else None,
        "above_ma200": bool(close >= float(ma200)) if ma200 else None,
        "eps_ttm": _num(q.get("epsTrailingTwelveMonths")),
        "eps_current_year": _num(q.get("epsCurrentYear")),
        "eps_forward": _num(q.get("epsForward")),
        "rating_score": score,
        "rating_label": label,
        "earnings_date": _ny_date(earn_ts),
        "earnings_is_estimate": bool(q.get("isEarningsDateEstimate", False)),
    }


def build(raw_quotes: list[dict], today: date, generated_at: str) -> dict:
    rows = [r for q in raw_quotes if (r := parse_quote(q)) is not None]
    rows.sort(key=lambda r: r["market_cap_b"] or 0, reverse=True)
    asof = max((r["date"] for r in rows if r.get("date")), default=today.isoformat())
    since = (today - timedelta(days=7)).isoformat()
    until = (today + timedelta(days=120)).isoformat()
    upcoming = [
        r for r in rows
        if r.get("earnings_date") and since <= r["earnings_date"] <= until
    ]
    upcoming.sort(key=lambda r: (r["earnings_date"], -(r["market_cap_b"] or 0)))
    return {
        "asof": asof,
        "today": today.isoformat(),
        "generated_at": generated_at,
        "sectors": SECTORS,
        "rows": rows,
        "upcoming_earnings": upcoming,
        "sources": ["Yahoo Finance（美股報價、估值、財報日曆、華爾街評等共識）"],
        "note": "評等分數 1.0 為強力買進、3.0 為持有、5.0 為賣出；財報日期以美東時間為準。",
    }


async def fetch_and_build(today: date, generated_at: str) -> dict:
    symbols = [s for s, _, _ in US_POOL]
    async with yahoo.make_client() as client:
        raw = await yahoo.quotes(client, symbols)
    return build(raw, today, generated_at)
