"""警示規則（純函式）。

盤中規則看永豐推播（即時）；收盤規則每天收盤後看日 K 與法人。同一規則同一天只通知一次（由 store 去重）。
舊站 alert_engine.py 的 pct_move 誤用漲跌「金額」、ma20_break 未實作，這裡重寫。
"""

from __future__ import annotations

from app.services.stock import streak

# type → (說明, 時機, 數值單位, 允許範圍)
RULES = {
    "price_above": ("價格突破", "intraday", "元", (0.01, 1e6)),
    "price_below": ("價格跌破", "intraday", "元", (0.01, 1e6)),
    "pct_move": ("單日漲跌幅達", "intraday", "%", (0.5, 10)),
    "ma20_break": ("收盤跌破月線（20 日均線）", "close", "", (0, 0)),
    "ma20_reclaim": ("收盤站上月線（20 日均線）", "close", "", (0, 0)),
    "foreign_buy_streak": ("外資連續買超達", "close", "天", (2, 30)),
    "foreign_sell_streak": ("外資連續賣超達", "close", "天", (2, 30)),
}


def validate(type_: str, value: float) -> str | None:
    """回傳錯誤訊息；合法回傳 None。"""
    if type_ not in RULES:
        return "未知的警示類型"
    lo, hi = RULES[type_][3]
    if (lo, hi) != (0, 0) and not (lo <= value <= hi):
        return f"數值需介於 {lo:g} 與 {hi:g} 之間"
    return None


def _p(x: float) -> str:
    return f"{x:,.0f}" if x == int(x) else f"{x:,.2f}"


def eval_price(rule: dict, price: float, pct: float, when: str) -> str | None:
    """價格類規則；when＝「現價」或「收盤」。"""
    t, v = rule["type"], rule["value"]
    if t == "price_above" and price >= v:
        return f"價格突破 {_p(v)} 元（{when} {_p(price)}）"
    if t == "price_below" and price <= v:
        return f"價格跌破 {_p(v)} 元（{when} {_p(price)}）"
    if t == "pct_move" and abs(pct) >= v:
        return f"單日{'上漲' if pct > 0 else '下跌'} {abs(pct):.2f}%（門檻 {v:g}%）"
    return None


def _ma(closes: list[float]) -> float:
    return sum(closes) / len(closes)


def eval_close(rule: dict, bars: list[dict], foreign: list[int]) -> str | None:
    """收盤規則。bars 為日 K（舊→新）；foreign 為外資每日買賣超（張，舊→新，最後一筆須與 bars 同日）。"""
    t, v = rule["type"], rule["value"]
    if t in ("price_above", "price_below", "pct_move"):
        if len(bars) < 2:
            return None
        last, prev = bars[-1], bars[-2]
        pct = (last["close"] - prev["close"]) / prev["close"] * 100
        return eval_price(rule, last["close"], round(pct, 2), "收盤")
    if t in ("ma20_break", "ma20_reclaim"):
        if len(bars) < 21:
            return None
        closes = [b["close"] for b in bars]
        ma_now, ma_prev = _ma(closes[-20:]), _ma(closes[-21:-1])
        c, pc = closes[-1], closes[-2]
        if t == "ma20_break" and pc >= ma_prev and c < ma_now:
            return f"收盤 {_p(c)} 跌破月線 {_p(round(ma_now, 2))}"
        if t == "ma20_reclaim" and pc <= ma_prev and c > ma_now:
            return f"收盤 {_p(c)} 站上月線 {_p(round(ma_now, 2))}"
        return None
    if t in ("foreign_buy_streak", "foreign_sell_streak"):
        sign, n = streak(foreign)
        want = 1 if t == "foreign_buy_streak" else -1
        # 剛好達到門檻那天通知；之後每多一天也會再通知（每天最多一次）
        if sign == want and n >= v:
            return f"外資連續 {n} 天{'買超' if want > 0 else '賣超'}（今日 {foreign[-1]:+,} 張）"
        return None
    return None


def intraday_codes(rules: list[dict]) -> set[str]:
    return {r["code"] for r in rules if r["enabled"] and RULES.get(r["type"], ("", ""))[1] == "intraday"}
