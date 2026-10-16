"""市場總覽（盤後）：解析證交所官方回應並組裝成單一資料日期的頁面資料。

全部為純函式，不做網路呼叫；抓資料與排程在 app/worker.py。
資料日期契約：整頁數字都屬於同一個 asof 交易日（國際市場另標其收盤日）。
"""

from __future__ import annotations

from datetime import date

SHARES_PER_LOT = 1000


# ── 基本解析 ────────────────────────────────────────────

def num(s) -> float | None:
    """'1,234.5' → 1234.5；'--'、'' → None。"""
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "---", "X"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sign_of(html: str) -> int:
    """證交所漲跌欄是 HTML：'<p style= color:red>+</p>' → 1，green/'-' → -1，其餘 0。"""
    h = html or ""
    if "+" in h or "red" in h:
        return 1
    if "-" in h or "green" in h:
        return -1
    return 0


def count_with_limit(s: str) -> tuple[int, int]:
    """'684(19)' → (684, 19)。"""
    s = (s or "").replace(",", "")
    if "(" in s:
        a, b = s.split("(", 1)
        return int(a), int(b.rstrip(")"))
    return int(s), 0


def is_common_stock(code: str) -> bool:
    return len(code) == 4 and code.isdigit() and not code.startswith("0")


def roc_to_date(s: str) -> date:
    """'115/10/16' → date(2026, 10, 16)。"""
    y, m, d = (int(x) for x in s.split("/"))
    return date(y + 1911, m, d)


def _table(raw: dict, keyword: str) -> dict | None:
    for t in raw.get("tables", []):
        if keyword in (t.get("title") or "") or (keyword == "漲跌證券數合計" and t.get("title") == keyword):
            return t
    return None


# ── MI_INDEX（ALLBUT0999）──────────────────────────────

def has_trading_data(raw: dict) -> bool:
    t = _table(raw, "每日收盤行情")
    return raw.get("stat") == "OK" and bool(t and t.get("data"))


def parse_mi_index(raw: dict) -> dict:
    idx = _table(raw, "價格指數(臺灣證券交易所)")
    taiex = None
    for row in (idx or {}).get("data", []):
        if row[0] == "發行量加權股價指數":
            sgn = sign_of(row[2])
            taiex = {"close": num(row[1]), "change": sgn * (num(row[3]) or 0.0), "change_pct": num(row[4])}
            break

    turnover = None
    for row in (_table(raw, "大盤統計資訊") or {}).get("data", []):
        if row[0].startswith("總計"):
            turnover = num(row[1])

    breadth = {}
    for row in (_table(raw, "漲跌證券數合計") or {}).get("data", []):
        kind, stocks = row[0], row[2]
        if kind.startswith("上漲"):
            breadth["up"], breadth["up_limit"] = count_with_limit(stocks)
        elif kind.startswith("下跌"):
            breadth["down"], breadth["down_limit"] = count_with_limit(stocks)
        elif kind == "持平":
            breadth["flat"] = count_with_limit(stocks)[0]
        elif kind == "未成交":
            breadth["untraded"] = count_with_limit(stocks)[0]

    quotes = []
    table = _table(raw, "每日收盤行情") or {}
    f = {name: i for i, name in enumerate(table.get("fields") or [])}
    for row in table.get("data", []):
        close = num(row[f["收盤價"]])
        if close is None:
            continue
        sgn_raw = row[f["漲跌(+/-)"]]
        sgn = sign_of(sgn_raw)
        change = sgn * (num(row[f["漲跌價差"]]) or 0.0)
        prev = close - change
        quotes.append({
            "code": row[f["證券代號"]].strip(),
            "name": row[f["證券名稱"]].strip(),
            "close": close,
            "change": change,
            "change_pct": round(change / prev * 100, 2) if prev else 0.0,
            "value_twd": num(row[f["成交金額"]]) or 0.0,
            "ex_right": "X" in (sgn_raw or ""),
        })
    return {"taiex": taiex, "turnover_twd": turnover, "breadth": breadth, "quotes": quotes}


# ── T86 三大法人 ────────────────────────────────────────

def parse_t86(raw: dict) -> list[dict]:
    """→ [{code, name, foreign, trust, dealer}]，單位：股。"""
    f = {name: i for i, name in enumerate(raw.get("fields") or [])}
    cols = {
        "foreign": "外陸資買賣超股數(不含外資自營商)",
        "trust": "投信買賣超股數",
        "dealer": "自營商買賣超股數",
    }
    out = []
    for row in raw.get("data", []):
        item = {"code": row[f["證券代號"]].strip(), "name": row[f["證券名稱"]].strip()}
        for k, col in cols.items():
            item[k] = int(num(row[f[col]]) or 0)
        out.append(item)
    return out


# ── FMTQIK 加權指數日序列 ───────────────────────────────

