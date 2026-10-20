"""投資組合風險分析（純函式，不做網路呼叫；不依賴 numpy）。

假設（回傳時一併附上，前端照實顯示）：
- 「過去一年都持有目前的股數、不再平衡」：V_t = Σ 股數_i × 還原收盤_i,t。
  波動度、最大回撤、VaR、Sharpe、Beta 都由 V 的日報酬計算。
- 風險貢獻與相關性用「目前市值權重」（固定權重）計算：RC_i = w_i·cov(r_i, r_p) / var(r_p)，加總恰為 100%，可為負。
- 價格一律用還原權值（除權息向後調整，最新一日等於實際收盤），避免除息日被當成虧損。
- 上市櫃有 10% 漲跌幅限制：還原後單日漲跌超過 JUMP_LIMIT 視為分割、減資等未調整事件，當日報酬以 0 計並回報筆數。
- 各股只取共同交易日；近一年少於 MIN_BARS 筆的股票（新上市、長期停牌）排除並列出。
"""

from __future__ import annotations

import math
from statistics import mean

TRADING_DAYS = 252  # 年化採國際慣例 252 日（台股實際約 245 日，差異小）
WINDOW = 252  # 取最近 252 個共同交易日的報酬
MIN_BARS = 120
JUMP_LIMIT = 0.105
RISK_FREE = 0.017  # 無風險利率固定假設：約當台灣一年期定存，非即時利率
VAR_LEVEL = 0.95
CORR_TOP = 12


def _var(xs: list[float]) -> float:
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _cov(xs: list[float], ys: list[float]) -> float:
    mx, my = mean(xs), mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)


def corr(xs: list[float], ys: list[float]) -> float | None:
    vx, vy = _var(xs), _var(ys)
    if vx <= 0 or vy <= 0:
        return None
    return _cov(xs, ys) / math.sqrt(vx * vy)


def percentile(xs: list[float], q: float) -> float:
    """線性內插百分位（同 numpy 預設 'linear'）；q 介於 0～1。"""
    s = sorted(xs)
    if not s:
        raise ValueError("empty")
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def max_drawdown(values: list[float], dates: list[str]) -> dict:
    """最大回撤（負值，%）與高點／低點日期。"""
    peak_v, peak_d = values[0], dates[0]
    best = {"pct": 0.0, "peak_date": dates[0], "trough_date": dates[0]}
    for v, d in zip(values, dates):
        if v > peak_v:
            peak_v, peak_d = v, d
        dd = v / peak_v - 1
        if dd < best["pct"]:
            best = {"pct": dd, "peak_date": peak_d, "trough_date": d}
    return {**best, "pct": round(best["pct"] * 100, 2)}


def clean_returns(closes: list[float], guard: bool) -> tuple[list[float], int]:
    """日報酬；guard=True 時超過漲跌幅限制的跳動以 0 計。回傳（報酬, 被排除筆數）。"""
    out, jumps = [], 0
    for a, b in zip(closes, closes[1:]):
        r = b / a - 1
        if guard and abs(r) > JUMP_LIMIT:
            r, jumps = 0.0, jumps + 1
        out.append(r)
    return out, jumps


def risk_contributions(weights: list[float], rets: list[list[float]]) -> list[float]:
    """固定權重下各資產占組合變異數的比例（加總為 1）。"""
    rp = [sum(w * r[t] for w, r in zip(weights, rets)) for t in range(len(rets[0]))]
    vp = _var(rp)
    if vp <= 0:
        return [0.0 for _ in weights]
    return [w * _cov(r, rp) / vp for w, r in zip(weights, rets)]


