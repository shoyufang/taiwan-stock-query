import logging
import time
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

from logging_config import main_logger
from sqlite_cache import get_cache, set_cache
import query_wrapper as qw

# 監控對照組
ADR_PAIRS = {
    "TSMC": {"adr_ticker": "TSM", "tw_code": "2330", "ratio": 5, "name": "台積電"},
    "UMC": {"adr_ticker": "UMC", "tw_code": "2303", "ratio": 5, "name": "聯電"},
    "ASE": {"adr_ticker": "ASX", "tw_code": "3711", "ratio": 5, "name": "日月光"}
}

def get_usd_twd_rate() -> float:
    """
    獲取最新美元兌台幣匯率 (含多重 Fallback)
    1. 優先從 yfinance 獲取 TWD=X (即時)
    2. 備份從 FinMind 獲取今日匯率
    3. 終極 Fallback 預設值 32.2
    """
    cache_key = "usd_twd_rate_val"
    cached = get_cache(cache_key)
    if cached is not None:
        return float(cached)

    # 1. 嘗試 yfinance TWD=X
    try:
        ticker = yf.Ticker("TWD=X")
        # 嘗試使用 fast_info 獲取最新價
        rate = ticker.fast_info.get('lastPrice')
        if rate and 20 < rate < 40:  # 確保在合理區間
            set_cache(cache_key, rate, ttl=300)  # 匯率快取 5 分鐘
            return float(rate)
            
        # 若 fast_info 沒有，使用 history
        hist = ticker.history(period="2d")
        if not hist.empty and len(hist) >= 1:
            rate = hist['Close'].iloc[-1]
            if 20 < rate < 40:
                set_cache(cache_key, rate, ttl=300)
                return float(rate)
    except Exception as e:
        main_logger.warning(f"從 yfinance 獲取匯率失敗: {e}")

    # 2. 嘗試 FinMind / 銀行匯率
    try:
        today = date.today()
        # 查過去五天，防範週末或假日無匯率
        df_rate = qw.query_exchange_rate("USD", today - timedelta(days=5), today)
        if isinstance(df_rate, pd.DataFrame) and not df_rate.empty:
            # 找到最新的買入或賣出匯率均值
            if 'cash_buy' in df_rate.columns and 'cash_sell' in df_rate.columns:
                df_rate['rate'] = (df_rate['cash_buy'].astype(float) + df_rate['cash_sell'].astype(float)) / 2
                rate = df_rate['rate'].dropna().iloc[-1]
                if 20 < rate < 40:
                    set_cache(cache_key, rate, ttl=3600)  # FinMind 匯率快取 1 小時
                    return float(rate)
    except Exception as e:
        main_logger.warning(f"從 FinMind 獲取匯率失敗: {e}")

    # 3. 終極 Fallback
    main_logger.warning("匯率 API 全數失效，使用預設值 32.2")
    return 32.2

def _get_single_stock_price_with_fallback(tw_code: str) -> float:
    """
    獲取台股最新價格，優先使用 Shioaji 快照，Fallback 使用 yfinance (防斷線或週末)
    """
    # 1. 嘗試 Shioaji 即時快照
    try:
        snap = qw.query_snapshot([tw_code])
        if isinstance(snap, pd.DataFrame) and not snap.empty:
            # 檢查列名可能為 '收盤' 或 'close'
            for col in ['收盤', 'close', 'current_price', '最新價']:
                if col in snap.columns:
                    val = snap.iloc[0][col]
                    # 排除 0 或 None
                    if val and float(val) > 0:
                        return float(val)
    except Exception as e:
        main_logger.debug(f"Shioaji 快照獲取台股 {tw_code} 失敗: {e}")

    # 2. Fallback: 使用 yfinance 獲取個股日 K 最末收盤價
    try:
        tw_ticker = f"{tw_code}.TW"
        ticker = yf.Ticker(tw_ticker)
        hist = ticker.history(period="5d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            if price and price > 0:
                return float(price)
    except Exception as e:
        main_logger.warning(f"yfinance Fallback 獲取台股 {tw_code} 失敗: {e}")

    return 0.0

def get_adr_snapshots() -> Dict[str, Any]:
    """
    獲取台美 ADR 即時對比與溢折價數據 (全套 60 秒 SQLite 快取)
    """
    cache_key = "adr_dashboard_data"
    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    start_time = time.time()
    main_logger.info("開始抓取台美 ADR 對比數據...")

    rate = get_usd_twd_rate()
    results = []

    for key, cfg in ADR_PAIRS.items():
        adr_ticker = cfg["adr_ticker"]
        tw_code = cfg["tw_code"]
        ratio = cfg["ratio"]
        name = cfg["name"]

        # 1. 抓取美股 ADR 即時價
        adr_price = 0.0
        try:
            ticker = yf.Ticker(adr_ticker)
            # 優先使用 fast_info
            adr_price = ticker.fast_info.get('lastPrice', 0.0)
            if not adr_price or adr_price <= 0:
                hist = ticker.history(period="2d")
                if not hist.empty:
                    adr_price = hist['Close'].iloc[-1]
        except Exception as e:
            main_logger.error(f"獲取美股 ADR {adr_ticker} 價格失敗: {e}")

        # 2. 抓取台股即時價 (含強健 Fallback)
        tw_price = _get_single_stock_price_with_fallback(tw_code)

        # 3. 計算溢折價
        if adr_price > 0 and tw_price > 0:
            # ADR 折合台幣價 = (ADR 美金價 * 匯率) / 換算比例
            adr_twd_equiv = (adr_price * rate) / ratio
            # 溢折價率 = (折合台幣價 - 台股實際價) / 台股實際價 * 100%
            premium_pct = ((adr_twd_equiv - tw_price) / tw_price) * 100
        else:
            adr_twd_equiv = 0.0
            premium_pct = 0.0

        results.append({
            "key": key,
            "name": name,
            "adr_ticker": adr_ticker,
            "adr_price": round(adr_price, 2) if adr_price else 0.0,
            "tw_code": tw_code,
            "tw_price": round(tw_price, 2) if tw_price else 0.0,
            "adr_twd_equiv": round(adr_twd_equiv, 2) if adr_twd_equiv else 0.0,
            "premium_pct": round(premium_pct, 2) if premium_pct else 0.0
        })

    elapsed_ms = (time.time() - start_time) * 1000
    main_logger.info(f"台美 ADR 數據抓取完成，耗時 {elapsed_ms:.1f}ms")

    output = {
        "rate": rate,
        "timestamp": time.strftime("%H:%M:%S"),
        "data": results
    }

    # 存入快取 60 秒
    set_cache(cache_key, output, ttl=60)
    return output
