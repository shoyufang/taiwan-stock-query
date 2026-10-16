import sys
from unittest.mock import patch, MagicMock, Mock
import pandas as pd
from datetime import datetime, date
import pytest

# 強制覆寫 mock shioaji 模組以防本地未安裝時單元測試報錯
mock_sj = MagicMock()
mock_sj.constant = MagicMock()
mock_sj.constant.KBarTimeResolution = MagicMock()
mock_sj.constant.KBarTimeResolution.Min1 = "Min1"
mock_sj.constant.KBarTimeResolution.Min5 = "Min5"
mock_sj.constant.KBarTimeResolution.Min15 = "Min15"
mock_sj.constant.KBarTimeResolution.Min30 = "Min30"
mock_sj.constant.KBarTimeResolution.Min60 = "Min60"
mock_sj.constant.KBarTimeResolution.Day = "Day"

mock_sj.constant.TicksQueryType = MagicMock()
mock_sj.constant.TicksQueryType.AllDay = "AllDay"
mock_sj.constant.TicksQueryType.RangeTime = "RangeTime"
mock_sj.constant.TicksQueryType.LastCount = "LastCount"

sys.modules["shioaji"] = mock_sj
sys.modules["shioaji.constant"] = mock_sj.constant

# 確保可導入 modules
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sinopac_query as sq
import query_wrapper as qw

@pytest.mark.unit
class TestShioajiMarketQuery:
    """測試 Shioaji 行情與歷史資料查詢功能"""

    @patch("sinopac_query.HAS_SHIOAJI", False)
    def test_query_snapshot_no_shioaji(self):
        """測試無 shioaji 時快照查詢優雅提示"""
        res = sq.query_shioaji_snapshot(["2330"])
        assert isinstance(res, pd.DataFrame)
        assert "說明" in res.columns
        assert "環境中未安裝 Shioaji 庫" in res.iloc[0]["說明"]

    @patch("sinopac_query.HAS_SHIOAJI", False)
    def test_query_kbars_no_shioaji(self):
        """測試無 shioaji 時分K線查詢優雅提示"""
        res = sq.query_shioaji_kbars("2330", "2026-05-01")
        assert isinstance(res, pd.DataFrame)
        assert "說明" in res.columns
        assert "環境中未安裝 Shioaji 庫" in res.iloc[0]["說明"]

    @patch("sinopac_query.HAS_SHIOAJI", False)
    def test_query_contract_no_shioaji(self):
        """測試無 shioaji 時合約查詢優雅提示"""
        res = sq.query_shioaji_contract_info("2330")
        assert isinstance(res, pd.DataFrame)
        assert "說明" in res.columns
        assert "環境中未安裝 Shioaji 庫" in res.iloc[0]["說明"]

    @patch("sinopac_query.HAS_SHIOAJI", False)
    def test_analyze_big_orders_no_shioaji(self):
        """測試無 shioaji 時大單分析優雅提示"""
        res = sq.analyze_shioaji_big_orders("2330", "2026-05-23")
        assert isinstance(res, dict)
        assert "summary" in res
        assert "detail" in res
        assert "說明" in res["detail"].columns
        assert "環境中未安裝 Shioaji 庫" in res["detail"].iloc[0]["說明"]

    @patch("sinopac_query.HAS_SHIOAJI", True)
    @patch("sinopac_query.login")
    def test_query_contract_info_valid(self, mock_login):
        """測試有 Shioaji 時合約查詢成功解析"""
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_contract.code = "2330"
        mock_contract.name = "台積電"
        mock_contract.exchange = "TSE"
        mock_contract.category = "半導體業"
        mock_contract.margin = True
        mock_contract.short_selling = True
        mock_contract.margin_rate = 0.6
        mock_contract.short_selling_rate = 0.9
        mock_contract.day_trade = "Yes"
        mock_contract.reference = 650.0
        mock_contract.limit_up = 715.0
        mock_contract.limit_down = 585.0
        
        mock_api.Contracts.Stocks = {"2330": mock_contract}
        mock_login.return_value = mock_api
        
        res = sq.query_shioaji_contract_info("2330")
        assert isinstance(res, pd.DataFrame)
        assert "屬性" in res.columns
        assert "官方設定值" in res.columns
        
        c_dict = dict(zip(res["屬性"], res["官方設定值"]))
        assert c_dict["股票代號"] == "2330"
        assert c_dict["股票名稱"] == "台積電"
        assert c_dict["交易所"] == "TSE"
        assert c_dict["產業類別"] == "半導體業"
        assert c_dict["現股當沖/資券互抵"] == "可現股當沖 (資券互抵)"

    @patch("sinopac_query.HAS_SHIOAJI", True)
    @patch("sinopac_query.login")
    def test_query_snapshot_valid(self, mock_login):
        """測試有 Shioaji 時即時快照查詢成功解析"""
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_contract.name = "台積電"
        mock_api.Contracts.Stocks = {"2330": mock_contract}
        
        mock_snapshot = MagicMock()
        mock_snapshot.code = "2330"
        mock_snapshot.open = 645.0
        mock_snapshot.high = 652.0
        mock_snapshot.low = 644.0
        mock_snapshot.close = 650.0
        mock_snapshot.yesterday_close = 643.0
        mock_snapshot.change = 7.0
        mock_snapshot.change_rate = 0.0108
        mock_snapshot.volume = 1500
        mock_snapshot.total_volume = 45000
        mock_snapshot.buy_price = [649.0, 648.0, 647.0, 646.0, 645.0]
        mock_snapshot.buy_volume = [10, 20, 30, 40, 50]
        mock_snapshot.ask_price = [651.0, 652.0, 653.0, 654.0, 655.0]
        mock_snapshot.ask_volume = [15, 25, 35, 45, 55]
        
        mock_api.snapshots.return_value = [mock_snapshot]
        mock_login.return_value = mock_api
        
        res = sq.query_shioaji_snapshot(["2330"])
        assert isinstance(res, pd.DataFrame)
        assert len(res) == 1
        assert res.iloc[0]["代號"] == "2330"
        assert res.iloc[0]["收盤"] == 650.0
        assert res.iloc[0]["名稱"] == "台積電"
        assert res.iloc[0]["委買價"] == [649.0, 648.0, 647.0, 646.0, 645.0]

    @patch("sinopac_query.HAS_SHIOAJI", True)
    @patch("sinopac_query.login")
    def test_query_kbars_valid(self, mock_login):
        """測試有 Shioaji 時分K線查詢"""
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_api.Contracts.Stocks = {"2330": mock_contract}
        
        mock_kbars = MagicMock()
        mock_kbars.close = [646.0, 647.0]
        
        # 模擬 dict behaviors (例如 {**kbars} / keys() 等)
        mock_data = {
            "ts": ["2026-05-23 09:00:00", "2026-05-23 09:01:00"],
            "open": [645.0, 646.0],
            "high": [647.0, 648.0],
            "low": [644.0, 645.0],
            "close": [646.0, 647.0],
            "volume": [100, 200]
        }
        
        mock_kbars.keys.return_value = mock_data.keys()
        mock_kbars.__getitem__.side_effect = lambda x: mock_data[x]
        
        mock_api.kbars.return_value = mock_kbars
        mock_login.return_value = mock_api
        
        res = sq.query_shioaji_kbars("2330", "2026-05-23", resolution="5min")
        assert isinstance(res, pd.DataFrame)
        assert len(res) == 2
        assert "開盤" in res.columns
        assert "最高" in res.columns
        assert res.iloc[0]["收盤"] == 646.0

    @patch("sinopac_query.HAS_SHIOAJI", True)
    @patch("sinopac_query.login")
    def test_analyze_big_orders_valid(self, mock_login):
        """測試有 Shioaji 時大單分析"""
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_api.Contracts.Stocks = {"2330": mock_contract}
        
        mock_ticks = MagicMock()
        mock_ticks.close = [650.0, 651.0]
        
        mock_data = {
            "ts": ["2026-05-23 09:05:00", "2026-05-23 09:06:00"],
            "close": [650.0, 651.0],
            "volume": [60, 2], # 第二筆2張，金額130萬，不是大單
            "tick_type": [1, 2] # 買進，賣出
        }
        mock_ticks.keys.return_value = mock_data.keys()
        mock_ticks.__getitem__.side_effect = lambda x: mock_data[x]
        
        mock_api.ticks.return_value = mock_ticks
        mock_login.return_value = mock_api
        
        res = sq.analyze_shioaji_big_orders("2330", "2026-05-23", threshold_volume=50)
        assert isinstance(res, dict)
        assert "summary" in res
        assert "detail" in res
        
        sum_df = res["summary"]
        detail_df = res["detail"]
        
        assert not sum_df.empty
        assert len(detail_df) == 1 # 只有那一筆大單
        assert detail_df.iloc[0]["成交張數"] == 60
        assert "🟢 主動賣出" not in detail_df.iloc[0]["買賣方向"]
        assert "🔴 主動買入" in detail_df.iloc[0]["買賣方向"]