def build(positions: dict[str, int], series: dict[str, list[dict]], index_bars: list[dict],
          profiles: dict[str, dict], generated_at: str, failed: set[str] | None = None) -> dict:
    """positions：代號→股數（已合併多筆買進）；series：代號→還原後日 K（由舊到新）；
    index_bars：加權指數日 K；profiles：代號→{name, industry, market}；failed：資料來源抓取失敗的代號。"""
    failed = failed or set()
    assumptions = {
        "window_days": WINDOW, "annualization_days": TRADING_DAYS, "risk_free_pct": round(RISK_FREE * 100, 2),
        "var_level_pct": VAR_LEVEL * 100, "rebalancing": "不再平衡（持有目前股數）",
        "price_basis": "還原權值收盤", "benchmark": "加權指數（價格指數，未含息）",
    }
    base = {"generated_at": generated_at, "assumptions": assumptions, "excluded": [], "excluded_jumps": 0}
    if not positions:
        return {**base, "status": "empty"}

    included, excluded = [], []
    for code in positions:
        n = len(series.get(code) or [])
        if code in failed:
            excluded.append({"code": code, "name": profiles.get(code, {}).get("name", code), "bars": 0,
                             "reason": "資料來源暫時無法取得"})
        elif n < MIN_BARS:
            excluded.append({"code": code, "name": profiles.get(code, {}).get("name", code), "bars": n,
                             "reason": f"近一年交易日不足 {MIN_BARS} 天"})
        else:
            included.append(code)
    base["excluded"] = excluded
    if not included:
        return {**base, "status": "insufficient"}

    # 共同交易日，取最近 WINDOW+1 天（得到 WINDOW 個報酬）
    common = set.intersection(*(set(b["date"] for b in series[c]) for c in included))
    dates = sorted(common)[-(WINDOW + 1):]
    if len(dates) < MIN_BARS:
        return {**base, "status": "insufficient"}
    close = {c: {b["date"]: b["close"] for b in series[c]} for c in included}

    rets, idx_levels, jumps = {}, {}, 0
    for c in included:
        guard = profiles.get(c, {}).get("market") in ("上市", "上櫃")
        r, j = clean_returns([close[c][d] for d in dates], guard)
        rets[c], jumps = r, jumps + j
        # 由清理後報酬重建價格指數，錨定最後一天＝實際（還原）收盤
        lv = [1.0]
        for x in r:
            lv.append(lv[-1] * (1 + x))
        last = close[c][dates[-1]]
        idx_levels[c] = [v / lv[-1] * last for v in lv]
    base["excluded_jumps"] = jumps

    values = [sum(positions[c] * idx_levels[c][t] for c in included) for t in range(len(dates))]
    mv = {c: positions[c] * close[c][dates[-1]] for c in included}
    total = sum(mv.values())
    weights = [mv[c] / total for c in included]

    rv = [b / a - 1 for a, b in zip(values, values[1:])]
    n = len(rv)
    vol = math.sqrt(_var(rv)) * math.sqrt(TRADING_DAYS)
    ann_ret = (values[-1] / values[0]) ** (TRADING_DAYS / n) - 1
    var_pct = -percentile(rv, 1 - VAR_LEVEL)

    # Beta：只用大盤與組合都有資料的相鄰交易日（大盤缺幾天不致整個算不出來）
    beta = None
    idx_close = {b["date"]: b["close"] for b in index_bars}
    pairs = [(r, idx_close[b] / idx_close[a] - 1) for r, a, b in zip(rv, dates, dates[1:])
             if a in idx_close and b in idx_close]
    if len(pairs) >= MIN_BARS:
        rp_, rm = [p for p, _ in pairs], [m for _, m in pairs]
        vm = _var(rm)
        beta = round(_cov(rp_, rm) / vm, 2) if vm > 0 else None

    rc = risk_contributions(weights, [rets[c] for c in included])
    holdings = []
    for c, w, k in zip(included, weights, rc):
        p = profiles.get(c, {})
        holdings.append({"code": c, "name": p.get("name", c), "industry": p.get("industry"),
                         "shares": positions[c], "market_value": round(mv[c]), "weight_pct": round(w * 100, 2),
                         "risk_pct": round(k * 100, 2),
                         "vol_pct": round(math.sqrt(_var(rets[c])) * math.sqrt(TRADING_DAYS) * 100, 2)})
    holdings.sort(key=lambda h: h["market_value"], reverse=True)

    industries: dict[str, float] = {}
    for h in holdings:
        key = h["industry"] or "其他"
        industries[key] = industries.get(key, 0) + h["weight_pct"]
    industry_rows = sorted(({"industry": k, "weight_pct": round(v, 2)} for k, v in industries.items()),
                           key=lambda r: r["weight_pct"], reverse=True)

    correlation = None
    if len(included) >= 2:
        top = [h["code"] for h in holdings[:CORR_TOP]]
        correlation = {"codes": top, "names": [profiles.get(c, {}).get("name", c) for c in top],
                       "matrix": [[1.0 if a == b else (round(x, 2) if (x := corr(rets[a], rets[b])) is not None else None)
                                   for b in top] for a in top]}

    return {
        **base,
        "status": "ok",
        "start": dates[0],
        "end": dates[-1],
        "days": n,
        "market_value": round(total),
        "metrics": {
            "annual_return_pct": round(ann_ret * 100, 2),
            "annual_vol_pct": round(vol * 100, 2),
            "sharpe": round((ann_ret - RISK_FREE) / vol, 2) if vol > 0 else None,
            "max_drawdown": max_drawdown(values, dates),
            "var_1d_pct": round(var_pct * 100, 2),
            "var_1d_amount": round(var_pct * total),
            "beta": beta,
        },
        "holdings": holdings,
        "industries": industry_rows,
        "top_weight_pct": holdings[0]["weight_pct"],
        "correlation": correlation,
        "series": [{"date": d, "value": round(v)} for d, v in zip(dates, values)],
    }
