import sys
import os
from unittest.mock import MagicMock, patch

# 確保專案根目錄在 sys.path 最前面
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root in sys.path:
    sys.path.remove(_project_root)
sys.path.insert(0, _project_root)

# 強制載入本地 utils.py 並覆蓋 shioaji 搶註冊的 sys.modules['utils']
import importlib.util
_local_utils_path = os.path.join(_project_root, 'utils.py')
_spec = importlib.util.spec_from_file_location('utils', _local_utils_path)
_local_utils = importlib.util.module_from_spec(_spec)
sys.modules['utils'] = _local_utils
_spec.loader.exec_module(_local_utils)

# 自訂強大的 MockStreamlit 類別，根據呼叫參數動態回傳正確數量的 mock 物件與真實輸入值，防範解包與 JSON 序列化錯誤
class MockStreamlit(MagicMock):
    def columns(self, spec, *args, **kwargs):
        if isinstance(spec, int):
            return [MagicMock() for _ in range(spec)]
        elif isinstance(spec, (list, tuple)):
            return [MagicMock() for _ in range(len(spec))]
        return [MagicMock(), MagicMock()]
        
    def tabs(self, spec, *args, **kwargs):
        if isinstance(spec, int):
            return [MagicMock() for _ in range(spec)]
        elif isinstance(spec, (list, tuple)):
            return [MagicMock() for _ in range(len(spec))]
        return [MagicMock(), MagicMock()]

    def text_input(self, label, value="", *args, **kwargs):
        return value
        
    def number_input(self, label, value=0, *args, **kwargs):
        return value
        
    def checkbox(self, label, value=False, *args, **kwargs):
        return value
        
    def selectbox(self, label, options=None, *args, **kwargs):
        if options:
            return options[0]
        return ""
        
    def multiselect(self, label, options=None, default=None, *args, **kwargs):
        return default if default is not None else []

mock_st = MockStreamlit()

# 模擬 session_state 為字典格式，並給予一個真實的 json serializable config 字典
class MockSessionState(dict):
    def __getattr__(self, item):
        return self.get(item, MagicMock())
    def __setattr__(self, key, value):
        self[key] = value

session_state = MockSessionState()
session_state.config = {
    "api_key": "test_key",
    "secret_key": "test_secret",
    "finmind_token": "test_token",
    "export_format": "csv",
    "simulation_mode": True
}
session_state.bookmarks = []
mock_st.session_state = session_state

# 將 mock 註冊到 sys.modules 中（僅供本檔匯入期間使用，匯入完畢後立即還原，
# 避免污染 sys.modules 導致同一 pytest process 內後續收集的其他測試檔案
# 拿到假的 streamlit 模組，見 2026-07-07 審查發現）
_real_streamlit = sys.modules.get('streamlit')
sys.modules['streamlit'] = mock_st

import pytest
import streamlit as st
import pandas as pd
from datetime import date

# 導入待測函數（app.py 匯入時期需要 mock streamlit，匯入完成後其內部的
# streamlit 參照已綁定完成，之後還原 sys.modules 不影響 app 或本檔案）
from app import execute_query_by_params

# 還原 sys.modules，讓後續收集的其他測試檔案拿到真正的 streamlit
if _real_streamlit is not None:
    sys.modules['streamlit'] = _real_streamlit
else:
    sys.modules.pop('streamlit', None)

