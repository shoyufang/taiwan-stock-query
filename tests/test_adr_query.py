import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from adr_query import get_usd_twd_rate, get_adr_snapshots, ADR_PAIRS

def test_get_usd_twd_rate_live():
    """驗證線上獲取匯率成功且值合理 (20-40 之間)"""
    rate = get_usd_twd_rate()
    assert isinstance(rate, float)
    assert 20.0 < rate < 40.0

@patch("yfinance.Ticker")
def test_get_usd_twd_rate_yfinance_fallback(mock_ticker):
    """驗證當 yfinance 拋出異常時，匯率獲取能優雅 Fallback"""
    # 模擬 yfinance 故障
    mock_ticker.side_effect = Exception("yfinance down")
    
    # 呼叫匯率獲取
    rate = get_usd_twd_rate()
    
    # 應能藉由 FinMind 或 預設值 32.2 獲取合理浮點數
    assert isinstance(rate, float)
    assert 20.0 < rate < 40.0

def test_get_adr_snapshots_structure():
    """驗證 ADR 數據包裝格式是否完全正確"""
    output = get_adr_snapshots()
    
    # 檢查頂層欄位
    assert "rate" in output
    assert "timestamp" in output
    assert "data" in output
    
    rate = output["rate"]
    assert isinstance(rate, float)
    assert 20.0 < rate < 40.0
    
    # 檢查子資料結構
    data_list = output["data"]
    assert len(data_list) == len(ADR_PAIRS)
    
    for item in data_list:
        assert "key" in item
        assert "name" in item
        assert "adr_ticker" in item
        assert "adr_price" in item
        assert "tw_code" in item
        assert "tw_price" in item
        assert "adr_twd_equiv" in item
        assert "premium_pct" in item
        
        assert item["key"] in ADR_PAIRS
        assert isinstance(item["adr_price"], float)
        assert isinstance(item["tw_price"], float)
        assert isinstance(item["adr_twd_equiv"], float)
        assert isinstance(item["premium_pct"], float)

def test_premium_calculation_math():
    """手動 Mock 股價與匯率，驗證溢折價數學公式與比例是否精確符合標準"""
    # Mock yfinance 的 adr 報價為 $150.0
    # Mock Shioaji / yfinance 的台股 2330 報價為 920.0 元
    # 匯率設為 32.0，Ratio 設為 5
    # 折合台幣應為: (150 * 32) / 5 = 960 元
    # 溢折價率應為: (960 - 920) / 920 * 100% = 4.3478% -> 四捨五入為 4.35%
    
    with patch("yfinance.Ticker") as mock_yf_ticker, \
         patch("adr_query._get_single_stock_price_with_fallback") as mock_tw_price, \
         patch("adr_query.get_usd_twd_rate") as mock_rate:
         
         # 模擬匯率
         mock_rate.return_value = 32.0
         
         # 模擬台股價格 (TSMC: 2330 -> 920.0, UMC: 2303 -> 50.0, ASE: 3711 -> 150.0)
         def tw_price_side_effect(code):
             if code == "2330": return 920.0
             if code == "2303": return 50.0
             if code == "3711": return 150.0
             return 0.0
         mock_tw_price.side_effect = tw_price_side_effect
         
         # 模擬美股 ADR 價格
         mock_instance = MagicMock()
         mock_instance.fast_info = {"lastPrice": 150.0} # TSM
         
         # 依據 ticker 回傳不同 mock 實例
         def ticker_side_effect(symbol):
             inst = MagicMock()
             if symbol == "TSM":
                 inst.fast_info = {"lastPrice": 150.0}
             elif symbol == "UMC":
                 inst.fast_info = {"lastPrice": 8.0} # (8 * 32)/5 = 51.2
             elif symbol == "ASX":
                 inst.fast_info = {"lastPrice": 24.0} # (24 * 32)/5 = 153.6
             return inst
         mock_yf_ticker.side_effect = ticker_side_effect
         
         # 強制清除快取以重新計算
         from sqlite_cache import cache_manager
         cache_manager.delete("adr_dashboard_data")
         
         output = get_adr_snapshots()
         data = {item["key"]: item for item in output["data"]}
         
         # 驗證台積電計算
         tsmc = data["TSMC"]
         assert tsmc["adr_price"] == 150.0
         assert tsmc["tw_price"] == 920.0
         assert tsmc["adr_twd_equiv"] == 960.0
         assert tsmc["premium_pct"] == 4.35 # (960-920)/920 * 100 = 4.3478% -> 4.35%
         
         # 驗證聯電計算
         umc = data["UMC"]
         assert umc["adr_price"] == 8.0
         assert umc["tw_price"] == 50.0
         assert umc["adr_twd_equiv"] == 51.2 # (8 * 32)/5 = 51.2
         assert umc["premium_pct"] == 2.40 # (51.2-50)/50 * 100 = 2.40%
