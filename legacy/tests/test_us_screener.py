"""
美股選股篩選器單元測試 — Phase 7 Stage 4
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from us_screener import US_SCREENER_POOL, _fetch_ticker_metrics, get_us_screener_data, filter_us_stocks

def test_us_screener_pool_definition():
    """驗證股票池定義"""
    assert isinstance(US_SCREENER_POOL, list)
    assert len(US_SCREENER_POOL) == 50
    assert "AAPL" in US_SCREENER_POOL
    assert "TSM" in US_SCREENER_POOL

@patch("yfinance.Ticker")
def test_fetch_ticker_metrics_success(mock_ticker_class):
    """測試單檔股票指標抓取成功"""
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "currentPrice": 180.0,
        "fiftyTwoWeekHigh": 200.0,
        "dividendYield": 0.015,
        "returnOnEquity": 0.45,
        "trailingPE": 28.5,
        "forwardPE": 26.0,
        "marketCap": 2800000000000
    }
    mock_ticker_class.return_value = mock_ticker
    
    metrics = _fetch_ticker_metrics("AAPL")
    
    assert metrics is not None
    assert metrics["代號"] == "AAPL"
    assert metrics["名稱"] == "Apple Inc."
    assert metrics["行業板塊"] == "Technology"
    assert metrics["收盤"] == 180.0
    assert metrics["52週高點"] == 200.0
    assert metrics["拉回幅度%"] == -10.0  # (180 - 200) / 200 * 100
    assert metrics["股利殖利率%"] == 1.5   # 0.015 * 100
    assert metrics["股東權益報酬率%"] == 45.0 # 0.45 * 100
    assert metrics["本益比"] == 28.5
    assert metrics["預期本益比"] == 26.0
    assert metrics["市值"] == 2800000000000

@patch("us_screener.get_cache")
def test_get_us_screener_data_from_cache(mock_get_cache):
    """測試當快取存在時，直接從快取讀取"""
    mock_df = pd.DataFrame([{"代號": "AAPL", "收盤": 180.0}])
    mock_get_cache.return_value = mock_df
    
    df = get_us_screener_data(force_refresh=False)
    
    assert df.equals(mock_df)
    mock_get_cache.assert_called_once_with("us_screener_dataset")

@patch("us_screener.get_cache")
@patch("us_screener.set_cache")
@patch("us_screener._fetch_ticker_metrics")
def test_get_us_screener_data_force_refresh(mock_fetch, mock_set_cache, mock_get_cache):
    """測試強刷或快取不存在時，呼叫並行下載並更新快取"""
    mock_get_cache.return_value = None
    mock_fetch.side_effect = lambda ticker: {
        "代號": ticker,
        "名稱": ticker,
        "行業板塊": "Tech",
        "細分產業": "Semi",
        "收盤": 100.0,
        "52週高點": 120.0,
        "拉回幅度%": -16.67,
        "本益比": 15.0,
        "預期本益比": 12.0,
        "股利殖利率%": 2.0,
        "股東權益報酬率%": 18.0,
        "市值": 50000000000
    }
    
    df = get_us_screener_data(force_refresh=True)
    
    assert not df.empty
    assert len(df) == 50
    assert mock_set_cache.called
    mock_set_cache.assert_called_once()
    
    # 確保寫入快取的 key 是 us_screener_dataset 且 TTL 是 12小時 (43200秒)
    args, kwargs = mock_set_cache.call_args
    assert args[0] == "us_screener_dataset"
    assert kwargs.get("ttl") == 43200

def test_filter_us_stocks():
    """測試多因子篩選過濾邏輯"""
    # 建立測試 DataFrame
    data = [
        {
            "代號": "AAPL", "名稱": "Apple Inc.", "行業板塊": "Technology", "細分產業": "Consumer Electronics",
            "收盤": 180.0, "52週高點": 200.0, "拉回幅度%": -10.0, "本益比": 28.0, "預期本益比": 26.0,
            "股利殖利率%": 1.5, "股東權益報酬率%": 45.0, "市值": 2800000000000
        },
        {
            "代號": "NVDA", "名稱": "NVIDIA Corp.", "行業板塊": "Technology", "細分產業": "Semiconductors",
            "收盤": 900.0, "52週高點": 1000.0, "拉回幅度%": -10.0, "本益比": 75.0, "預期本益比": 35.0,
            "股利殖利率%": 0.05, "股東權益報酬率%": 55.0, "市值": 2200000000000
        },
        {
            "代號": "JPM", "名稱": "JPMorgan Chase & Co.", "行業板塊": "Financials", "細分產業": "Diversified Banks",
            "收盤": 190.0, "52週高點": 200.0, "拉回幅度%": -5.0, "本益比": 11.5, "預期本益比": 11.0,
            "股利殖利率%": 2.2, "股東權益報酬率%": 12.0, "市值": 550000000000
        },
        {
            "代號": "INTC", "名稱": "Intel Corp.", "行業板塊": "Technology", "細分產業": "Semiconductors",
            "收盤": 30.0, "52週高點": 50.0, "拉回幅度%": -40.0, "本益比": float("nan"), "預期本益比": 24.0,
            "股利殖利率%": 1.6, "股東權益報酬率%": 1.5, "市值": 120000000000
        }
    ]
    df = pd.DataFrame(data)
    
    # 測試 1: 市值篩選
    res1 = filter_us_stocks(df, {"min_mcap": "> 100B"})
    assert len(res1) == 4
    
    res1_high = filter_us_stocks(df, {"min_mcap": "> 100B", "min_roe": 40.0})
    assert len(res1_high) == 2  # AAPL, NVDA
    
    # 測試 2: 本益比篩選
    res2 = filter_us_stocks(df, {"max_pe": 30.0})
    assert len(res2) == 2  # AAPL (28.0), JPM (11.5) (INTC is nan, NVDA is 75)
    
    # 測試 3: 預期本益比篩選
    res3 = filter_us_stocks(df, {"max_forward_pe": 30.0})
    assert len(res3) == 3  # AAPL (26), JPM (11), INTC (24)
    
    # 測試 4: 拉回幅度篩選 (-25% 到 -8%)
    res4 = filter_us_stocks(df, {"pullback_min": -25.0, "pullback_max": -8.0})
    assert len(res4) == 2  # AAPL (-10), NVDA (-10)
    
    # 測試 5: 行業篩選
    res5 = filter_us_stocks(df, {"sectors": ["Financials"]})
    assert len(res5) == 1
    assert res5.iloc[0]["代號"] == "JPM"
    
    # 混合多因子過濾
    res_mix = filter_us_stocks(df, {
        "min_mcap": "> 50B",
        "max_pe": 35.0,
        "min_roe": 10.0,
        "pullback_min": -15.0,
        "pullback_max": 0.0,
        "sectors": ["Technology", "Financials"]
    })
    # AAPL: PE 28 (<=35), ROE 45 (>=10), pullback -10 (in [-15, 0]), sector Tech. Passed!
    # NVDA: PE 75 (>35). Failed!
    # JPM: PE 11.5 (<=35), ROE 12 (>=10), pullback -5 (in [-15, 0]), sector Fin. Passed!
    # INTC: PE nan. Failed!
    assert len(res_mix) == 2
    assert set(res_mix["代號"]) == {"AAPL", "JPM"}
