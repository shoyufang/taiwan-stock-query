import yfinance as yf
import pandas as pd
import logging
from typing import Optional, Dict, Any, List
import datetime

main_logger = logging.getLogger(__name__)

def get_us_stock_info(ticker: str) -> Optional[Dict[str, Any]]:
    """
    透過 yfinance 獲取美股基本資料
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 提取我們需要的關鍵資訊
        return {
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "eps": info.get("trailingEps", "N/A"),
            "dividend_yield": info.get("dividendYield", 0),
            "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52_week_low": info.get("fiftyTwoWeekLow", "N/A"),
            "summary": info.get("longBusinessSummary", "無公司簡介。"),
            "currency": info.get("currency", "USD")
        }
    except Exception as e:
        main_logger.error(f"獲取美股 {ticker} 基本資料失敗: {e}")
        return None

def get_us_stock_history(ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    透過 yfinance 獲取美股歷史 K 線資料
    period 可以是 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return None
            
        # yfinance 的索引是 DatetimeIndex，有時區資訊。轉為無時區的字串格式
        df.reset_index(inplace=True)
        if 'Date' in df.columns:
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        elif 'Datetime' in df.columns:
            df['Datetime'] = df['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
        return df
    except Exception as e:
        main_logger.error(f"獲取美股 {ticker} 歷史資料失敗: {e}")
        return None

def get_us_stock_news(ticker: str) -> List[Dict[str, Any]]:
    """
    透過 yfinance 獲取美股相關新聞
    """
    try:
        stock = yf.Ticker(ticker)
        news_list = stock.news
        results = []
        for n in news_list:
            results.append({
                "title": n.get("title", ""),
                "publisher": n.get("publisher", "Yahoo Finance"),
                "link": n.get("link", ""),
                "providerPublishTime": n.get("providerPublishTime", 0),
                "type": n.get("type", "STORY")
            })
        return results
    except Exception as e:
        main_logger.error(f"獲取美股 {ticker} 新聞失敗: {e}")
        return []
