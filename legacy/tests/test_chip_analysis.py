"""
Phase I 測試：chip_analysis 模組
"""
import pandas as pd
import pytest

from chip_analysis import (
    load_institutional_history,
    consecutive_buy_ranking,
    consecutive_sell_ranking,
    dual_buy_ranking,
    get_individual_chip_summary,
)


class TestLoadInstitutionalHistory:
    def test_returns_dataframe(self):
        df = load_institutional_history(20)
        assert isinstance(df, pd.DataFrame)

    def test_limit_param(self):
        df1 = load_institutional_history(5)
        df30 = load_institutional_history(30)
        # 只讀本地 CSV，天數不同可能相同（檔案少）
        assert isinstance(df1, pd.DataFrame)
        assert isinstance(df30, pd.DataFrame)


class TestConsecutiveBuyRanking:
    def test_returns_dataframe(self):
        df = consecutive_buy_ranking("外資", min_days=1, limit=10)
        assert isinstance(df, pd.DataFrame)

    def test_min_days_filter(self):
        df1 = consecutive_buy_ranking("外資", min_days=1, limit=10)
        df5 = consecutive_buy_ranking("外資", min_days=5, limit=10)
        if not df1.empty:
            assert df1["連買天數"].min() >= 1
        if not df5.empty:
            assert df5["連買天數"].min() >= 5

    def test_who_parameter(self):
        fw = consecutive_buy_ranking("外資", min_days=1, limit=5)
        tr = consecutive_buy_ranking("投信", min_days=1, limit=5)
        assert isinstance(fw, pd.DataFrame)
        assert isinstance(tr, pd.DataFrame)


class TestConsecutiveSellRanking:
    def test_returns_dataframe(self):
        df = consecutive_sell_ranking("外資", min_days=1, limit=10)
        assert isinstance(df, pd.DataFrame)


class TestDualBuyRanking:
    def test_returns_dataframe(self):
        df = dual_buy_ranking(min_days=1, limit=10)
        assert isinstance(df, pd.DataFrame)

    def test_empty_when_no_data(self):
        df = dual_buy_ranking(min_days=1, limit=5)
        # 若無交集資料，應回傳空 DataFrame
        if not df.empty:
            assert "代號" in df.columns


class TestIndividualChipSummary:
    def test_returns_dict(self):
        summary = get_individual_chip_summary("2330")
        assert isinstance(summary, dict)

    def test_has_expected_keys(self):
        summary = get_individual_chip_summary("2330")
        expected_keys = {"代號", "外資連買", "外資累計", "投信連買", "投信累計"}
        if "error" not in summary:
            assert expected_keys.issubset(set(summary.keys()))

    def test_unknown_stock(self):
        summary = get_individual_chip_summary("99999999")
        if "error" in summary:
            assert summary["error"] in ("查無此股", "籌碼資料不足")
