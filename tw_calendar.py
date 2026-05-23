"""
台股財報行事曆與除權息日程引擎 — Phase 7 Stage 5 (台股擴充)
提供 50 檔台股權值股 (台灣 50 成份股) 的法說會/財報申報日、預估 EPS、除息日與預估營收
"""

import time
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from logging_config import main_logger
from sqlite_cache import get_cache, set_cache

# 50 檔最具代表性的台股權值股 (台灣 50 指數成分股及熱門藍籌)
TW_SCREENER_POOL = [
    "2330", "2317", "2454", "2308", "2881", "2882", "2382", "2301", "2357", "2891",
    "2303", "3711", "2412", "2886", "2002", "1216", "2327", "2603", "2609", "2615",
    "5880", "2892", "2885", "3008", "3045", "2395", "4938", "2884", "2880", "1301",
    "1303", "1326", "1101", "2912", "6505", "2408", "2379", "3037", "3034", "2377",
    "2353", "2324", "3231", "3481", "2409", "1605", "2618", "2610", "9904", "1402"
]

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
    cache_key = "tw_calendar_consensus_dataset"
    ttl_seconds = 86400  # 24 小時
    
    if not force_refresh:
        cached_df = get_cache(cache_key)
        if isinstance(cached_df, pd.DataFrame) and not cached_df.empty:
            main_logger.info("成功從 SQLite 快取讀取台股日曆數據")
            return cached_df
            
    main_logger.info("台股日曆快取失效，啟動並行抓取台股數據...")
    results = []
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_single_tw_calendar_consensus, code): code for code in TW_SCREENER_POOL}
        for future in as_completed(futures):
            code = futures[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception as exc:
                main_logger.error(f"台股日曆線程 {code} 產生異常: {exc}")
                
    main_logger.info(f"台股日曆並行下載完成，費時: {time.time() - start_time:.2f} 秒，共取得 {len(results)} 檔數據")
    
    if not results:
        main_logger.warning("所有台股日曆下載均失敗，回傳空 DataFrame")
        return pd.DataFrame()
        
    df = pd.DataFrame(results)
    # 儲存到快取
    set_cache(cache_key, df, ttl=ttl_seconds)
    return df
