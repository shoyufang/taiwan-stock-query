"""港美股基本面：把 Yahoo quoteSummary 原始資料整理成頁面資料（純函式，不做網路呼叫）。

比率一律轉成百分比（Yahoo 給 0.164 → 16.4）。金額保留原幣別：
報價幣別（currency）與財報幣別（financial_currency）可能不同，例如 TSM 以美元報價、以新台幣編財報。
指數、期貨、匯率沒有這些模組，回 has_data=False。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")

REC_ZH = {
    "strong_buy": "強力買進",
    "buy": "買進",
    "hold": "持有",
    "underperform": "表現落後",
    "sell": "賣出",
    "strong_sell": "強力賣出",
}


def _raw(d: dict | None, key: str):
    """Yahoo 數值多半包成 {"raw": 1.2, "fmt": "1.20"}；空物件 {} 代表無資料。"""
    v = (d or {}).get(key)
    if isinstance(v, dict):
        return v.get("raw")
    return v


def _num(d: dict | None, key: str, digits: int = 2) -> float | None:
    v = _raw(d, key)
    return round(float(v), digits) if isinstance(v, (int, float)) else None


def _pct(d: dict | None, key: str, digits: int = 2) -> float | None:
    v = _raw(d, key)
    return round(float(v) * 100, digits) if isinstance(v, (int, float)) else None


def _pos(d: dict | None, key: str, digits: int = 2) -> float | None:
    v = _num(d, key, digits)
    return v if v is not None and v > 0 else None


def _date(d: dict | None, key: str) -> str | None:
    v = _raw(d, key)
    if not isinstance(v, (int, float)) or v <= 0:
        return None
    return datetime.fromtimestamp(int(v), UTC).date().isoformat()


def quarters(res: dict, n: int = 4) -> list[dict]:
    """近四季營收、淨利（earnings.financialsChart）對上 EPS 實際與預估（earningsHistory），依季末日期排序。"""
    eps_by_q: dict[str, dict] = {}
    for h in (res.get("earningsHistory") or {}).get("history") or []:
        q = _date(h, "quarter")
        if q:
            eps_by_q[q[:7]] = {"eps": _num(h, "epsActual", 3), "eps_estimate": _num(h, "epsEstimate", 3),
                               "surprise_pct": _pct(h, "surprisePercent", 1)}
    out = []
    for q in ((res.get("earnings") or {}).get("financialsChart") or {}).get("quarterly") or []:
        label = q.get("date") or ""  # 例：'2Q2026'
        if len(label) != 6 or label[0] not in "1234" or label[1] != "Q":
            continue
        qn, year = int(label[0]), int(label[2:])
        end_month = f"{year}-{qn * 3:02d}"
        rev, ni = _raw(q, "revenue"), _raw(q, "earnings")
        out.append({"quarter": f"{year}Q{qn}", "revenue": rev, "net_income": ni,
                    "net_margin": round(ni / rev * 100, 2) if rev and ni is not None else None,
                    **eps_by_q.get(end_month, {"eps": None, "eps_estimate": None, "surprise_pct": None})})
    out.sort(key=lambda r: r["quarter"])
    return out[-n:]


def build(symbol: str, res: dict, generated_at: str) -> dict:
    price, sd, ks, fd = res.get("price") or {}, res.get("summaryDetail") or {}, res.get("defaultKeyStatistics") or {}, res.get("financialData") or {}
    ap, cal = res.get("assetProfile") or {}, res.get("calendarEvents") or {}
    qs = quarters(res)
    has_data = bool(fd or qs or _raw(sd, "trailingPE") or ap.get("sector"))
    earn_dates = [d for x in ((cal.get("earnings") or {}).get("earningsDate") or []) if (d := _date({"v": x}, "v"))]
    rec_key = fd.get("recommendationKey")
    return {
        "symbol": symbol,
        "name": price.get("longName") or price.get("shortName") or symbol,
        "quote_type": price.get("quoteType"),
        "currency": price.get("currency") or sd.get("currency"),
        "financial_currency": fd.get("financialCurrency") or (res.get("earnings") or {}).get("financialCurrency"),
        "has_data": has_data,
        "generated_at": generated_at,
        "profile": {
            "sector": ap.get("sectorDisp") or ap.get("sector"),
            "industry": ap.get("industryDisp") or ap.get("industry"),
            "country": ap.get("country"),
            "employees": ap.get("fullTimeEmployees"),
            "website": ap.get("website"),
            "summary": ap.get("longBusinessSummary"),
        },
        "valuation": {
            "market_cap": _raw(price, "marketCap") or _raw(sd, "marketCap"),
            "trailing_pe": _pos(sd, "trailingPE"),
            "forward_pe": _pos(sd, "forwardPE") or _pos(ks, "forwardPE"),
            "pb": _pos(ks, "priceToBook"),
            "ps": _pos(sd, "priceToSalesTrailing12Months"),
            "peg": _pos(ks, "pegRatio"),
            "eps_ttm": _num(ks, "trailingEps"),
            "eps_forward": _num(ks, "forwardEps"),
            "beta": _num(sd, "beta") or _num(ks, "beta"),
        },
        "dividend": {
            "rate": _pos(sd, "dividendRate", 4),
            "yield_pct": _pct(sd, "dividendYield"),
            "payout_pct": _pct(sd, "payoutRatio", 1),
            "five_year_avg_yield_pct": _num(sd, "fiveYearAvgDividendYield"),  # Yahoo 這欄本來就是百分比
            "ex_date": _date(sd, "exDividendDate") or _date(cal, "exDividendDate"),
        },
        "profitability": {
            "gross_margin": _pct(fd, "grossMargins"),
            "operating_margin": _pct(fd, "operatingMargins"),
            "profit_margin": _pct(fd, "profitMargins"),
            "roe": _pct(fd, "returnOnEquity"),
            "roa": _pct(fd, "returnOnAssets"),
            "revenue_growth": _pct(fd, "revenueGrowth"),
            "earnings_growth": _pct(fd, "earningsGrowth"),
        },
        "health": {
            "total_revenue": _raw(fd, "totalRevenue"),
            "total_cash": _raw(fd, "totalCash"),
            "total_debt": _raw(fd, "totalDebt"),
            "free_cashflow": _raw(fd, "freeCashflow"),
            "debt_to_equity": _num(fd, "debtToEquity", 1),  # Yahoo 給的是百分比（例 102.6 ＝ 負債是權益的 1.03 倍）
            "current_ratio": _num(fd, "currentRatio"),
        },
        "analyst": {
            "target_mean": _pos(fd, "targetMeanPrice"),
            "target_high": _pos(fd, "targetHighPrice"),
            "target_low": _pos(fd, "targetLowPrice"),
            "count": _raw(fd, "numberOfAnalystOpinions"),
            "rating_score": _num(fd, "recommendationMean"),
            "rating_key": rec_key,
            "rating_label": REC_ZH.get(rec_key or "", rec_key) if rec_key and rec_key != "none" else None,
        },
        "quarters": qs,
        "next_earnings": earn_dates[0] if earn_dates else None,
        "sources": ["Yahoo Finance（quoteSummary：公司簡介、估值、獲利能力、財務、分析師共識、近四季財報）"],
    }
