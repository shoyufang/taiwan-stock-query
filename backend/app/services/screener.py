"""選股總表（純函式）：上市普通股的單日官方資料＋法人連續買賣超天數＋產業。

篩選在前端做（一次載入約一千檔，條件即時生效）。
"""

from __future__ import annotations

from app.services import overview as ov
from app.services.stock import streak

SHARES_PER_LOT = 1000


def parse_bwibbu(raw: dict) -> dict[str, dict]:
    f = {name: i for i, name in enumerate(raw.get("fields") or [])}
    out = {}
    for row in raw.get("data", []):
        out[row[f["證券代號"]].strip()] = {
            "pe": ov.num(row[f["本益比"]]),
            "dividend_yield": ov.num(row[f["殖利率(%)"]]),
            "pb": ov.num(row[f["股價淨值比"]]),
        }
    return out


def signed_streak(values: list[int]) -> int:
    """連續買超 n 天回傳 +n、連續賣超回傳 −n、今天為 0 回傳 0。"""
    sign, n = streak(values)
    return sign * n


def build_base(asof: str, mi_raw: dict, t86_days: list[dict], bwibbu_raw: dict,
               industry: dict[str, str], generated_at: str) -> dict:
    """t86_days：由舊到新的 T86 原始回應，最後一筆必須是 asof 當日。"""
    quotes = [q for q in ov.parse_mi_index(mi_raw)["quotes"] if ov.is_common_stock(q["code"])]
    val = parse_bwibbu(bwibbu_raw)

    history: dict[str, list[tuple[int, int, int]]] = {}
    for day in t86_days:
        today_codes = set()
        for r in ov.parse_t86(day):
            history.setdefault(r["code"], []).append((r["foreign"], r["trust"], r["dealer"]))
            today_codes.add(r["code"])
        for code, h in history.items():  # 當天沒有資料的股票視為 0（打斷連續）
            if code not in today_codes:
                h.append((0, 0, 0))

    rows = []
    for q in quotes:
        h = history.get(q["code"], [(0, 0, 0)])
        f, t, d = h[-1]
        v = val.get(q["code"], {})
        rows.append({
            "code": q["code"], "name": q["name"], "industry": industry.get(q["code"], ""),
            "close": q["close"], "change_pct": q["change_pct"], "value_e8": round(q["value_twd"] / 1e8, 2),
            "pe": v.get("pe"), "dividend_yield": v.get("dividend_yield"), "pb": v.get("pb"),
            "foreign": round(f / SHARES_PER_LOT), "trust": round(t / SHARES_PER_LOT), "dealer": round(d / SHARES_PER_LOT),
            "foreign_streak": signed_streak([x[0] for x in h]),
            "trust_streak": signed_streak([x[1] for x in h]),
        })
    return {"asof": asof, "generated_at": generated_at, "days": len(t86_days), "rows": rows,
            "units": {"institutional": "張", "value": "億元"},
            "sources": ["臺灣證券交易所（MI_INDEX、T86、BWIBBU_d）", "FinMind（產業別）"]}
