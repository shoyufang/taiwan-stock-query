"""
台股財報行事曆與除權息日程引擎 — Phase 7 Stage 5 (台股擴充)
提供 50 檔台股權值股 (台灣 50 成份股) 的法說會/財報申報日、預估 EPS、除息日與預估營收
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from typing import List, Dict, Any, Optional
from logging_config import main_logger
from stock_pools import TW_TOP50 as TW_SCREENER_POOL
from calendar_engine import fetch_consensus_pool

def _fetch_single_tw_calendar_consensus(code: str) -> Optional[dict]:
    """獲取單檔台股的財報/法說會日程與除息日資訊"""
    try:
        # 嘗試利用本地名稱字典獲取中文名稱
        name = code
        try:
            from stock_lookup import resolve_code, get_name_hint
            hint = get_name_hint(code)
            if hint and "➡️" in hint:
                # 例如 "2330 ➡️ 台積電" -> 取 "台積電"
                name = hint.split("➡️")[-1].strip()
            elif hint:
                name = hint
        except Exception:
            pass
            
        t = yf.Ticker(f"{code}.TW")
        info = t.info
        calendar = t.calendar
        
        # 1. 解析財報日與除息日
        earnings_date_str = "N/A"
        ex_div_date_str = "N/A"
        eps_avg = float("nan")
        rev_avg_b = float("nan")
        
        if isinstance(calendar, dict):
            # 財報日
            ed = calendar.get("Earnings Date")
            if isinstance(ed, list) and len(ed) > 0:
                earnings_date_str = str(ed[0])
            elif ed:
                earnings_date_str = str(ed)
                
            # 除息日
            ex_div = calendar.get("Ex-Dividend Date")
            if ex_div:
                ex_div_date_str = str(ex_div)
                
            # 預估 EPS
            eps_avg = calendar.get("Earnings Average")
            if eps_avg is None:
                eps_avg = float("nan")
                
            # 預估營收 (以百萬/十億台幣為單位，yfinance 台股營收通常為台幣)
            rev_avg = calendar.get("Revenue Average")
            if rev_avg is not None:
                rev_avg_b = round(rev_avg / 1e9, 2)
            else:
                rev_avg_b = float("nan")
                
        # 2. 獲取最新收盤價
        current_price = None
        if info:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            
        if current_price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
                
        return {
            "代號": code,
            "名稱": name,
            "最新價": round(current_price, 2) if current_price else float("nan"),
            "財報公佈日": earnings_date_str,
            "除息日": ex_div_date_str,
            "預估下季EPS": eps_avg if pd.notna(eps_avg) else "N/A",
            "預估營收(B元)": rev_avg_b if pd.notna(rev_avg_b) else "N/A"
        }
    except Exception as e:
        main_logger.error(f"獲取台股 {code} 財報日曆失敗: {str(e)}")
        return None

def get_tw_calendar_consensus_data(force_refresh: bool = False, max_workers: int = 10) -> pd.DataFrame:
    """
    獲取台股 50 檔權值股的財報日曆與除息日程。
    支援 24 小時 SQLite 永久快取 (TTL: 86400 秒)。
    """
    return fetch_consensus_pool(
        TW_SCREENER_POOL, _fetch_single_tw_calendar_consensus,
        "tw_calendar_consensus_dataset", "台股日曆",
        force_refresh=force_refresh, max_workers=max_workers,
    )