def parse_fmtqik(raw: dict) -> list[dict]:
    f = {name: i for i, name in enumerate(raw.get("fields") or [])}
    out = []
    for row in raw.get("data", []):
        close = num(row[f["發行量加權股價指數"]])
        if close is not None:
            out.append({"date": roc_to_date(row[f["日期"]]).isoformat(), "close": close})
    return out


# ── 摘要句 ──────────────────────────────────────────────

def move_word(pct: float) -> str:
    if pct >= 2:
        return "大漲"
    if pct >= 0.5:
        return "上漲"
    if pct > 0:
        return "小漲"
    if pct == 0:
        return "平盤"
    if pct > -0.5:
        return "小跌"
    if pct > -2:
        return "下跌"
    return "重挫"


def _lots_wan(shares: int) -> str:
    return f"{abs(shares) / SHARES_PER_LOT / 10_000:.1f} 萬張"


def _net(label: str, shares: int) -> str:
    if shares == 0:
        return f"{label}持平"
    return f"{label}{'買超' if shares > 0 else '賣超'} {_lots_wan(shares)}"


def _fmt_price(p: float) -> str:
    return f"{p:,.0f}" if p == int(p) else f"{p:,.2f}"


def build_headline(taiex: dict) -> str:
    pct = taiex["change_pct"]
    if pct == 0:
        return f"加權指數平盤，收 {taiex['close']:,.0f} 點"
    return f"加權指數{move_word(pct)} {abs(pct):.2f}%，收 {taiex['close']:,.0f} 點"


def build_lead(breadth: dict, turnover_twd: float, inst: dict, top: dict | None) -> str:
    parts = [
        f"上市股票 {breadth.get('up', 0)} 家上漲、{breadth.get('down', 0)} 家下跌，"
        f"成交金額 {turnover_twd / 1e8:,.0f} 億元。",
        f"三大法人中，{_net('外資', inst['foreign'])}、{_net('投信', inst['trust'])}、{_net('自營商', inst['dealer'])}。",
    ]
    if top:
        direction = "上漲" if top["change_pct"] > 0 else ("下跌" if top["change_pct"] < 0 else "持平")
        tail = f"{direction} {abs(top['change_pct']):.2f}%" if top["change_pct"] else "持平"
        parts.append(f"成交值最大的是{top['name']}，收 {_fmt_price(top['close'])} 元，{tail}。")
    return "".join(parts)


# ── 組裝 ────────────────────────────────────────────────

def _quote_row(q: dict) -> dict:
    return {k: q[k] for k in ("code", "name", "close", "change", "change_pct", "value_twd")}


def build_overview(asof: date, mi_raw: dict, t86_raw: dict, series: list[dict],
                   international: list[dict], generated_at: str) -> dict:
    mi = parse_mi_index(mi_raw)
    if not mi["taiex"] or mi["turnover_twd"] is None:
        raise ValueError(f"{asof} 的 MI_INDEX 缺少加權指數或成交統計")

    inst_rows = parse_t86(t86_raw)
    totals = {k: sum(r[k] for r in inst_rows) for k in ("foreign", "trust", "dealer")}
    four = [r for r in inst_rows if len(r["code"]) == 4]
    by_foreign = sorted(four, key=lambda r: r["foreign"], reverse=True)

    quotes = mi["quotes"]
    stocks = [q for q in quotes if is_common_stock(q["code"]) and not q["ex_right"] and q["value_twd"] > 0]
    top_value = sorted(quotes, key=lambda q: q["value_twd"], reverse=True)[:10]

    return {
        "asof": asof.isoformat(),
        "generated_at": generated_at,
        "headline": build_headline(mi["taiex"]),
        "lead": build_lead(mi["breadth"], mi["turnover_twd"], totals, top_value[0] if top_value else None),
        "taiex": mi["taiex"],
        "turnover_twd": mi["turnover_twd"],
        "breadth": mi["breadth"],
        "institutional": {k: round(v / SHARES_PER_LOT) for k, v in totals.items()},
        "top_value": [_quote_row(q) for q in top_value],
        "gainers": [_quote_row(q) for q in sorted(stocks, key=lambda q: q["change_pct"], reverse=True)[:8]],
        "losers": [_quote_row(q) for q in sorted(stocks, key=lambda q: q["change_pct"])[:8]],
        "foreign_buy": [{"code": r["code"], "name": r["name"], "lots": round(r["foreign"] / SHARES_PER_LOT)}
                        for r in by_foreign[:6] if r["foreign"] > 0],
        "foreign_sell": [{"code": r["code"], "name": r["name"], "lots": round(r["foreign"] / SHARES_PER_LOT)}
                         for r in reversed(by_foreign[-6:]) if r["foreign"] < 0],
        "index_series": [p for p in series if p["date"] <= asof.isoformat()],
        "international": international,
        "units": {"institutional": "張", "turnover": "元", "value": "元"},
        "sources": ["臺灣證券交易所（MI_INDEX、T86、FMTQIK）", "Yahoo Finance（國際市場）"],
    }
