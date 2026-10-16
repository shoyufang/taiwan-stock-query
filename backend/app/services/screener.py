"""選股總表（純函式）：上市普通股的單日官方資料＋法人連續買賣超＋技術面指標與訊號＋月營收 YoY＋產業。

篩選在前端做（一次載入約一千檔，多因子漏斗與技術條件即時生效，無需等待後端重跑）。
"""

from __future__ import annotations

import statistics

from app.services import overview as ov
from app.services.stock import streak

SHARES_PER_LOT = 1000

# 台灣 50 成分股（與 stock_pools.TW_TOP50 同步）
TW_TOP50: set[str] = {
    "2330", "2454", "2308", "2317", "3711", "2303", "2383", "2327", "2891", "2345",
    "3037", "2881", "2382", "2882", "1303", "2887", "2885", "3017", "2360", "2886",
    "2890", "2884", "2412", "2344", "6669", "2883", "2357", "2408", "2059", "3231",
    "4958", "2301", "2368", "1216", "2892", "3008", "2880", "3443", "7769", "3665",
    "2449", "3661", "3653", "5880", "2395", "8046", "2603", "4904", "3045", "6505",
}

TECH_CONDITIONS: dict[str, str] = {
    "kd_golden": "KD 黃金交叉（低檔）",
    "kd_death": "KD 死亡交叉（高檔）",
    "kd_oversold": "KD 超賣 K<20",
    "macd_golden": "MACD 黃金交叉",
    "macd_positive": "MACD 柱狀翻正",
    "macd_death": "MACD 死亡交叉",
    "rsi_oversold": "RSI 超賣 <30",
    "rsi_overbought": "RSI 超買 >70",
    "ma_bullish": "均線多頭排列",
    "ma_bearish": "均線空頭排列",
    "ma5_cross_ma20": "MA5 黃金交叉 MA20",
    "ma5_death_ma20": "MA5 死亡交叉 MA20",
    "bb_breakout": "布林突破上軌",
    "bb_oversold": "布林觸下軌",
    "vol_breakout": "帶量突破 MA20",
    "vol_expand": "量增 >1.5 倍五日均量",
    "vol_2x": "爆量 >2 倍月均量",
    "high_20d": "突破 20 日高點",
}


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


def parse_mi_ohlcv(raw: dict) -> dict[str, dict]:
    """從單日 MI_INDEX 取出普通股 OHLCV：{code: {o, h, l, c, v}}（v 為成交股數）。"""
    table = None
    for t in raw.get("tables", []):
        if "每日收盤行情" in (t.get("title") or ""):
            table = t
            break
    if not table:
        return {}
    f = {name: i for i, name in enumerate(table.get("fields") or [])}
    out: dict[str, dict] = {}
    for row in table.get("data", []):
        code = row[f["證券代號"]].strip()
        if not ov.is_common_stock(code):
            continue
        c = ov.num(row[f["收盤價"]])
        if c is None:
            continue
        o = ov.num(row[f["開盤價"]]) if "開盤價" in f else None
        h = ov.num(row[f["最高價"]]) if "最高價" in f else None
        lo = ov.num(row[f["最低價"]]) if "最低價" in f else None
        v = int(ov.num(row[f["成交股數"]]) or 0) if "成交股數" in f else 0
        out[code] = {
            "o": o if o is not None else c,
            "h": h if h is not None else c,
            "l": lo if lo is not None else c,
            "c": c,
            "v": v,
        }
    return out


def parse_monthly_revenue(rows: list[dict]) -> dict[str, dict]:
    """解析證交所 OpenAPI t187ap05_L 月營收彙總表：{code: {rev_yoy, rev_mom, rev_ym}}。"""
    out: dict[str, dict] = {}
    for r in rows or []:
        code = str(r.get("公司代號") or "").strip()
        if not ov.is_common_stock(code):
            continue
        yoy = ov.num(r.get("營業收入-去年同月增減(%)"))
        mom = ov.num(r.get("營業收入-上月比較增減(%)"))
        ym_raw = str(r.get("資料年月") or "").strip()
        rev_ym = None
        if len(ym_raw) >= 5 and ym_raw.isdigit():
            roc_y, m = int(ym_raw[:-2]), int(ym_raw[-2:])
            rev_ym = f"{roc_y + 1911:04d}-{m:02d}"
        out[code] = {
            "rev_yoy": round(yoy, 2) if yoy is not None else None,
            "rev_mom": round(mom, 2) if mom is not None else None,
            "rev_ym": rev_ym,
        }
    return out


