"""
datasources/router.py 守門測試 — 確保今日/歷史兩條路由規則都選對來源、
欄位契約穩定（見 docs/plans/REDESIGN_PLAN_2026-07.md R4）。
"""

from unittest.mock import patch
from datetime import date

import pandas as pd
import pytest

from datasources import router


def _fake_twse_numeric():
    return pd.DataFrame({
        "Code": ["2330", "2317"],
        "Name": ["台積電", "鴻海"],
        "ForeignInvestmentNetBuySell": [-4155172, 1000000],
        "InvestmentTrustNetBuySell": [729872, -50000],
        "DealerNetBuySell": [468443, 20000],
        "TotalInstitutionalNetBuySell": [-2956857, 970000],
    })


def _fake_finmind_institutional():
    rows = []
    for d, name, buy, sell in [
        ("2026-07-08", "外資", 100, 4255172),
        ("2026-07-08", "投信", 800000, 70128),
        ("2026-07-08", "自營(自行)", 400000, 100000),
        ("2026-07-08", "自營(避險)", 200000, 31557),
    ]:
        rows.append({"日期": d, "法人": name, "買進": buy, "賣出": sell, "買超": buy - sell})
    return pd.DataFrame(rows)


class TestGetInstitutionalRouting:
    def test_no_dates_routes_to_twse(self):
        with patch("datasources.router.query_twse_institutional_numeric", return_value=_fake_twse_numeric()) as m:
            df = router.get_institutional(code="2330")
            m.assert_called_once()
        assert list(df.columns) == ["日期", "代號", "名稱", "外資買賣超", "投信買賣超", "自營商買賣超"]
        assert df.iloc[0]["代號"] == "2330"
        assert df.iloc[0]["外資買賣超"] == -4155172

    def test_today_range_routes_to_twse(self):
        today = date.today().isoformat()
        with patch("datasources.router.query_twse_institutional_numeric", return_value=_fake_twse_numeric()) as m:
            df = router.get_institutional(code="2317", start=today, end=today)
            m.assert_called_once()
        assert df.iloc[0]["代號"] == "2317"

    def test_historical_range_routes_to_finmind(self):
        with patch("datasources.router.query_institutional", return_value=_fake_finmind_institutional()) as m:
            df = router.get_institutional(code="2330", start="2026-07-01", end="2026-07-08")
            m.assert_called_once()
        assert list(df.columns) == ["日期", "代號", "名稱", "外資買賣超", "投信買賣超", "自營商買賣超"]
        assert df.iloc[0]["外資買賣超"] == -4255072
        assert df.iloc[0]["投信買賣超"] == 729872
        assert df.iloc[0]["自營商買賣超"] == 468443

    def test_historical_range_without_code_raises(self):
        with pytest.raises(ValueError):
            router.get_institutional(start="2026-07-01", end="2026-07-08")

    def test_empty_twse_response_returns_empty_with_contract_columns(self):
        with patch("datasources.router.query_twse_institutional_numeric", return_value=pd.DataFrame()):
            df = router.get_institutional(code="2330")
        assert df.empty
        assert list(df.columns) == ["日期", "代號", "名稱", "外資買賣超", "投信買賣超", "自營商買賣超"]
