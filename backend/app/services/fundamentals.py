"""個股基本面（純函式）：季損益、資產負債、股利政策、本益比河流圖、同業比較。

FinMind 損益表為「單季」數字（已用 2330 2026Q2 營收＝4～6 月營收合計驗證）。
金融業沒有毛利、營業利益，欄位留 None。
"""

from __future__ import annotations

import re
from collections import defaultdict
from statistics import quantiles


def _by_date(rows: list[dict]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        out[r["date"]][r["type"]] = r["value"]
    return out


def _ratio(a: float | None, b: float | None, pct: bool = True) -> float | None:
    if a is None or not b:
        return None
    return round(a / b * (100 if pct else 1), 2)


def quarter_label(iso: str) -> str:
    return f"{iso[:4]}Q{(int(iso[5:7]) + 2) // 3}"


def income_quarters(rows: list[dict], n: int = 12) -> list[dict]:
    by = _by_date(rows)
    dates = sorted(by)
    out = []
    for i, d in enumerate(dates):
        v = by[d]
        rev = v.get("Revenue")
        net = v.get("EquityAttributableToOwnersOfParent", v.get("IncomeAfterTaxes", v.get("IncomeAfterTax")))
        prev_year = by.get(f"{int(d[:4]) - 1}{d[4:]}", {}).get("Revenue")
        out.append({"date": d, "quarter": quarter_label(d), "revenue": rev, "gross_profit": v.get("GrossProfit"),
                    "operating_income": v.get("OperatingIncome"), "net_income": net, "eps": v.get("EPS"),
                    "gross_margin": _ratio(v.get("GrossProfit"), rev), "operating_margin": _ratio(v.get("OperatingIncome"), rev),
                    "net_margin": _ratio(net, rev), "revenue_yoy": _ratio(rev - prev_year, prev_year) if rev and prev_year else None})
    return out[-n:]


def eps_ttm(quarters: list[dict]) -> float | None:
    eps = [q["eps"] for q in quarters[-4:] if q["eps"] is not None]
    return round(sum(eps), 2) if len(eps) == 4 else None


def balance_quarters(rows: list[dict], n: int = 8) -> list[dict]:
    by = _by_date(rows)
    out = []
    for d in sorted(by):
        v = by[d]
        equity_parent = v.get("EquityAttributableToOwnersOfParent", v.get("Equity"))
        shares = v["CapitalStock"] / 10 if v.get("CapitalStock") else None  # 面額 10 元
        out.append({"date": d, "quarter": quarter_label(d), "total_assets": v.get("TotalAssets"),
                    "liabilities": v.get("Liabilities"), "equity": v.get("Equity"),
                    "debt_ratio": _ratio(v.get("Liabilities"), v.get("TotalAssets")),
                    "current_ratio": _ratio(v.get("CurrentAssets"), v.get("CurrentLiabilities")),
                    "book_value_per_share": round(equity_parent / shares, 2) if equity_parent and shares else None})
    return out[-n:]


_ROC_YEAR = re.compile(r"\s*(\d{2,3})(?!\d)")  # 個股「112年第3季」、ETF 只有「112」


def dividend_years(rows: list[dict], quarters: list[dict] | None = None, n: int = 10) -> list[dict]:
    """依「所屬年度」彙總（季配息的四季合併）；配發率＝現金股利 ÷ 同年度 EPS（有四季資料才算）。"""
    years: dict[int, dict] = {}
    for r in rows:
        m = _ROC_YEAR.search(str(r.get("year", "")))
        if not m:
            continue
        y = int(m[1]) + 1911
        cash = (r.get("CashEarningsDistribution") or 0) + (r.get("CashStatutorySurplus") or 0)
        stock = (r.get("StockEarningsDistribution") or 0) + (r.get("StockStatutorySurplus") or 0)
        e = years.setdefault(y, {"year": y, "cash": 0.0, "stock": 0.0, "times": 0, "ex_dates": []})
        e["cash"] += cash
        e["stock"] += stock
        e["times"] += 1
        if r.get("CashExDividendTradingDate"):
            e["ex_dates"].append(r["CashExDividendTradingDate"])
    eps_by_year: dict[int, list[float]] = defaultdict(list)
    for q in quarters or []:
        if q["eps"] is not None:
            eps_by_year[int(q["date"][:4])].append(q["eps"])
    out = []
    for y in sorted(years)[-n:]:
        e = years[y]
        eps = round(sum(eps_by_year[y]), 2) if len(eps_by_year[y]) == 4 else None
        out.append({**e, "cash": round(e["cash"], 4), "stock": round(e["stock"], 4), "ex_dates": sorted(e["ex_dates"]),
                    "eps": eps, "payout": _ratio(e["cash"], eps) if eps and eps > 0 else None})
    return out


RIVER_PCTS = (10, 25, 50, 75, 90)


def pe_river(per_rows: list[dict], bars: list[dict], step: int = 5) -> dict | None:
    """本益比河流圖：隱含 EPS（收盤 ÷ 當日本益比）× 歷史本益比百分位（10/25/50/75/90）。
    每 step 個交易日取一點，最後一天一定保留。"""
    close = {b["date"]: b["close"] for b in bars}
    pts = [(r["date"], r["PER"], close[r["date"]]) for r in sorted(per_rows, key=lambda r: r["date"])
           if r.get("PER") and r["PER"] > 0 and r["date"] in close]
    if len(pts) < 60:
        return None
    pes = [p for _, p, _ in pts]
    q = quantiles(pes, n=100, method="inclusive")
    multiples = [round(q[p - 1], 2) for p in RIVER_PCTS]
    sampled = pts[::step] if pts[-1] in pts[::step] else [*pts[::step], pts[-1]]
    series = []
    for d, pe, c in sampled:
        eps = c / pe
        series.append({"date": d, "close": c, "bands": [round(eps * m, 2) for m in multiples]})
    return {"multiples": multiples, "percentiles": list(RIVER_PCTS), "series": series,
            "current_pe": pts[-1][1], "start": pts[0][0], "end": pts[-1][0]}


def peers(base: dict | None, code: str, industry: str | None, limit: int = 12) -> dict | None:
    """同產業（上市普通股，來自選股總表）依成交值排序；本股一定列入。"""
    if not base or not industry:
        return None
    rows = [r for r in base["rows"] if r.get("industry") == industry]
    if len(rows) < 2:
        return None
    rows.sort(key=lambda r: r.get("value_e8") or 0, reverse=True)
    picked = rows[:limit]
    if code not in {r["code"] for r in picked}:
        picked += [r for r in rows if r["code"] == code]
    keep = ("code", "name", "close", "change_pct", "pe", "pb", "dividend_yield", "foreign_streak", "value_e8")
    pe_vals = sorted(r["pe"] for r in rows if r.get("pe"))
    return {"industry": industry, "asof": base["asof"], "count": len(rows),
            "median_pe": pe_vals[len(pe_vals) // 2] if pe_vals else None,
            "rows": [{k: r.get(k) for k in keep} for r in picked]}


def build(code: str, income_rows: list[dict], balance_rows: list[dict], dividend_rows: list[dict],
          per_rows: list[dict], bars: list[dict], base: dict | None, industry: str | None, generated_at: str) -> dict:
    inc = income_quarters(income_rows, 12)
    all_inc = income_quarters(income_rows, 40)
    return {"code": code, "generated_at": generated_at, "income": inc, "eps_ttm": eps_ttm(inc),
            "balance": balance_quarters(balance_rows), "dividends": dividend_years(dividend_rows, all_inc),
            "river": pe_river(per_rows, bars), "peers": peers(base, code, industry),
            "units": {"amount": "元", "eps": "元", "margin": "%"},
            "sources": ["FinMind（綜合損益表、資產負債表、股利政策、本益比）", "臺灣證券交易所（同業本益比、殖利率，BWIBBU）"]}
