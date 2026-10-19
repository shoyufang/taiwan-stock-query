import json
from datetime import date
from pathlib import Path

from app.services import global_mkt as gm
from app.services import us_stocks as us

FIX = Path(__file__).parent / "fixtures"


def bars(*closes):
    return [{"date": date(2026, 10, 10 + i), "close": c} for i, c in enumerate(closes)]


def test_summarize():
    s = gm.summarize("^GSPC", "標普 500", bars(7718.94, 7744.06))
    assert s["date"] == "2026-10-11" and s["change_pct"] == round((7744.06 - 7718.94) / 7718.94 * 100, 2)
    assert gm.summarize("X", "x", bars(1.0)) is None


def test_adr_ratios_verified_by_real_prices():
    """2026-10-15/16 實價：ASX 必須用 1:2，台積電與聯電 1:5，溢價才落在合理範圍。"""
    fx = {"close": 32.33, "date": "2026-10-16"}
    tsm = gm.adr_premium({"symbol": "TSM", "close": 422.25, "date": "2026-10-15"},
                         {"symbol": "2330.TW", "close": 2420.0, "date": "2026-10-16"}, fx, 5)
    asx = gm.adr_premium({"symbol": "ASX", "close": 41.89, "date": "2026-10-15"},
                         {"symbol": "3711.TW", "close": 671.0, "date": "2026-10-16"}, fx, 2)
    assert tsm["premium_pct"] == 12.82
    assert asx["premium_pct"] == 0.92
    assert dict((a, r) for a, _, _, r in gm.ADRS) == {"TSM": 5, "UMC": 5, "ASX": 2}


def test_us_stocks_screener_and_earnings():
    assert len(us.US_POOL) == 50
    raw = json.loads((FIX / "yahoo_us_quotes.json").read_text(encoding="utf-8"))["quoteResponse"]["result"]
    res = us.build(raw, date(2026, 10, 17), "2026-10-17T06:00:00+08:00")
    assert len(res["rows"]) == 5
    # 依市值由大到小排序
    mcaps = [r["market_cap_b"] for r in res["rows"]]
    assert mcaps == sorted(mcaps, reverse=True)
    aapl = next(r for r in res["rows"] if r["symbol"] == "AAPL")
    assert aapl["name"] == "蘋果" and aapl["sector"] == "科技巨頭"
    assert aapl["pe"] > 0 and aapl["forward_pe"] > 0
    assert aapl["pullback_pct"] <= 0
    assert aapl["rating_score"] == 2.2 and aapl["rating_label"] == "買進"
    assert aapl["earnings_date"] is not None
    # 近期財報依日期由近到遠排序
    edates = [r["earnings_date"] for r in res["upcoming_earnings"]]
    assert len(edates) >= 3 and edates == sorted(edates)



def _summary(name):
    return json.loads((FIX / f"yahoo_quoteSummary_{name}.json").read_text(encoding="utf-8"))


def test_global_fundamentals_us_stock():
    """AAPL 2026-10-20 實抓：比率轉百分比、近四季依季別排序、EPS 對上同一季。"""
    from app.services import global_fundamentals as gf

    d = gf.build("AAPL", _summary("AAPL"), "2026-10-20T04:00:00+08:00")
    assert d["has_data"] and d["currency"] == "USD" and d["financial_currency"] == "USD"
    assert d["valuation"]["trailing_pe"] == 39.33 and d["valuation"]["eps_ttm"] == 8.72
    assert d["dividend"]["yield_pct"] == 0.31 and d["dividend"]["rate"] == 1.08
    assert d["profitability"]["gross_margin"] == 48.65 and d["profitability"]["revenue_growth"] == 16.4
    assert d["analyst"]["rating_label"] == "買進" and d["analyst"]["target_mean"] == 329.38
    q = d["quarters"]
    assert [x["quarter"] for x in q] == ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    assert q[-1]["revenue"] == 109417000000 and q[-1]["eps"] == 2.02 and q[-1]["eps_estimate"] == 1.892
    assert q[-1]["net_margin"] == round(29789000000 / 109417000000 * 100, 2)
    assert d["profile"]["sector"] == "Technology"


def test_global_fundamentals_hk_stock_and_index():
    from app.services import global_fundamentals as gf

    hk = gf.build("0700.HK", _summary("0700HK"), "t")
    assert hk["has_data"] and hk["currency"] == "HKD" and hk["analyst"]["rating_label"] == "強力買進"
    assert hk["quarters"][-1]["quarter"] == "2026Q1" and hk["quarters"][-1]["eps"] == 7.364
    idx = gf.build("^GSPC", _summary("GSPC"), "t")
    assert idx["has_data"] is False and idx["quarters"] == [] and idx["valuation"]["trailing_pe"] is None
