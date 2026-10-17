import copy
import json
from pathlib import Path

from app.services import screener as sc

FIX = Path(__file__).parent / "fixtures"
load = lambda n: json.loads((FIX / n).read_text(encoding="utf-8"))  # noqa: E731


def t86_with(base: dict, foreign_by_code: dict[str, int]) -> dict:
    """以真實 T86 結構造出前幾天的資料（只改外資欄）。"""
    d = copy.deepcopy(base)
    f = {n: i for i, n in enumerate(d["fields"])}
    col = f["外陸資買賣超股數(不含外資自營商)"]
    for row in d["data"]:
        if row[0].strip() in foreign_by_code:
            row[col] = f"{foreign_by_code[row[0].strip()]:,}"
    return d


def test_parse_bwibbu_matches_official():
    v = sc.parse_bwibbu(load("bwibbu_20261016.json"))
    assert v["2330"] == {"pe": 28.05, "dividend_yield": 0.91, "pb": 9.76}  # 與 FinMind 同日數字一致
    assert v["1101"]["pe"] is None  # 虧損股本益比為「-」


def test_signed_streak():
    assert sc.signed_streak([1, -2, -3]) == -2
    assert sc.signed_streak([5, 6]) == 2
    assert sc.signed_streak([5, 0]) == 0


def test_build_base():
    t86_today = load("t86_20261016.json")
    days = [
        t86_with(t86_today, {"2454": -1_000_000, "2002": 5_000_000}),
        t86_with(t86_today, {"2454": 2_000_000, "2002": 6_000_000}),  # 2454 前一天買超 → 打斷賣超
        t86_today,                                                     # 10/16：2454 外資 −1,622,341 股
    ]
    bw = load("bwibbu_20261016.json")
    base = sc.build_base("2026-10-16", load("mi_index_20261016.json"), days, bw, {"2454": "半導體業"}, "t")
    rows = {r["code"]: r for r in base["rows"]}
    r = rows["2454"]
    assert r["foreign"] == -1622 and r["foreign_streak"] == -1
    assert rows["2002"]["foreign_streak"] == 3  # 中鋼連 3 日買超
    v = sc.parse_bwibbu(bw)["2454"]
    assert (r["pe"], r["dividend_yield"], r["pb"], r["industry"]) == (v["pe"], v["dividend_yield"], v["pb"], "半導體業")
    assert r["close"] == 4250 and r["change_pct"] == 2.04  # 與市場總覽 10/16 數字一致
    assert "0050" not in rows and "00400A" not in rows  # 只收普通股
    assert base["days"] == 3


def test_parse_mi_ohlcv_and_monthly_revenue():
    mi = load("mi_index_20261016.json")
    ohlcv = sc.parse_mi_ohlcv(mi)
    assert "2330" in ohlcv and "0050" not in ohlcv
    b = ohlcv["2330"]
    assert b["c"] > 0 and b["h"] >= b["l"] and b["v"] > 0

    revs = sc.parse_monthly_revenue([
        {
            "公司代號": "2330",
            "資料年月": "11509",
            "營業收入-去年同月增減(%)": "39.584",
            "營業收入-上月比較增減(%)": "0.412",
        },
        {"公司代號": "0050", "資料年月": "11509", "營業收入-去年同月增減(%)": "10"},
    ])
    assert revs == {"2330": {"rev_yoy": 39.58, "rev_mom": 0.41, "rev_ym": "2026-09"}}


def test_compute_technicals_bullish_and_breakout():
    # 構造 60 根穩步上漲、最後一根放量大漲突破的日 K
    bars = []
    for i in range(59):
        p = 100.0 + i * 0.5
        bars.append({"o": p - 0.2, "h": p + 0.5, "l": p - 0.5, "c": p, "v": 1_000_000})
    # 第 60 根放量 3 倍、大漲突破布林上軌與 20 日高點
    bars.append({"o": 130.0, "h": 138.0, "l": 129.5, "c": 137.0, "v": 3_000_000})
    t = sc.compute_technicals(bars)
    assert t["ma5"] > t["ma10"] > t["ma20"] > t["ma60"]
    assert t["rsi14"] > 70
    assert t["vol_ratio"] > 2.0
    for sig in ("ma_bullish", "rsi_overbought", "bb_breakout", "vol_expand", "vol_2x", "high_20d"):
        assert sig in t["tech_signals"], f"expected {sig} in {t['tech_signals']}"


def test_compute_technicals_oversold_and_cross():
    # 前 30 根下跌造出超賣，可用於檢驗空頭排列、RSI 超賣與 KD 超賣
    down_bars = []
    for i in range(30):
        p = 200.0 - i * 2.0
        down_bars.append({"o": p + 0.5, "h": p + 1.0, "l": p - 1.0, "c": p - 0.8, "v": 1_000_000})
    td = sc.compute_technicals(down_bars)
    assert "ma_bearish" in td["tech_signals"]
    assert "rsi_oversold" in td["tech_signals"]
    assert "kd_oversold" in td["tech_signals"]

    # 構造平盤 25 天後最後一天帶量長紅突破 MA20（觸發 ma5_cross_ma20 與 vol_breakout）
    flat_bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1_000_000} for _ in range(25)]
    flat_bars[-1] = {"o": 100.0, "h": 108.0, "l": 100.0, "c": 107.0, "v": 2_500_000}
    tc = sc.compute_technicals(flat_bars)
    assert "ma5_cross_ma20" in tc["tech_signals"]
    assert "vol_breakout" in tc["tech_signals"]


def test_build_base_includes_tech_and_rev():
    mi = load("mi_index_20261016.json")
    t86_today = load("t86_20261016.json")
    bw = load("bwibbu_20261016.json")
    day_ohlcv = sc.parse_mi_ohlcv(mi)
    ohlcv_days = [day_ohlcv for _ in range(25)]
    revs = {"2330": {"rev_yoy": 35.2, "rev_mom": 4.1, "rev_ym": "2026-09"}}
    base = sc.build_base("2026-10-16", mi, [t86_today], bw, {"2330": "半導體業"}, "t",
                         ohlcv_days=ohlcv_days, rev_map=revs)
    rows = {r["code"]: r for r in base["rows"]}
    tsmc = rows["2330"]
    assert tsmc["in_tw50"] is True
    assert tsmc["rev_yoy"] == 35.2 and tsmc["rev_ym"] == "2026-09"
    assert tsmc["vol_lots"] > 0
    assert tsmc["total_inst"] == tsmc["foreign"] + tsmc["trust"] + tsmc["dealer"]
    assert tsmc["ma20"] == tsmc["close"]
    assert base["tech_days"] == 25

