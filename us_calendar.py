"""
美股財報行事曆與華爾街評等共識引擎 — Phase 7 Stage 5
提供 50 檔美股權值股的財報公佈日、預估財務數據、分析師目標價潛在漲幅與評等共識
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from typing import List, Dict, Any, Optional
from logging_config import main_logger
from us_screener import US_SCREENER_POOL
from calendar_engine import fetch_consensus_pool

# 分析師評等中文化對照
RATING_MAP = {
    "strong_buy": "強力買入 🟢🟢",
    "buy": "買入 🟢",
    "hold": "持有 🟡",
    "underperform": "跑輸大盤 🟠",
    "sell": "賣出 🔴",
    "strong_sell": "強力賣出 🔴🔴",
    "none": "無評等 ⚪"
}

def _fetch_single_calendar_consensus(ticker: str) -> Optional[dict]:
    """獲取單檔美股的財報行事曆與華爾街評等共識"""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info:
            return None
            
        calendar = t.calendar
        
        # 1. 解析財報日期
        earnings_date_str = "N/A"
        eps_avg = float("nan")
        rev_avg_b = float("nan")
        
        if isinstance(calendar, dict):
            # 財報日
            ed = calendar.get("Earnings Date")
            if isinstance(ed, list) and len(ed) > 0:
                earnings_date_str = str(ed[0])
            elif ed:
                earnings_date_str = str(ed)
                
            # 預估 EPS
            eps_avg = calendar.get("Earnings Average")
            if eps_avg is None:
                eps_avg = float("nan")
                
            # 預估營收
            rev_avg = calendar.get("Revenue Average")
            if rev_avg is not None:
                rev_avg_b = round(rev_avg / 1e9, 2)
            else:
                rev_avg_b = float("nan")
                
        # 2. 解析價格與評等目標價
        current_price = info.get("currentPrice")
        if current_price is None:
            current_price = info.get("regularMarketPrice")
            
        if current_price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
                
        target_mean = info.get("targetMeanPrice")
        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")
        
        # 計算潛在空間%
        upside = float("nan")
        if current_price and target_mean:
            upside = round(((target_mean - current_price) / current_price) * 100, 2)
            
        rec_key = str(info.get("recommendationKey", "none")).lower()
        rec_chinese = RATING_MAP.get(rec_key, rec_key.upper())
        
        return {
            "代號": ticker,
            "名稱": info.get("shortName") or info.get("longName") or ticker,
            "行業板塊": info.get("sector") or "Other",
            "最新價": round(current_price, 2) if current_price else float("nan"),
            "平均目標價": round(target_mean, 2) if target_mean else float("nan"),
            "目標最高價": round(target_high, 2) if target_high else float("nan"),
            "目標最低價": round(target_low, 2) if target_low else float("nan"),
            "潛在漲幅%": upside,
            "共識評等": rec_chinese,
            "分析師人數": info.get("numberOfAnalystOpinions") or 0,
            "財報公佈日": earnings_date_str,
            "預估下季EPS": eps_avg if pd.notna(eps_avg) else "N/A",
            "預估營收(B)": rev_avg_b if pd.notna(rev_avg_b) else "N/A"
        }
    except Exception as e:
        main_logger.error(f"獲取 {ticker} 財報與共識失敗: {str(e)}")
        return None

def get_us_calendar_consensus_data(force_refresh: bool = False, max_workers: int = 10) -> pd.DataFrame:
    """
    獲取美股 50 檔股票的財報行事曆與華爾街共識數據。
    支援 24 小時 SQLite 永久快取 (TTL: 86400 秒)。
    """
    return fetch_consensus_pool(
        US_SCREENER_POOL, _fetch_single_calendar_consensus,
        "us_calendar_consensus_dataset", "美股日曆與共識",
        force_refresh=force_refresh, max_workers=max_workers,
    )
