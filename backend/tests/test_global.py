from datetime import date

from app.services import global_mkt as gm


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