@pytest.mark.unit
class TestDashboardPinning:
    """測試儀表板常用捷徑與釘選查詢的原位執行與分流功能"""

    @patch('dispatch.qw.query_daily_kbar')
    @patch('technical_analysis.plot_kbar_with_indicators')
    def test_execute_technical_analysis(self, mock_plot, mock_kbar):
        """測試技術分析 K 線圖捷徑執行"""
        # 模擬返回的 K 線 dataframe
        mock_df = pd.DataFrame({
            "date": ["2026-05-22"],
            "open": [100.0],
            "high": [105.0],
            "low": [99.0],
            "close": [104.0],
            "volume": [1000]
        })
        mock_kbar.return_value = mock_df
        
        mock_fig = MagicMock()
        mock_plot.return_value = mock_fig
        
        params = {
            "type": "technical_analysis",
            "code": "2330",
            "start": "2026-05-01",
            "end": "2026-05-22",
            "indicators": ["MA5", "MA20"]
        }
        
        with patch.object(st, 'plotly_chart') as mock_plotly_chart:
            execute_query_by_params("技術分析", params)
            mock_plotly_chart.assert_called_once_with(mock_fig, use_container_width=True)
        
        mock_kbar.assert_called_once_with("2330", date(2026, 5, 1), date(2026, 5, 22))
        mock_plot.assert_called_once()

    @patch('tabs.taistock._taistock_dispatch')
    @patch('tabs._shared._render_batch_results')
    def test_execute_taistock_batch(self, mock_render, mock_dispatch):
        """測試台股市場批次查詢捷徑執行"""
        mock_dispatch.return_value = pd.DataFrame({"test": [1]})
        
        params = {
            "type": "taistock_batch",
            "selected": ["個股即時快照"],
            "code": "2330",
            "codes": ["2330"],
            "start_date": "2026-05-01",
            "end_date": "2026-05-22",
            "query_date": "2026-05-22",
            "count": 10
        }
        
        execute_query_by_params("台股市場", params)
        
        mock_dispatch.assert_called_once_with(
            "個股即時快照", "2330", ["2330"], date(2026, 5, 1), date(2026, 5, 22), date(2026, 5, 22), 10
        )
        mock_render.assert_called_once_with("db_batch_results")
        assert st.session_state["db_batch_results"] == [("個股即時快照", mock_dispatch.return_value)]

    @patch('tabs.twse._twse_dispatch')
    @patch('tabs._shared._render_batch_results')
    def test_execute_twse_batch(self, mock_render, mock_dispatch):
        """測試 TWSE OpenAPI 批次查詢捷徑執行"""
        mock_dispatch.return_value = (pd.DataFrame({"test": [1]}), None)
        
        params = {
            "type": "twse_batch",
            "selected": ["每日收盤行情"],
            "code": "2330"
        }
        
        execute_query_by_params("TWSE", params)
        
        mock_dispatch.assert_called_once_with("每日收盤行情", "2330")
        mock_render.assert_called_once_with("db_batch_results")

    @patch('tabs.finmind._finmind_dispatch')
    @patch('tabs._shared._render_batch_results')
    def test_execute_finmind_batch(self, mock_render, mock_dispatch):
        """測試 FinMind 批次查詢捷徑執行"""
        mock_dispatch.return_value = pd.DataFrame({"test": [1]})
        
        params = {
            "type": "finmind_batch",
            "selected": ["三大法人買賣超"],
            "code": "2330",
            "start_date": "2026-05-01",
            "end_date": "2026-05-22"
        }
        
        execute_query_by_params("FinMind", params)
        
        mock_dispatch.assert_called_once_with("三大法人買賣超", "2330", date(2026, 5, 1), date(2026, 5, 22))
        mock_render.assert_called_once()
        assert st.session_state["db_batch_results"] == ([("三大法人買賣超", mock_dispatch.return_value)], "2330")

    @patch('tabs.futures_forex._futures_forex_dispatch')
    @patch('tabs._shared._render_batch_results')
    def test_execute_futures_forex_batch(self, mock_render, mock_dispatch):
        """測試期貨與外匯批次查詢捷徑執行"""
        mock_dispatch.return_value = pd.DataFrame({"test": [1]})
        
        params = {
            "type": "futures_forex_batch",
            "selected": ["台股期指日K"],
            "futures_code": "TX",
            "currency": "USD/TWD",
            "start_date": "2026-05-01",
            "end_date": "2026-05-22"
        }
        
        execute_query_by_params("期貨/匯率", params)
        
        mock_dispatch.assert_called_once_with(
            "台股期指日K", "TX", "USD/TWD", date(2026, 5, 1), date(2026, 5, 22)
        )
        mock_render.assert_called_once_with("db_batch_results")

    @patch('us_screener.get_us_screener_data')
    @patch('us_screener.filter_us_stocks')
    @patch('tabs.screener_tab._us_screener_result_block')
    def test_execute_screener_us(self, mock_result_block, mock_filter, mock_get_data):
        """測試美股多因子選股捷徑執行"""
        mock_df_all = pd.DataFrame({"ticker": ["AAPL", "MSFT"]})
        mock_get_data.return_value = mock_df_all
        
        mock_df_filtered = pd.DataFrame({"ticker": ["AAPL"]})
        mock_filter.return_value = mock_df_filtered
        
        filters = {"pe_min": 10}
        params = {
            "type": "screener_us",
            "filters": filters
        }
        
        execute_query_by_params("選股", params)
        
        mock_get_data.assert_called_once_with(force_refresh=False)
        mock_filter.assert_called_once_with(mock_df_all, filters)
        mock_result_block.assert_called_once_with(mock_df_filtered, "美股多因子選股")

    @patch('tabs.us_stocks._us_stock_dispatch')
    @patch('tabs._shared._render_batch_results')
    def test_execute_us_stock_batch(self, mock_render, mock_dispatch):
        """測試美股批次查詢捷徑執行"""
        mock_dispatch.return_value = pd.DataFrame({"test": [1]})
        
        params = {
            "type": "us_stock_batch",
            "selected": ["個股基本面"],
            "ticker": "AAPL",
            "start_date": "2026-05-01",
            "end_date": "2026-05-22"
        }
        
        execute_query_by_params("🇺🇸 美股專區", params)
        
        mock_dispatch.assert_called_once_with("個股基本面", "AAPL", date(2026, 5, 1), date(2026, 5, 22))
        mock_render.assert_called_once_with("db_batch_results")

    @patch('us_calendar.get_us_calendar_consensus_data')
    def test_execute_us_calendar_consensus(self, mock_get_data):
        """測試美股日曆與共識捷徑執行"""
        mock_df = pd.DataFrame({
            "代號": ["AAPL"],
            "名稱": ["Apple Inc."],
            "行業板塊": ["Technology"],
            "最新價": [180.0],
            "共識評等": ["強力買入 🟢🟢"],
            "平均目標價": [200.0],
            "潛在漲幅%": [11.1],
            "分析師人數": [35]
        })
        mock_get_data.return_value = mock_df
        
        params = {
            "type": "us_calendar_consensus"
        }
        
        with patch.object(st, 'dataframe') as mock_st_dataframe:
            execute_query_by_params("📅 美股日曆 & 共識", params)
            mock_st_dataframe.assert_called_once()
            
        mock_get_data.assert_called_once_with(force_refresh=False)
