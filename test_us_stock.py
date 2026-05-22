import pytest
import pandas as pd
from us_stock_query import get_us_stock_info, get_us_stock_history, get_us_stock_news
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
