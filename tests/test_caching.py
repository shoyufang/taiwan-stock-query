import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date, datetime
from caching import cached_query

class TestCachedQueryDecorator(unittest.TestCase):
    
    def setUp(self):
        # 建立一個測試函數
        self.call_count = 0
        
        # 透過 patch 將 HAS_STREAMLIT 設為 False，防止單元測試中 Streamlit 快取機制干擾
        with patch("caching.HAS_STREAMLIT", False):
            @cached_query(ttl=60, sqlite_ttl=120, name="test_func")
            def mock_api_func(code: str, query_date: date) -> pd.DataFrame:
                self.call_count += 1
                if code == "empty":
                    return pd.DataFrame()
                return pd.DataFrame({"code": [code], "value": [100]})
                
            self.test_func = mock_api_func

    @patch("caching.get_cache")
    @patch("caching.set_cache")
    @patch("query_wrapper._check_cache_hit", return_value=False)
    @patch("query_wrapper._record_cache_hit")
    def test_cache_miss_and_set(self, mock_record_hit, mock_check_hit, mock_set_cache, mock_get_cache):
        # 測試：SQLite 沒命中，應呼叫原始函數並寫回 SQLite
        mock_get_cache.return_value = None
        
        res = self.test_func("2330", date(2026, 6, 10))
        
        self.assertEqual(self.call_count, 1)
        self.assertFalse(res.empty)
        # 驗證 set_cache 被呼叫
        mock_set_cache.assert_called_once()
        # 驗證 _record_cache_hit 被呼叫
        mock_record_hit.assert_called_once()

    @patch("caching.get_cache")
    @patch("caching.set_cache")
    @patch("query_wrapper._check_cache_hit", return_value=False)
    @patch("query_wrapper._record_cache_hit")
    def test_cache_hit_no_api_call(self, mock_record_hit, mock_check_hit, mock_set_cache, mock_get_cache):
        # 測試：SQLite 命中，不應呼叫原始函數
        mock_df = pd.DataFrame({"code": ["2330"], "value": [100]})
        mock_get_cache.return_value = mock_df
        
        res = self.test_func("2330", date(2026, 6, 10))
        
        self.assertEqual(self.call_count, 0)
        self.assertEqual(res.iloc[0]["code"], "2330")
        mock_set_cache.assert_not_called()

    @patch("caching.get_cache")
    @patch("caching.set_cache")
    @patch("query_wrapper._check_cache_hit", return_value=False)
    @patch("query_wrapper._record_cache_hit")
    def test_empty_df_not_cached(self, mock_record_hit, mock_check_hit, mock_set_cache, mock_get_cache):
        # 測試：原始函數返回空 DataFrame 時，不寫入 SQLite
        mock_get_cache.return_value = None
        
        res = self.test_func("empty", date(2026, 6, 10))
        
        self.assertEqual(self.call_count, 1)
        self.assertTrue(res.empty)
        mock_set_cache.assert_not_called()

    @patch("caching.get_cache")
    @patch("caching.set_cache")
    @patch("query_wrapper._check_cache_hit", return_value=False)
    @patch("query_wrapper._record_cache_hit")
    def test_sqlite_exception_fallback(self, mock_record_hit, mock_check_hit, mock_set_cache, mock_get_cache):
        # 測試：SQLite 查詢出錯時，應有 fallback 能繼續呼叫 API 且不崩潰
        mock_get_cache.side_effect = Exception("SQLite connection failed")
        
        res = self.test_func("2330", date(2026, 6, 10))
        
        self.assertEqual(self.call_count, 1)
        self.assertEqual(res.iloc[0]["code"], "2330")