def compute_technicals(bars: list[dict]) -> dict:
    """由舊到新的日 K 序列 [{o, h, l, c, v}, ...] 計算技術指標與觸發訊號。"""
    empty = {
        "rsi14": None, "k": None, "d": None, "macd_hist": None,
        "ma5": None, "ma10": None, "ma20": None, "ma60": None,
        "vol_ratio": None, "tech_signals": [],
    }
    n = len(bars)
    if n < 5:
        return empty

    closes = [float(b["c"]) for b in bars]
    highs = [float(b.get("h", b["c"])) for b in bars]
    lows = [float(b.get("l", b["c"])) for b in bars]
    vols = [float(b.get("v", 0)) for b in bars]

    ma5 = sum(closes[-5:]) / 5
    ma5_prev = sum(closes[-6:-1]) / 5 if n >= 6 else None
    ma10 = sum(closes[-10:]) / 10 if n >= 10 else None
    ma20 = sum(closes[-20:]) / 20 if n >= 20 else None
    ma20_prev = sum(closes[-21:-1]) / 20 if n >= 21 else None
    ma60 = sum(closes[-60:]) / 60 if n >= 60 else None

    vol_ma5 = sum(vols[-5:]) / 5
    vol_ma20 = sum(vols[-20:]) / 20 if n >= 20 else None
    vol_ratio = round(vols[-1] / vol_ma20, 2) if (vol_ma20 and vol_ma20 > 0) else None

    # RSI(14) — 14 日簡單移動平均漲跌（對齊舊站 screener.py / technical_scanner.py）
    rsi14: float | None = None
    if n >= 15:
        deltas = [closes[i] - closes[i - 1] for i in range(n - 14, n)]
        avg_gain = sum(max(d, 0.0) for d in deltas) / 14
        avg_loss = sum(max(-d, 0.0) for d in deltas) / 14
        if avg_loss == 0:
            rsi14 = 100.0 if avg_gain > 0 else 50.0
        else:
            rsi14 = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    # KD(9, 3) — 9 日 RSV 與 3 日 K 均線（對齊舊站 _stoch）
    k_last = d_last = k_prev = d_prev = None
    if n >= 11:
        k_series: list[float] = []
        for i in range(8, n):
            lo9 = min(lows[i - 8 : i + 1])
            hi9 = max(highs[i - 8 : i + 1])
            k_series.append(100.0 * (closes[i] - lo9) / (hi9 - lo9) if hi9 > lo9 else 50.0)
        k_last = k_series[-1]
        d_last = sum(k_series[-3:]) / 3
        if len(k_series) >= 4:
            k_prev = k_series[-2]
            d_prev = sum(k_series[-4:-1]) / 3

    # MACD(12, 26, 9) — EMA(adjust=False)
    dif_last = sig_last = hist_last = dif_prev = sig_prev = hist_prev = None
    if n >= 26:
        af, a_s, asig = 2.0 / 13.0, 2.0 / 27.0, 2.0 / 10.0
        ef = es = closes[0]
        sig = 0.0
        for i, c in enumerate(closes):
            if i > 0:
                ef = af * c + (1.0 - af) * ef
                es = a_s * c + (1.0 - a_s) * es
            dif = ef - es
            sig = dif if i == 0 else (asig * dif + (1.0 - asig) * sig)
            hist = dif - sig
            if i == n - 2:
                dif_prev, sig_prev, hist_prev = dif, sig, hist
            elif i == n - 1:
                dif_last, sig_last, hist_last = dif, sig, hist

    # Bollinger Bands(20, 2)
    bb_u = bb_l = bb_u_prev = None
    if n >= 20:
        sd = statistics.stdev(closes[-20:])
        bb_u = ma20 + 2.0 * sd  # type: ignore[operator]
        bb_l = ma20 - 2.0 * sd  # type: ignore[operator]
        if n >= 21 and ma20_prev is not None:
            sd_prev = statistics.stdev(closes[-21:-1])
            bb_u_prev = ma20_prev + 2.0 * sd_prev

    signals: list[str] = []
    if k_prev is not None and d_prev is not None and k_last is not None and d_last is not None:
        if k_prev < d_prev and k_last > d_last and k_last < 50:
            signals.append("kd_golden")
        if k_prev > d_prev and k_last < d_last and k_last > 50:
            signals.append("kd_death")
    if k_last is not None and k_last < 20:
        signals.append("kd_oversold")

    if dif_prev is not None and sig_prev is not None and dif_last is not None and sig_last is not None:
        if dif_prev < sig_prev and dif_last > sig_last:
            signals.append("macd_golden")
        if dif_prev > sig_prev and dif_last < sig_last:
            signals.append("macd_death")
    if hist_prev is not None and hist_last is not None and hist_prev < 0 and hist_last > 0:
        signals.append("macd_positive")

    if rsi14 is not None:
        if rsi14 < 30:
            signals.append("rsi_oversold")
        if rsi14 > 70:
            signals.append("rsi_overbought")

    if ma10 is not None and ma20 is not None:
        if ma60 is not None:
            if ma5 > ma10 > ma20 > ma60:
                signals.append("ma_bullish")
            if ma5 < ma10 < ma20 < ma60:
                signals.append("ma_bearish")
        else:
            if ma5 > ma10 > ma20:
                signals.append("ma_bullish")
            if ma5 < ma10 < ma20:
                signals.append("ma_bearish")

    if ma5_prev is not None and ma20_prev is not None and ma20 is not None:
        if ma5_prev <= ma20_prev and ma5 > ma20:
            signals.append("ma5_cross_ma20")
        if ma5_prev >= ma20_prev and ma5 < ma20:
            signals.append("ma5_death_ma20")

    if bb_u is not None and bb_u_prev is not None and n >= 2:
        if closes[-2] <= bb_u_prev and closes[-1] > bb_u:
            signals.append("bb_breakout")
    if bb_l is not None and closes[-1] <= bb_l:
        signals.append("bb_oversold")

    if ma20 is not None and ma20_prev is not None and vol_ma20 is not None and n >= 2:
        if closes[-2] <= ma20_prev and closes[-1] > ma20 and vols[-1] > 1.5 * vol_ma20:
            signals.append("vol_breakout")
    if vol_ma5 > 0 and vols[-1] > 1.5 * vol_ma5:
        signals.append("vol_expand")
    if vol_ma20 is not None and vol_ma20 > 0 and vols[-1] > 2.0 * vol_ma20:
        signals.append("vol_2x")
    if n >= 20 and closes[-1] > max(closes[-20:-1]):
        signals.append("high_20d")

    return {
        "rsi14": round(rsi14, 1) if rsi14 is not None else None,
        "k": round(k_last, 1) if k_last is not None else None,
        "d": round(d_last, 1) if d_last is not None else None,
        "macd_hist": round(hist_last, 2) if hist_last is not None else None,
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2) if ma10 is not None else None,
        "ma20": round(ma20, 2) if ma20 is not None else None,
        "ma60": round(ma60, 2) if ma60 is not None else None,
        "vol_ratio": vol_ratio,
        "tech_signals": signals,
    }


