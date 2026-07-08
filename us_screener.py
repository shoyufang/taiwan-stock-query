"""
美股多因子選股引擎 — Phase 7 Stage 4
提供 50 檔熱門美股巨頭/藍籌股的多因子篩選、背景並行下載與 12 小時 SQLite 快取
"""

import time
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from logging_config import main_logger
from sqlite_cache import get_cache, set_cache
from stock_pools import US_TOP50 as US_SCREENER_POOL

def _fetch_ticker_metrics(ticker: str) -> Optional[dict]:
    """獲取單檔美股的關鍵篩選指標"""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info:
            main_logger.warning(f"美股 {ticker} 未回傳有效 info")
            return None
        
        # 獲取最新價格 (支援 Fallback)
        current_price = info.get("currentPrice")
        if current_price is None:
            current_price = info.get("regularMarketPrice")
        
        if current_price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
        
        if current_price is None:
            main_logger.warning(f"無法取得美股 {ticker} 的最新價格")
            return None
            
        # 52 週高點，若無則以現價替代
        fifty_two_week_high = info.get("fiftyTwoWeekHigh")
        if fifty_two_week_high is None:
            fifty_two_week_high = current_price
            
        # 計算拉回幅度% (通常為負值或 0)
        pullback = ((current_price - fifty_two_week_high) / fifty_two_week_high) * 100 if fifty_two_week_high else 0.0

        # dividendYield 轉換為百分比數值
        div_yield = info.get("dividendYield")
        div_yield_pct = div_yield * 100 if div_yield is not None else 0.0

        # returnOnEquity 轉換為百分比數值
        roe = info.get("returnOnEquity")
        roe_pct = roe * 100 if roe is not None else 0.0

        return {
            "代號": ticker,
            "名稱": info.get("shortName") or info.get("longName") or ticker,
            "行業板塊": info.get("sector") or "Other",
            "細分產業": info.get("industry") or "Other",
            "收盤": round(current_price, 2),
            "52週高點": round(fifty_two_week_high, 2),
            "拉回幅度%": round(pullback, 2),
            "本益比": round(info.get("trailingPE"), 2) if info.get("trailingPE") is not None else float("nan"),
            "預期本益比": round(info.get("forwardPE"), 2) if info.get("forwardPE") is not None else float("nan"),
            "股利殖利率%": round(div_yield_pct, 2),
            "股東權益報酬率%": round(roe_pct, 2),
            "市值": info.get("marketCap") or 0
        }
    except Exception as e:
        main_logger.error(f"下載美股 {ticker} 指標失敗: {str(e)}")
        return None

def get_us_screener_data(force_refresh: bool = False, max_workers: int = 10) -> pd.DataFrame:
    """
    獲取美股 50 檔股票的篩選指標數據。
    支援 12 小時 SQLite 永久快取 (TTL: 43200 秒)。
    """
    cache_key = "us_screener_dataset"
    ttl_seconds = 43200  # 12 小時
    
    if not force_refresh:
        cached_df = get_cache(cache_key)
        if isinstance(cached_df, pd.DataFrame) and not cached_df.empty:
            main_logger.info("成功從 SQLite 快取讀取美股選股數據")
            return cached_df
            
    main_logger.info("快取失效或要求強制刷新，啟動並行下載美股指標數據...")
    results = []
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_ticker_metrics, ticker): ticker for ticker in US_SCREENER_POOL}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception as exc:
                main_logger.error(f"美股線程 {ticker} 產生異常: {exc}")
                
    main_logger.info(f"並行下載完成，花費時間: {time.time() - start_time:.2f} 秒，共取得 {len(results)} 檔數據")
    
    if not results:
        main_logger.warning("所有美股指標下載均失敗，回傳空 DataFrame")
        return pd.DataFrame()
        
    df = pd.DataFrame(results)
    # 儲存到快取
    set_cache(cache_key, df, ttl=ttl_seconds)
    return df

def filter_us_stocks(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    """
    多因子過濾邏輯：
    傳入篩選條件字典 filters，回傳符合條件的股票 DataFrame。
    
    支援因子：
    - min_mcap: 最小市值 (例如 100B, 50B, 10B, All)
    - max_pe: 最大本益比 (None 表示不限制)
    - max_forward_pe: 最大預期本益比 (None 表示不限制)
    - min_roe: 最小 ROE%
    - min_yield: 最小股利殖利率%
    - pullback_min: 最小拉回幅度% (如 -20)
    - pullback_max: 最大拉回幅度% (如 -5)
    - sectors: 允許的行業板塊清單 (List[str], 若為空或 "All" 則不限制)
    """
    if df.empty:
        return df
        
    filtered = df.copy()
    
    # 1. 市值篩選
    # 單位是 B (Billion USD)
    # yfinance 中的 marketCap 是原始數字 (e.g. 3,000,000,000,000)
    min_mcap_str = filters.get("min_mcap", "All")
    if min_mcap_str != "All":
        mcap_map = {
            "> 100B": 100 * 10**9,
            "> 50B": 50 * 10**9,
            "> 10B": 10 * 10**9,
        }
        threshold = mcap_map.get(min_mcap_str, 0)
        filtered = filtered[filtered["市值"] >= threshold]
        
    # 2. 本益比過濾 (需排除 NaN 或是處理 NaN 排除)
    max_pe = filters.get("max_pe")
    if max_pe is not None and max_pe > 0:
        filtered = filtered[filtered["本益比"].notna() & (filtered["本益比"] <= max_pe)]
        
    # 3. 預期本益比過濾
    max_forward_pe = filters.get("max_forward_pe")
    if max_forward_pe is not None and max_forward_pe > 0:
        filtered = filtered[filtered["預期本益比"].notna() & (filtered["預期本益比"] <= max_forward_pe)]
        
    # 4. ROE% 過濾
    min_roe = filters.get("min_roe")
    if min_roe is not None:
        filtered = filtered[filtered["股東權益報酬率%"] >= min_roe]
        
    # 5. 殖利率% 過濾
    min_yield = filters.get("min_yield")
    if min_yield is not None:
        filtered = filtered[filtered["股利殖利率%"] >= min_yield]
        
    # 6. 拉回幅度% 過濾 (拉回幅度通常為負數，例如 -15% 到 -5%)
    pullback_min = filters.get("pullback_min")
    pullback_max = filters.get("pullback_max")
    if pullback_min is not None and pullback_max is not None:
        filtered = filtered[(filtered["拉回幅度%"] >= pullback_min) & (filtered["拉回幅度%"] <= pullback_max)]
        
    # 7. 板塊過濾
    sectors = filters.get("sectors")
    if sectors and "All" not in sectors:
        filtered = filtered[filtered["行業板塊"].isin(sectors)]
        
    return filtered.reset_index(drop=True)
