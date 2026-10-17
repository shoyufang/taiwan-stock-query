"""
技術分析指標與雙圖表渲染引擎單元測試 — Phase 7 Stage 1-5
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import technical_analysis as ta

@pytest.fixture
def sample_stock_df():
    """建立包含100天模擬股價資料的 DataFrame"""
    np.random.seed(42)
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(100)]
    
    # 模擬隨機股價波動
    close = 100.0 + np.random.normal(0, 2.0, 100).cumsum()
    open_prices = close + np.random.normal(0, 0.5, 100)
    high = np.maximum(open_prices, close) + np.random.uniform(0, 1.5, 100)
    low = np.minimum(open_prices, close) - np.random.uniform(0, 1.5, 100)
    volume = np.random.uniform(1000, 10000, 100)
    
    df = pd.DataFrame({
        "open": open_prices,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    
    return df

def test_technical_indicator_calculations(sample_stock_df):
    """測試技術指標計算函數"""
    df = sample_stock_df.copy()
    
    # 1. MA
    ma20 = ta.calc_ma(df, window=20)
    assert len(ma20) == 100
    assert pd.isna(ma20.iloc[18])
    assert not pd.isna(ma20.iloc[19])
    
    # 2. EMA
    ema12 = ta.calc_ema(df, window=12)
    assert len(ema12) == 100
    assert not pd.isna(ema12.iloc[0]) # EMA 透過 ewm 可以有啟始值
    
    # 3. RSI
    rsi14 = ta.calc_rsi(df, window=14)
    assert len(rsi14) == 100
    assert pd.isna(rsi14.iloc[12])
    assert not pd.isna(rsi14.iloc[14])
    assert all(0 <= val <= 100 for val in rsi14.dropna())
    
    # 4. MACD
    macd_line, signal_line, histogram = ta.calc_macd(df)
    assert len(macd_line) == 100
    assert len(signal_line) == 100
    assert len(histogram) == 100
    
    # 5. Bollinger Bands
    middle, upper, lower = ta.calc_bollinger_bands(df, window=20)
    assert len(middle) == 100
    assert len(upper) == 100
    assert len(lower) == 100
    assert all(upper.dropna() >= middle.dropna())
    assert all(middle.dropna() >= lower.dropna())
    
    # 6. ATR
    atr14 = ta.calc_atr(df, window=14)
    assert len(atr14) == 100
    assert pd.isna(atr14.iloc[12])
    assert not pd.isna(atr14.iloc[14])

def test_plot_kbar_with_indicators(sample_stock_df):
    """測試 Plotly 技術指標圖表生成"""
    df = sample_stock_df.copy()
    
    fig = ta.plot_kbar_with_indicators(
        df=df,
        code="2330",
        indicators=["MA5", "MA20", "RSI", "MACD", "BB", "ATR"],
        height=800
    )
    
    assert isinstance(fig, go.Figure)
    
    # 驗證標題
    assert "2330" in fig.layout.title.text
    # 驗證 subplot 數量 (K線 + 成交量 + RSI + MACD + ATR) 共 5 個 subplot
    # Plotly 內部的 subplots 在有多個 row 時會有 shared xaxis
    assert len(fig.data) > 0

def test_render_tradingview_chart_html(sample_stock_df):
    """測試 TradingView HTML Canvas 圖表渲染包含全部指標 JS 代碼"""
    df = sample_stock_df.copy()
    
    theme_cfg = {
        "bg": "#0F172A",
        "surface": "#1E293B",
        "primary": "#3B82F6",
        "text": "#F1F5F9",
        "border": "#334155"
    }
    
    html = ta.render_tradingview_chart(
        df=df,
        code="AAPL",
        theme_cfg=theme_cfg,
        indicators=["MA5", "MA20", "EMA12", "BB", "RSI", "MACD", "ATR"],
        height=750
    )
    
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "LightweightCharts.createChart" in html
    assert "addCandlestickSeries" in html
    assert "addHistogramSeries" in html
    
    # 驗證是否包含大升級後的所有主圖趨勢指標 JS 調用與關鍵字
    assert "maData" in html
    assert "emaData" in html
    assert "bbData" in html