def signed_streak(values: list[int]) -> int:
    """連續買超 n 天回傳 +n、連續賣超回傳 −n、今天為 0 回傳 0。"""
    sign, n = streak(values)
    return sign * n


def build_base(
    asof: str,
    mi_raw: dict,
    t86_days: list[dict],
    bwibbu_raw: dict,
    industry: dict[str, str],
    generated_at: str,
    ohlcv_days: list[dict[str, dict]] | None = None,
    rev_map: dict[str, dict] | None = None,
) -> dict:
    """t86_days：由舊到新的 T86 原始回應，最後一筆必須是 asof 當日。
    ohlcv_days：由舊到新的每日 OHLCV 字典（parse_mi_ohlcv 結果），供計算技術指標與訊號。
    """
    quotes = [q for q in ov.parse_mi_index(mi_raw)["quotes"] if ov.is_common_stock(q["code"])]
    today_ohlcv = parse_mi_ohlcv(mi_raw)
    val = parse_bwibbu(bwibbu_raw)
    revs = rev_map or {}

    history: dict[str, list[tuple[int, int, int]]] = {}
    for day in t86_days:
        today_codes = set()
        for r in ov.parse_t86(day):
            history.setdefault(r["code"], []).append((r["foreign"], r["trust"], r["dealer"]))
            today_codes.add(r["code"])
        for code, h in history.items():  # 當天沒有資料的股票視為 0（打斷連續）
            if code not in today_codes:
                h.append((0, 0, 0))

    bars_by_code: dict[str, list[dict]] = {}
    for day_map in ohlcv_days or [today_ohlcv]:
        for code, bar in day_map.items():
            bars_by_code.setdefault(code, []).append(bar)

    rows = []
    for q in quotes:
        code = q["code"]
        h = history.get(code, [(0, 0, 0)])
        f, t, d = h[-1]
        v = val.get(code, {})
        rev = revs.get(code, {})
        tech = compute_technicals(bars_by_code.get(code, []))
        vol_shares = today_ohlcv.get(code, {}).get("v", 0)
        rows.append({
            "code": code,
            "name": q["name"],
            "industry": industry.get(code, ""),
            "in_tw50": code in TW_TOP50,
            "close": q["close"],
            "change_pct": q["change_pct"],
            "value_e8": round(q["value_twd"] / 1e8, 2),
            "vol_lots": round(vol_shares / SHARES_PER_LOT),
            "pe": v.get("pe"),
            "dividend_yield": v.get("dividend_yield"),
            "pb": v.get("pb"),
            "rev_yoy": rev.get("rev_yoy"),
            "rev_mom": rev.get("rev_mom"),
            "rev_ym": rev.get("rev_ym"),
            "foreign": round(f / SHARES_PER_LOT),
            "trust": round(t / SHARES_PER_LOT),
            "dealer": round(d / SHARES_PER_LOT),
            "total_inst": round((f + t + d) / SHARES_PER_LOT),
            "foreign_streak": signed_streak([x[0] for x in h]),
            "trust_streak": signed_streak([x[1] for x in h]),
            "dealer_streak": signed_streak([x[2] for x in h]),
            **tech,
        })
    return {
        "asof": asof,
        "generated_at": generated_at,
        "days": len(t86_days),
        "tech_days": len(ohlcv_days) if ohlcv_days else 1,
        "rows": rows,
        "units": {"institutional": "張", "value": "億元", "volume": "張"},
        "sources": ["臺灣證券交易所（MI_INDEX、T86、BWIBBU_d、t187ap05_L）", "FinMind（產業別）"],
    }

