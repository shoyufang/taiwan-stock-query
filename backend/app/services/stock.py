"""個股頁：把 FinMind 原始資料整理成頁面資料與摘要句（純函式，不做網路呼叫）。

單位：法人與融資券一律「張」；營收「元」；股價「元」。
外資定義與證交所 T86「外陸資買賣超（不含外資自營商）」一致，故不計 Foreign_Dealer_Self。
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

GENERIC_INDUSTRY = {"電子工業"}


# ── 基本資料 ──

def pick_profile(info_rows: list[dict], code: str) -> dict | None:
    rows = [r for r in info_rows if r.get("stock_id") == code]
    if not rows:
        return None
    specific = [r for r in rows if r.get("industry_category") not in GENERIC_INDUSTRY]
    r = (specific or rows)[0]
    return {"code": code, "name": r["stock_name"].strip(), "industry": r["industry_category"],
            "market": {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}.get(r.get("type"), r.get("type"))}


def is_searchable(r: dict) -> bool:
    """排除權證（6 位純數字代號）與指數等非個股項目。"""
    code = r["stock_id"]
    if len(code) == 6 and code.isdigit():
        return False
    return r.get("industry_category") not in ("所有證券", "大盤", "Index")


def search(info_rows: list[dict], q: str, limit: int = 10) -> list[dict]:
    q = q.strip().upper()
    if not q:
        return []
    candidates = [r for r in info_rows if is_searchable(r)]

    def rank(r: dict) -> tuple[int, int] | None:
        code, name = r["stock_id"], r["stock_name"].strip().upper()
        if code == q or name == q:
            tier = 0
        elif code.startswith(q):
            tier = 1
        elif name.startswith(q):
            tier = 2
        elif q in name:
            tier = 3
        else:
            return None
        return tier, 0 if len(code) == 4 and not code.startswith("0") else 1  # 一般股票優先於 ETF 等

    scored = sorted(((rk, r["stock_id"]) for r in candidates if (rk := rank(r)) is not None))
    out, seen = [], set()
    for _, code in scored:
        if code in seen:
            continue
        seen.add(code)
        p = pick_profile(info_rows, code)
        if p:
            out.append(p)
        if len(out) >= limit:
            break
    return out


# ── 日 K ──

def bars_from_finmind(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if not r.get("close"):
            continue
        out.append({"date": r["date"], "open": float(r["open"]), "high": float(r["max"]), "low": float(r["min"]),
                    "close": float(r["close"]), "volume": round(int(r["Trading_Volume"]) / 1000),
                    "value": float(r["Trading_money"])})
    return out


def adjust_bars(bars: list[dict], dividends: list[dict]) -> list[dict]:
    """還原權值（向後調整）：除權息日之前的價格乘上 參考價／前一日收盤。"""
    events = sorted(((d["date"], d["after_price"] / d["before_price"]) for d in dividends
                     if d.get("before_price") and d.get("after_price")), reverse=True)
    out = []
    factor, i = 1.0, 0
    for b in reversed(bars):
        while i < len(events) and events[i][0] > b["date"]:
            factor *= events[i][1]
            i += 1
        out.append({**b, **{k: round(b[k] * factor, 2) for k in ("open", "high", "low", "close")}})
    return list(reversed(out))


# ── 法人 ──

def institutional_daily(rows: list[dict]) -> list[dict]:
    by_date: dict[str, dict] = defaultdict(lambda: {"foreign": 0, "trust": 0, "dealer": 0})
    for r in rows:
        net = int(r["buy"]) - int(r["sell"])
        d = by_date[r["date"]]
        if r["name"] == "Foreign_Investor":
            d["foreign"] += net
        elif r["name"] == "Investment_Trust":
            d["trust"] += net
        elif r["name"] in ("Dealer_self", "Dealer_Hedging"):
            d["dealer"] += net
    return [{"date": k, **{f: round(v / 1000) for f, v in by_date[k].items()}} for k in sorted(by_date)]


def streak(values: list[int]) -> tuple[int, int]:
    """從最後一天往回數同方向的天數 → (方向 1/-1/0, 天數)。"""
    sign, n = 0, 0
    for v in reversed(values):
        s = (v > 0) - (v < 0)
        if s == 0:
            break
        if sign == 0:
            sign = s
        if s != sign:
            break
        n += 1
    return sign, n


# ── 融資融券 ──

def margin_daily(rows: list[dict]) -> list[dict]:
    return [{"date": r["date"], "margin_balance": int(r["MarginPurchaseTodayBalance"]),
             "margin_change": int(r["MarginPurchaseTodayBalance"]) - int(r["MarginPurchaseYesterdayBalance"]),
             "short_balance": int(r["ShortSaleTodayBalance"])} for r in sorted(rows, key=lambda r: r["date"])]


# ── 月營收（用 revenue_year/revenue_month，不用公告日期）──

def revenue_monthly(rows: list[dict]) -> list[dict]:
    items = sorted(({"year": int(r["revenue_year"]), "month": int(r["revenue_month"]), "revenue": float(r["revenue"])}
                    for r in rows), key=lambda x: (x["year"], x["month"]))
    lookup = {(x["year"], x["month"]): x["revenue"] for x in items}
    for x in items:
        ly = lookup.get((x["year"] - 1, x["month"]))
        pm = lookup.get((x["year"] - 1, 12) if x["month"] == 1 else (x["year"], x["month"] - 1))
        x["yoy"] = round((x["revenue"] / ly - 1) * 100, 1) if ly else None
        x["mom"] = round((x["revenue"] / pm - 1) * 100, 1) if pm else None
    return items


# ── 本益比五年位置 ──

def pe_position(rows: list[dict]) -> dict | None:
    pts = [(r["date"], float(r["PER"])) for r in sorted(rows, key=lambda r: r["date"]) if r.get("PER") and r["PER"] > 0]
    if not pts:
        return None
    vals = [v for _, v in pts]
    cur = vals[-1]
    last = sorted(rows, key=lambda r: r["date"])[-1]
    return {"current": cur, "min": min(vals), "max": max(vals), "median": round(median(vals), 2),
            "pct_rank": round(sum(v < cur for v in vals) / len(vals) * 100, 1), "days": len(vals),
            "start": pts[0][0], "end": pts[-1][0],
            "pbr": last.get("PBR"), "dividend_yield": last.get("dividend_yield")}


# ── 摘要句 ──

def _lots(n: int) -> str:
    return f"{abs(n) / 10_000:.1f} 萬張" if abs(n) >= 10_000 else f"{abs(n):,} 張"


def _price(p: float) -> str:
    return f"{p:,.0f}" if p == int(p) else f"{p:,.2f}"


def _dir(v: float, up="上漲", down="下跌", flat="持平") -> str:
    return up if v > 0 else down if v < 0 else flat


def build_report(profile: dict, last: dict, prev_close: float, inst: list[dict], margin: list[dict],
                 revenue: list[dict], pe: dict | None, taiex_pct: float | None) -> dict:
    name = profile["name"]
    change = round(last["close"] - prev_close, 2)
    pct = round(change / prev_close * 100, 2) if prev_close else 0.0
    f_today = inst[-1]["foreign"] if inst and inst[-1]["date"] == last["date"] else None

    if f_today is not None and abs(f_today) >= 10_000:
        headline = f"{name}收 {_price(last['close'])} 元，外資單日{'買超' if f_today > 0 else '賣超'} {_lots(f_today)}"
    elif abs(pct) >= 3:
        headline = f"{name}{'大漲' if pct > 0 else '重挫'} {abs(pct):.2f}%，收 {_price(last['close'])} 元"
    else:
        headline = f"{name}收 {_price(last['close'])} 元，{_dir(pct)} {abs(pct):.2f}%" if pct else f"{name}收 {_price(last['close'])} 元，平盤"

    lead = [f"{name}{_dir(pct)} {abs(pct):.2f}%" if pct else f"{name}平盤"]
    # 只有上市股票拿來跟加權指數比；上櫃應比櫃買指數（尚未接入），興櫃不比
    if taiex_pct is not None and profile.get("market") == "上市":
        rel = "強於大盤" if pct > taiex_pct else "弱於大盤" if pct < taiex_pct else "與大盤同步"
        lead[0] += f"，同日加權指數{_dir(taiex_pct)} {abs(taiex_pct):.2f}%，{rel}"
    lead[0] += "。"

    sections = {}
    if inst:
        fs = [d["foreign"] for d in inst]
        sign, n = streak(fs)
        month = last["date"][:7]
        mtd = sum(d["foreign"] for d in inst if d["date"].startswith(month))
        if n >= 2:
            s = f"外資已連續 {n} 個交易日{'買超' if sign > 0 else '賣超'}"
        else:
            s = f"外資{'買超' if fs[-1] > 0 else '賣超'} {_lots(fs[-1])}" if fs[-1] else "外資買賣持平"
        s += f"，{int(month[5:])} 月以來累計{'買超' if mtd >= 0 else '賣超'}約 {_lots(mtd)}"
        t, d = inst[-1]["trust"], inst[-1]["dealer"]
        s2 = f"投信{'買超' if t > 0 else '賣超' if t < 0 else '持平'}{' ' + _lots(t) if t else ''}、自營商{'買超' if d > 0 else '賣超' if d < 0 else '持平'}{' ' + _lots(d) if d else ''}"
        lead.append(s + "；" + s2 + "。")
        sections["institutional"] = s + "。"
    if margin:
        last_m = margin[-1]
        sign, n = streak([m["margin_change"] for m in margin])
        if n >= 2:
            s = f"融資餘額連 {n} 日{'增加' if sign > 0 else '減少'}至 {last_m['margin_balance']:,} 張"
        else:
            s = f"融資餘額 {last_m['margin_balance']:,} 張（{_dir(last_m['margin_change'], '增加', '減少', '持平')} {abs(last_m['margin_change']):,} 張）"
        s += f"；融券餘額 {last_m['short_balance']:,} 張。"
        lead.append(s.replace("；融券餘額", "，融券餘額"))
        sections["margin"] = s
    if revenue:
        r = revenue[-1]
        s = f"{r['month']} 月營收 {r['revenue'] / 1e8:,.1f} 億元"
        if r["yoy"] is not None:
            s += f"，年增 {r['yoy']:.1f}%" if r["yoy"] >= 0 else f"，年減 {abs(r['yoy']):.1f}%"
        lead.append("基本面方面，" + s + "。")
        if r["mom"] is not None:
            s += f"、{'月增' if r['mom'] >= 0 else '月減'} {abs(r['mom']):.1f}%"
        sections["revenue"] = s + "。"
    if pe:
        sections["valuation"] = (f"本益比 {pe['current']:.2f} 倍，高於過去五年 {pe['pct_rank']:.0f}% 的交易日，"
                                 f"五年中位數 {pe['median']:.2f} 倍。")

    return {"headline": headline, "lead": "".join(lead), "sections": sections, "change": change, "change_pct": pct}


def build_stock_page(profile: dict, bars: list[dict], inst: list[dict], margin: list[dict], revenue: list[dict],
                     pe: dict | None, taiex_pct: float | None, generated_at: str) -> dict:
    if len(bars) < 2:
        raise ValueError(f"{profile['code']} 日 K 資料不足")
    last, prev = bars[-1], bars[-2]
    year = [b for b in bars if b["date"] > _minus_year(last["date"])]
    report = build_report(profile, last, prev["close"], inst, margin, revenue, pe, taiex_pct)
    return {
        "asof": last["date"],
        "generated_at": generated_at,
        "profile": profile,
        "quote": {"close": last["close"], "open": last["open"], "high": last["high"], "low": last["low"],
                  "prev_close": prev["close"], "change": report["change"], "change_pct": report["change_pct"],
                  "volume": last["volume"], "value": last["value"],
                  "week52_high": max(b["high"] for b in year), "week52_low": min(b["low"] for b in year)},
        "report": {k: report[k] for k in ("headline", "lead", "sections")},
        "institutional": inst[-15:],
        "margin": margin[-10:],
        "revenue": revenue[-13:],
        "valuation": pe,
        "units": {"institutional": "張", "margin": "張", "revenue": "元", "volume": "張"},
        "sources": ["FinMind（股價、法人、融資券、本益比、月營收）"],
    }


def _minus_year(d: str) -> str:
    return f"{int(d[:4]) - 1}{d[4:]}"
