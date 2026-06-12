"""
Phase K 測試：alert_engine 模組
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd

from alert_engine import check_alerts, check_alerts_intraday, _find_price_col, _find_pct_col


class TestAlertEngine:
    def test_check_alerts_returns_list(self):
        result = check_alerts()
        assert isinstance(result, list)

    def test_check_alerts_intraday_returns_dict(self):
        result = check_alerts_intraday()
        assert isinstance(result, dict)

    @patch("alert_engine.load_alerts")
    def test_empty_alerts_returns_empty_list(self, mock_load):
        mock_load.return_value = []
        result = check_alerts()
        assert result == []

    @patch("alert_engine.load_alerts")
    @patch("alert_engine._load_today_closing")
    def test_disabled_rule_skipped(self, mock_closing, mock_load):
        mock_load.return_value = [
            {"code": "2330", "type": "price_above", "value": 1000, "enabled": False}
        ]
        mock_df = pd.DataFrame({"代號": ["2330"], "收盤": [1100.0]})
        mock_closing.return_value = mock_df
        result = check_alerts()
        assert result == []

    def test_check_alerts_intraday_with_codes(self):
        with patch("alert_engine.load_alerts") as mock_load:
            mock_load.return_value = [
                {"code": "2330", "type": "price_above", "value": 1000, "enabled": True}
            ]
            result = check_alerts_intraday(["2330"])
            assert isinstance(result, dict)
            assert "_alerts" in result


class TestHelperFunctions:
    def test_find_price_col(self):
        df = pd.DataFrame({"代號": ["2330"], "Name": ["台積電"], "收盤": [1100.0]})
        col = _find_price_col(df)
        assert col == "收盤"

    def test_find_pct_col(self):
        df = pd.DataFrame({"代號": ["2330"], "收盤": [1100.0], "漲跌幅%": [2.5]})
        col = _find_pct_col(df)
        assert col == "漲跌幅%"

    def test_find_price_col_fallback(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4],
                           "E": [5], "F": [6], "G": [7], "H": [8], "I": [9]})
        col = _find_price_col(df)
        assert col == "I"

    def test_find_price_col_close(self):
        df = pd.DataFrame({"代號": ["2330"], "close": [1100.0]})
        col = _find_price_col(df)
        assert col == "close"
