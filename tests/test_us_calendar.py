"""
美股日曆與共識引擎單元測試 — Phase 7 Stage 5
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from us_calendar import _fetch_single_calendar_consensus, get_us_calendar_consensus_data

@patch("yfinance.Ticker")
def test_fetch_single_calendar_consensus_success(mock_ticker_class):
    """測試單檔股票的財報與分析師共識指標抓取成功"""
    import datetime
    
    mock_ticker = MagicMock()
    mock_ticker.calendar = {
        "Dividend Date": datetime.date(2026, 5, 14),
        "Ex-Dividend Date": datetime.date(2026, 5, 11),
        "Earnings Date": [datetime.date(2026, 7, 31)],
        "Earnings Average": 1.95,
        "Revenue Average": 110000000000
    }
    mock_ticker.info = {
        "shortName": "Apple Inc.",
        "sector": "Technology",
        "currentPrice": 180.0,
        "targetMeanPrice": 200.0,
        "targetHighPrice": 220.0,
        "targetLowPrice": 160.0,
        "recommendationKey": "buy",
        "numberOfAnalystOpinions": 40
    }
    mock_ticker_class.return_value = mock_ticker
    
    data = _fetch_single_calendar_consensus("AAPL")
    
    assert data is not None
    assert data["代號"] == "AAPL"
    assert data["名稱"] == "Apple Inc."
    assert data["行業板塊"] == "Technology"
    assert data["最新價"] == 180.0
    assert data["平均目標價"] == 200.0
    assert data["潛在漲幅%"] == 11.11  # ((200 - 180) / 180) * 100
    assert "買入" in data["共識評等"]
    assert data["分析師人數"] == 40
    assert data["財報公佈日"] == "2026-07-31"
    assert data["預估下季EPS"] == 1.95
    assert data["預估營收(B)"] == 110.0  # 110000000000 / 1e9

@patch("us_calendar.get_cache")
def test_get_us_calendar_consensus_data_from_cache(mock_get_cache):
    """測試當快取存在時，直接讀取快取"""
    mock_df = pd.DataFrame([{"代號": "AAPL", "最新價": 180.0}])
    mock_get_cache.return_value = mock_df
    
    df = get_us_calendar_consensus_data(force_refresh=False)
    
    assert df.equals(mock_df)
    mock_get_cache.assert_called_once_with("us_calendar_consensus_dataset")

@patch("us_calendar.get_cache")
@patch("us_calendar.set_cache")
@patch("us_calendar._fetch_single_calendar_consensus")
def test_get_us_calendar_consensus_data_force_refresh(mock_fetch, mock_set_cache, mock_get_cache):
    """測試強刷或無快取時，執行並行下載並寫入快取"""
    mock_get_cache.return_value = None
    mock_fetch.side_effect = lambda ticker: {
        "代號": ticker,
        "名稱": ticker,
        "行業板塊": "Tech",
        "最新價": 100.0,
        "平均目標價": 120.0,
        "潛在漲幅%": 20.0,
        "共識評等": "買入 🟢",
        "分析師人數": 10,
        "財報公佈日": "2026-07-30",
        "預估下季EPS": 1.5,
        "預估營收(B)": 50.0
    }
    
    df = get_us_calendar_consensus_data(force_refresh=True)
    
    assert not df.empty
    assert len(df) == 50
    assert mock_set_cache.called
    mock_set_cache.assert_called_once()
    
    # 確保寫入快取的 key 是 us_calendar_consensus_dataset 且 TTL 是 24小時 (86400秒)
    args, kwargs = mock_set_cache.call_args
    assert args[0] == "us_calendar_consensus_dataset"
    assert kwargs.get("ttl") == 86400
