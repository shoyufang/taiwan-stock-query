"""
台股日曆與除息引擎單元測試 — Phase 7 Stage 5 (台股擴充)
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from tw_calendar import _fetch_single_tw_calendar_consensus, get_tw_calendar_consensus_data

@patch("yfinance.Ticker")
def test_fetch_single_tw_calendar_consensus_success(mock_ticker_class):
    """測試單檔台股的財報日、除息日與營收/EPS指標抓取成功"""
    import datetime
    
    mock_ticker = MagicMock()
    mock_ticker.calendar = {
        "Dividend Date": datetime.date(2026, 6, 15),
        "Ex-Dividend Date": datetime.date(2026, 6, 11),
        "Earnings Date": [datetime.date(2026, 7, 16)],
        "Earnings Average": 23.75,
        "Revenue Average": 1260000000000
    }
    mock_ticker.info = {
        "shortName": "Taiwan Semiconductor Manufacturing Co Ltd",
        "currentPrice": 900.0
    }
    mock_ticker_class.return_value = mock_ticker
    
    data = _fetch_single_tw_calendar_consensus("2330")
    
    assert data is not None
    assert data["代號"] == "2330"
    assert "台積電" in data["名稱"] or data["名稱"] == "2330"
    assert data["最新價"] == 900.0
    assert data["財報公佈日"] == "2026-07-16"
    assert data["除息日"] == "2026-06-11"
    assert data["預估下季EPS"] == 23.75
    assert data["預估營收(B元)"] == 1260.0  # 1260000000000 / 1e9

@patch("calendar_engine.get_cache")
def test_get_tw_calendar_consensus_data_from_cache(mock_get_cache):
    """測試當快取存在時，直接讀取快取"""
    mock_df = pd.DataFrame([{"代號": "2330", "最新價": 900.0}])
    mock_get_cache.return_value = mock_df
    
    df = get_tw_calendar_consensus_data(force_refresh=False)
    
    assert df.equals(mock_df)
    mock_get_cache.assert_called_once_with("tw_calendar_consensus_dataset")

@patch("calendar_engine.get_cache")
@patch("calendar_engine.set_cache")
@patch("tw_calendar._fetch_single_tw_calendar_consensus")
def test_get_tw_calendar_consensus_data_force_refresh(mock_fetch, mock_set_cache, mock_get_cache):
    """測試強刷或無快取時，執行並行下載並寫入快取"""
    mock_get_cache.return_value = None
    mock_fetch.side_effect = lambda code: {
        "代號": code,
        "名稱": code,
        "最新價": 100.0,
        "財報公佈日": "2026-07-16",
        "除息日": "2026-06-11",
        "預估下季EPS": 1.5,
        "預估營收(B元)": 50.0
    }
    
    df = get_tw_calendar_consensus_data(force_refresh=True)
    
    assert not df.empty
    assert len(df) == 50
    assert mock_set_cache.called
    mock_set_cache.assert_called_once()
    
    # 確保寫入快取的 key 是 tw_calendar_consensus_dataset 且 TTL 是 24小時 (86400秒)
    args, kwargs = mock_set_cache.call_args
    assert args[0] == "tw_calendar_consensus_dataset"
    assert kwargs.get("ttl") == 86400
