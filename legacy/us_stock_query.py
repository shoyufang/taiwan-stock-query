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

def get_us_financials(ticker: str) -> Dict[str, pd.DataFrame]:
    """
    透過 yfinance 獲取美股財務報表 (損益表、資產負債表、現金流量表；含年度與季度)
    """
    try:
        stock = yf.Ticker(ticker)
        res = {
            "income_annual": stock.income_stmt,
            "income_quarterly": stock.quarterly_income_stmt,
            "balance_annual": stock.balance_sheet,
            "balance_quarterly": stock.quarterly_balance_sheet,
            "cashflow_annual": stock.cashflow,
            "cashflow_quarterly": stock.quarterly_cashflow
        }
        # 確保所有 index 和 columns 轉為字串格式，防止導出與渲染異常
        for k, df in res.items():
            if df is not None and not df.empty:
                df.columns = [c.strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c) for c in df.columns]
                df.index = [str(i) for i in df.index]
        return res
    except Exception as e:
        main_logger.error(f"獲取美股 {ticker} 財報失敗: {e}")
        return {}

def get_us_holders(ticker: str) -> Dict[str, pd.DataFrame]:
    """
    透過 yfinance 獲取美股股東結構 (機構持股、共同基金持股)
    """
    try:
        stock = yf.Ticker(ticker)
        inst = stock.institutional_holders
        muf = stock.mutualfund_holders
        
        if inst is not None and not inst.empty:
            inst = inst.copy()
            if 'Date Reported' in inst.columns:
                inst['Date Reported'] = inst['Date Reported'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)
                )
        
        if muf is not None and not muf.empty:
            muf = muf.copy()
            if 'Date Reported' in muf.columns:
                muf['Date Reported'] = muf['Date Reported'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)
                )
                
        return {
            "institutional": inst if inst is not None else pd.DataFrame(),
            "mutualfund": muf if muf is not None else pd.DataFrame()
        }
    except Exception as e:
        main_logger.error(f"獲取美股 {ticker} 股東結構失敗: {e}")
        return {"institutional": pd.DataFrame(), "mutualfund": pd.DataFrame()}

def get_us_analyst_info(ticker: str) -> Dict[str, Any]:
    """
    透過 yfinance 獲取美股分析師目標價與評等
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "current_price": info.get("currentPrice", "N/A"),
            "target_mean": info.get("targetMeanPrice", "N/A"),
            "target_high": info.get("targetHighPrice", "N/A"),
            "target_low": info.get("targetLowPrice", "N/A"),
            "analyst_count": info.get("numberOfAnalystOpinions", "N/A"),
            "recommendation": info.get("recommendationKey", "N/A"),
            "recommendation_mean": info.get("recommendationMean", "N/A")
        }
    except Exception as e:
        main_logger.error(f"獲取美股 {ticker} 分析師評等失敗: {e}")
        return {}

def get_us_sector_performance() -> pd.DataFrame:
    """
    獲取美股主要指數與行業板塊 ETF 的今日漲跌幅
    """
    mapping = {
        "SPY": ("S&P 500 指數 (SPY)", "大盤"),
        "QQQ": ("那斯達克 100 指數 (QQQ)", "大盤"),
        "DIA": ("道瓊工業 指數 (DIA)", "大盤"),
        "IWM": ("羅素 2000 指數 (IWM)", "大盤"),
        "XLK": ("科技板塊 (XLK)", "板塊"),
        "XLF": ("金融板塊 (XLF)", "板塊"),
        "XLV": ("醫療保健板塊 (XLV)", "板塊"),
        "XLY": ("消費性商品板塊 (XLY)", "板塊"),
        "XLE": ("能源板塊 (XLE)", "板塊"),
        "XLI": ("工業板塊 (XLI)", "板塊"),
        "XLP": ("民生消費板塊 (XLP)", "板塊"),
        "XLU": ("公用事業板塊 (XLU)", "板塊"),
        "XLB": ("原物料板塊 (XLB)", "板塊"),
        "XLRE": ("不動產板塊 (XLRE)", "板塊"),
        "XLC": ("通訊服務板塊 (XLC)", "板塊"),
    }
    
    tickers = list(mapping.keys())
    try:
        df = yf.download(tickers, period="5d", progress=False)
        if df.empty:
            return pd.DataFrame()
            
        res = []
        for tk in tickers:
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if ('Close', tk) in df.columns:
                        tk_close = df[('Close', tk)].dropna()
                    else:
                        continue
                else:
                    if 'Close' in df.columns:
                        tk_close = df['Close'].dropna()
                    else:
                        continue
                        
                if len(tk_close) >= 2:
                    prev_close = tk_close.iloc[-2]
                    last_close = tk_close.iloc[-1]
                    change = last_close - prev_close
                    pct = (change / prev_close) * 100
                    name, category = mapping[tk]
                    res.append({
                        "代號": tk,
                        "名稱": name,
                        "分類": category,
                        "最新價": round(last_close, 2),
                        "漲跌": round(change, 2),
                        "漲跌幅(%)": round(pct, 2)
                    })
            except Exception as e:
                main_logger.error(f"處理板塊 {tk} 失敗: {e}")
        return pd.DataFrame(res)
    except Exception as e:
        main_logger.error(f"下載板塊表現失敗: {e}")
        return pd.DataFrame()