@pytest.mark.unit
class TestQueryWrapperShioaji:
    """測試 query_wrapper 中的 Shioaji 包裝函數與快取機制"""

    @patch("caching.get_cache", return_value=None)
    @patch("caching.set_cache")
    @patch("query_wrapper.sq.query_shioaji_snapshot")
    def test_wrapper_snapshot_cache_miss(self, mock_query, mock_set, mock_get):
        """測試快照包裝函數 - Cache Miss"""
        mock_query.return_value = pd.DataFrame({"代號": ["2330"], "收盤": [650.0]})
        
        res = qw.query_shioaji_snapshot(["2330"])
        assert len(res) == 1
        assert res.iloc[0]["收盤"] == 650.0
        mock_set.assert_called_once()

    @patch("caching.get_cache")
    @patch("query_wrapper.sq.query_shioaji_snapshot")
    def test_wrapper_snapshot_cache_hit(self, mock_query, mock_get):
        """測試快照包裝函數 - Cache Hit"""
        if hasattr(qw._cached_shioaji_snapshot, "clear"):
            qw._cached_shioaji_snapshot.clear()
        mock_get.return_value = pd.DataFrame({"代號": ["2330"], "收盤": [655.0]})
        
        res = qw.query_shioaji_snapshot(["2330"])
        assert len(res) == 1
        assert res.iloc[0]["收盤"] == 655.0
        mock_query.assert_not_called()
