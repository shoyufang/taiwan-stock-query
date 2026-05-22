import pytest
import pandas as pd
from us_stock_query import (
    get_us_stock_info, get_us_stock_history, get_us_stock_news,
    get_us_financials, get_us_holders, get_us_analyst_info, get_us_sector_performance
)
from stock_lookup import resolve_us_stock

def test_resolve_us_stock_local():
    # 本地精確匹配
    assert resolve_us_stock("蘋果") == "AAPL"
    assert resolve_us_stock("AAPL") == "AAPL"
    
def test_get_us_stock_info():
    info = get_us_stock_info("AAPL")
    assert info is not None
    assert "Apple" in info["name"]
    assert info["currency"] == "USD"
    
def test_get_us_stock_history():
    df = get_us_stock_history("AAPL", period="1mo")
    assert df is not None
    assert not df.empty
    assert 'Close' in df.columns
    
def test_get_us_stock_news():
    news = get_us_stock_news("AAPL")
    assert isinstance(news, list)

def test_get_us_financials():
    fin = get_us_financials("AAPL")
    assert isinstance(fin, dict)
    assert "income_annual" in fin
    assert "balance_quarterly" in fin
    
def test_get_us_holders():
    holders = get_us_holders("AAPL")
    assert isinstance(holders, dict)
    assert "institutional" in holders
    assert "mutualfund" in holders
    
def test_get_us_analyst_info():
    analyst = get_us_analyst_info("AAPL")
    assert isinstance(analyst, dict)
    assert "current_price" in analyst
    assert analyst["recommendation"] in ["buy", "hold", "sell", "strong_buy", "strong_sell", "underperform", "outperform", "N/A"]

def test_get_us_sector_performance():
    perf = get_us_sector_performance()
    assert isinstance(perf, pd.DataFrame)
    if not perf.empty:
        assert "代號" in perf.columns
        assert "最新價" in perf.columns
        assert "漲跌幅(%)" in perf.columns
