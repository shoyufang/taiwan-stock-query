import math
from datetime import date, timedelta

import pytest

from app.services import portfolio_risk as pr
from app.services import stock as st


def series(closes, start=date(2025, 1, 1)):
    return [{"date": (start + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c, "close": c,
             "volume": 1, "value": 1} for i, c in enumerate(closes)]


def wave(n, amp, phase=0.0, base=100.0):
    return [base * (1 + amp * math.sin(i / 3 + phase)) for i in range(n)]


PROF = {"A": {"name": "甲", "industry": "半導體業", "market": "上市"},
        "B": {"name": "乙", "industry": "半導體業", "market": "上市"},
        "C": {"name": "丙", "industry": "金融保險業", "market": "上市"}}


def test_percentile_and_drawdown_known_values():
    assert pr.percentile([1, 2, 3, 4, 5], 0.05) == pytest.approx(1.2)
    dd = pr.max_drawdown([100, 120, 90, 110, 80, 130], ["d1", "d2", "d3", "d4", "d5", "d6"])
    assert dd == {"pct": round((80 / 120 - 1) * 100, 2), "peak_date": "d2", "trough_date": "d5"}


def test_single_holding_risk_is_100pct_and_no_correlation():
    d = pr.build({"A": 1000}, {"A": series(wave(200, 0.05))}, [], PROF, "t")
    assert d["status"] == "ok" and d["holdings"][0]["risk_pct"] == 100.0 and d["holdings"][0]["weight_pct"] == 100.0
    assert d["correlation"] is None and d["metrics"]["beta"] is None  # 無大盤資料就不算 Beta


def test_identical_series_correlation_one_and_beta_one():
    s = series(wave(200, 0.05))
    d = pr.build({"A": 1000, "B": 500}, {"A": s, "B": s}, s, PROF, "t")
    assert d["correlation"]["matrix"][0][1] == 1.0
    assert d["metrics"]["beta"] == 1.0
    assert sum(h["risk_pct"] for h in d["holdings"]) == pytest.approx(100, abs=0.05)


def test_risk_contributions_sum_to_one_and_can_be_negative():
    rets = [pr.clean_returns(wave(200, 0.05), False)[0], pr.clean_returns(wave(200, 0.05, math.pi), False)[0],
            pr.clean_returns(wave(200, 0.01, 1.0), False)[0]]
    rc = pr.risk_contributions([0.7, 0.2, 0.1], rets)
    assert sum(rc) == pytest.approx(1.0)
    assert min(rc) < 0  # 與主要持股反向的部位降低整體風險


def test_dividend_drop_only_in_raw_returns():
    """除息日：未還原價格出現跳空下跌，還原後消失。"""
    raw = series([100.0] * 10 + [96.0] * 10)  # 第 11 天除息 4 元，股價其實沒動
    divs = [{"date": raw[10]["date"], "before_price": 100.0, "after_price": 96.0}]
    adj = st.adjust_bars(raw, divs)
    raw_r, _ = pr.clean_returns([b["close"] for b in raw], False)
    adj_r, _ = pr.clean_returns([b["close"] for b in adj], False)
    assert min(raw_r) == pytest.approx(-0.04)
    assert max(abs(x) for x in adj_r) < 1e-9
    assert adj[-1]["close"] == raw[-1]["close"]  # 向後調整：最新一天等於實際收盤


def test_jump_guard_and_min_history_exclusion():
    closes = wave(200, 0.02)
    closes[100:] = [c / 4 for c in closes[100:]]  # 一拆四、未調整
    d = pr.build({"A": 1000, "C": 10}, {"A": series(closes), "C": series(wave(50, 0.02))}, [], PROF, "t")
    assert d["excluded_jumps"] == 1
    assert [e["code"] for e in d["excluded"]] == ["C"] and d["holdings"][0]["code"] == "A"
    assert d["metrics"]["max_drawdown"]["pct"] > -10  # 分割沒有被當成 −75% 的崩跌


def test_value_series_and_market_value_use_latest_close():
    a, b = series(wave(300, 0.03)), series(wave(300, 0.04, 1.0, 50))
    d = pr.build({"A": 2000, "B": 1000}, {"A": a, "B": b}, [], PROF, "t")
    assert d["days"] == pr.WINDOW and len(d["series"]) == pr.WINDOW + 1
    assert d["market_value"] == round(2000 * a[-1]["close"] + 1000 * b[-1]["close"])
    assert d["series"][-1]["value"] == d["market_value"]
    assert d["industries"] == [{"industry": "半導體業", "weight_pct": 100.0}]


def test_empty_and_insufficient():
    assert pr.build({}, {}, [], {}, "t")["status"] == "empty"
    d = pr.build({"A": 1}, {"A": series(wave(30, 0.01))}, [], PROF, "t")
    assert d["status"] == "insufficient" and d["excluded"][0]["code"] == "A"


def test_fetch_failure_has_own_reason():
    d = pr.build({"A": 1000, "B": 10}, {"A": series(wave(200, 0.03))}, [], PROF, "t", failed={"B"})
    assert d["status"] == "ok" and d["excluded"] == [{"code": "B", "name": "乙", "bars": 0, "reason": "資料來源暫時無法取得"}]


def test_beta_tolerates_missing_index_days():
    s = series(wave(300, 0.05))
    idx = [b for i, b in enumerate(s) if i % 50 != 7]  # 大盤缺幾天
    assert pr.build({"A": 1000}, {"A": s}, idx, PROF, "t")["metrics"]["beta"] == 1.0
