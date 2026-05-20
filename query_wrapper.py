"""
查詢函式包裝層 — 簡化 UI 調用
Phase 5.3: 添加日誌和性能追蹤
Phase 6.1: 添加非同步查詢支持
Phase 7.6: 本地 TWSE CSV 快取優先讀取
"""

import os
import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Callable, Tuple
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sinopac_query as sq
from config import load_config, add_history
from logging_config import main_logger, perf_tracker
from sqlite_cache import get_cache, set_cache


# ══════════════════════════════════════════════════════════
# 本地 TWSE CSV 快取工具
# ══════════════════════════════════════════════════════════

def _twse_local_cache_path(category: str, query_date: date = None) -> str:
    """回傳 data/twse/<category>/YYYY-MM-DD.csv 路徑"""
    d = (query_date or date.today()).isoformat()
    return os.path.join("data", "twse", category, f"{d}.csv")


def _read_twse_local(category: str, query_date: date = None) -> Optional[pd.DataFrame]:
    """
    嘗試讀取本地 TWSE CSV 快取。
    成功回傳 DataFrame，不存在回傳 None。
    """
    path = _twse_local_cache_path(category, query_date)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        main_logger.debug(f"讀取本地快取: {path} ({len(df)} 筆)")
        return df
    except Exception as e:
        main_logger.warning(f"讀取本地快取失敗 {path}: {e}")
        return None


def twse_cache_status() -> dict:
    """
    回傳今日 TWSE 本地快取狀態，供 UI 顯示。
    {category: {"exists": bool, "rows": int, "path": str}}
    """
    categories = ["daily_all", "institutional", "valuation", "margin",
                  "mi_index", "notice", "disposition"]
    status = {}
    for cat in categories:
        path = _twse_local_cache_path(cat)
        if os.path.exists(path):
            try:
                rows = sum(1 for _ in open(path, encoding="utf-8-sig")) - 1
            except Exception:
                rows = 0
            status[cat] = {"exists": True, "rows": rows, "path": path}
        else:
            status[cat] = {"exists": False, "rows": 0, "path": path}
    return status

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    # Mock decorator for non-Streamlit environments
    def cache_data(ttl=None, show_spinner=True):
        def decorator(func):
            return func
        return decorator

    class StreamlitMock:
        cache_data = staticmethod(cache_data)

    st = StreamlitMock()

# 緩存命中追蹤 — 用於檢測 Streamlit 緩存的命中
_query_cache = {}  # {func_name: {key: timestamp}}
_cache_ttl = {
    "query_ranking": 300,
    "query_snapshot": 300,
    "_cached_kbar": 86400,
    "_cached_ticks": 86400,
    "_cached_institutional": 3600,
    "_cached_institutional_summary": 3600,
    "_cached_day_trading": 3600,
    "_cached_margin_short": 3600,
    "_cached_shareholding": 3600,
    "_cached_securities_lending": 3600,
    "_cached_month_revenue": 604800,
    "_cached_financial_statement": 604800,
    "_cached_balance_sheet": 604800,
    "_cached_dividend": 604800,
    "_cached_twse_daily": 300,
    "_cached_twse_valuation": 300,
    "_cached_twse_institutional": 300,
    "_cached_twse_margin": 300,
    "_cached_stock_news": 3600,
    "_cached_market_news": 3600,
}

def _record_cache_hit(func_name: str, cache_key: str, is_hit: bool):
    """記錄緩存命中/未命中"""
    perf_tracker.record_cache_hit(func_name, is_hit)
    if is_hit:
        main_logger.debug(f"[CACHE HIT] {func_name}: {cache_key}")
    else:
        main_logger.debug(f"[CACHE MISS] {func_name}: {cache_key}")

def _check_cache_hit(func_name: str, cache_key: str) -> bool:
    """檢查是否命中緩存"""
    current_time = time.time()

    if func_name not in _query_cache:
        _query_cache[func_name] = {}

    if cache_key in _query_cache[func_name]:
        last_time = _query_cache[func_name][cache_key]
        ttl = _cache_ttl.get(func_name, 300)
        is_hit = (current_time - last_time) < ttl
        _query_cache[func_name][cache_key] = current_time
        return is_hit
    else:
        _query_cache[func_name][cache_key] = current_time
        return False

# ══════════════════════════════════════════════════════════
# 台股市場相關查詢
# ══════════════════════════════════════════════════════════

def _cached_ranking_internal(ranking_type: str, limit: int) -> pd.DataFrame:
    """Internal cached ranking query"""
    type_map = {
        "up": ("ChangePercentRank", True),
        "down": ("ChangePercentRank", False),
        "volume": ("VolumeRank", True),
        "amount": ("AmountRank", True),
    }
    if ranking_type not in type_map:
        return pd.DataFrame()
    scanner_type, ascending = type_map[ranking_type]
    return sq.query_scanner(scanner_type, ascending, count=limit)

@st.cache_data(ttl=300, show_spinner=False)  # 5 min: Real-time ranking
def _cached_ranking(ranking_type: str, limit: int) -> pd.DataFrame:
    """Streamlit cached ranking query with SQLite fallback"""
    cache_key = f"ranking:{ranking_type}:{limit}"
    # 嘗試從 SQLite 獲取
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
    
    # 執行實際查詢
    result = _cached_ranking_internal(ranking_type, limit)
    
    # 存入 SQLite (與 Streamlit TTL 同步)
    if not result.empty:
        set_cache(cache_key, result, ttl=300)
    return result

def query_ranking(ranking_type: str, limit: int = 10) -> pd.DataFrame:
    """
    查詢市場排行
    ranking_type: "up" (漲幅), "down" (跌幅), "volume" (成交量), "amount" (成交金額)
    """
    start_time = time.time()
    cache_key = f"{ranking_type}:{limit}"
    is_cache_hit = _check_cache_hit("query_ranking", cache_key)
    _record_cache_hit("query_ranking", cache_key, is_cache_hit)
    main_logger.info(f"查詢排行: {ranking_type}, limit={limit} ({'CACHE HIT' if is_cache_hit else 'CACHE MISS'})")

    if ranking_type not in ["up", "down", "volume", "amount"]:
        main_logger.warning(f"無效排行類型: {ranking_type}")
        return pd.DataFrame()

    try:
        result = _cached_ranking(ranking_type, limit)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_ranking", elapsed_ms)
        main_logger.info(f"排行查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("台股市場", {"type": "ranking", "ranking_type": ranking_type})
        return result
    except Exception as e:
        main_logger.error(f"查詢排行失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)  # 5 min: Real-time snapshot
def _cached_snapshot(codes_tuple: tuple) -> pd.DataFrame:
    """Internal cached snapshot query with SQLite fallback"""
    codes = list(codes_tuple)
    cache_key = f"snapshot:{','.join(sorted(codes))}"
    
    # 嘗試從 SQLite 獲取
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_snapshot(codes)
    
    if not result.empty:
        set_cache(cache_key, result, ttl=300)
    return result

def query_snapshot(codes: List[str]) -> pd.DataFrame:
    """查詢個股即時快照"""
    start_time = time.time()
    cache_key = str(tuple(codes))
    is_cache_hit = _check_cache_hit("query_snapshot", cache_key)
    _record_cache_hit("query_snapshot", cache_key, is_cache_hit)
    main_logger.info(f"查詢快照: {codes} ({'CACHE HIT' if is_cache_hit else 'CACHE MISS'})")
    try:
        result = _cached_snapshot(tuple(codes))
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_snapshot", elapsed_ms)
        main_logger.info(f"快照查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("台股市場", {"type": "snapshot", "codes": codes})
        return result
    except Exception as e:
        main_logger.error(f"查詢快照失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)  # 1 day: Historical K-bars
def _cached_kbar(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached K-bar query with SQLite fallback"""
    cache_key = f"kbar:{code}:{start_str}:{end_str}"
    
    # 嘗試從 SQLite 獲取
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_kbars(code, start_str, end_str)
    
    if not result.empty:
        set_cache(cache_key, result, ttl=86400)
    return result

def query_daily_kbar(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢日K線"""
    start_time = time.time()
    cache_key = f"{code}:{start_date}:{end_date}"
    is_cache_hit = _check_cache_hit("query_daily_kbar", cache_key)
    _record_cache_hit("query_daily_kbar", cache_key, is_cache_hit)
    main_logger.info(f"查詢 K 線: {code}, {start_date} ~ {end_date} ({'CACHE HIT' if is_cache_hit else 'CACHE MISS'})")
    try:
        # 確保日期格式正確
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date).date()
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date).date()

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_kbar(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_daily_kbar", elapsed_ms)
        main_logger.info(f"K 線查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("台股市場", {"type": "kbar", "code": code, "start": start_str, "end": end_str})
        return result
    except Exception as e:
        main_logger.error(f"查詢 K 線失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)  # 1 day: Historical ticks
def _cached_ticks(code: str, date_str: str) -> pd.DataFrame:
    """Internal cached ticks query with SQLite fallback"""
    cache_key = f"ticks:{code}:{date_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_ticks(code, date_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=86400)
    return result

def query_ticks(code: str, query_date: date) -> pd.DataFrame:
    """查詢逐筆成交"""
    start_time = time.time()
    main_logger.info(f"查詢逐筆: {code}, {query_date}")
    try:
        date_str = query_date.strftime("%Y-%m-%d")
        result = _cached_ticks(code, date_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_ticks", elapsed_ms)
        main_logger.info(f"逐筆查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("台股市場", {"type": "ticks", "code": code, "date": date_str})
        return result
    except Exception as e:
        main_logger.error(f"查詢逐筆失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# FinMind 籌碼面相關查詢 (1 hour cache: Technical indicators)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_institutional(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached institutional query with SQLite fallback"""
    cache_key = f"institutional:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_institutional(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=3600)
    return result

def query_institutional_investors(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢三大法人明細"""
    start_time = time.time()
    main_logger.info(f"查詢三大法人明細: {code}, {start_date} ~ {end_date}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_institutional(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_institutional_investors", elapsed_ms)
        main_logger.info(f"三大法人查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "institutional", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢三大法人明細失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_institutional_summary(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached institutional summary query with SQLite fallback"""
    cache_key = f"institutional_summary:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_institutional_summary(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=3600)
    return result

def query_institutional_summary(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢三大法人合計"""
    start_time = time.time()
    main_logger.info(f"查詢三大法人合計: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_institutional_summary(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_institutional_summary", elapsed_ms)
        main_logger.info(f"三大法人合計查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "institutional_summary", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢三大法人合計失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_day_trading(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached day trading query with SQLite fallback"""
    cache_key = f"day_trading:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_day_trading(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=3600)
    return result

def query_day_trading_volume(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢當沖交易量"""
    start_time = time.time()
    main_logger.info(f"查詢當沖交易: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_day_trading(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_day_trading_volume", elapsed_ms)
        main_logger.info(f"當沖交易查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "day_trading", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢當沖交易失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_margin_short(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached margin short query with SQLite fallback"""
    cache_key = f"margin_short:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_margin_short(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=3600)
    return result

def query_margin_short(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢融資融券餘額"""
    start_time = time.time()
    main_logger.info(f"查詢融資融券: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_margin_short(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_margin_short", elapsed_ms)
        main_logger.info(f"融資融券查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "margin_short", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢融資融券失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_shareholding(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached shareholding query with SQLite fallback"""
    cache_key = f"shareholding:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_shareholding(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=3600)
    return result

def query_foreign_shareholding(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢外資持股比例"""
    start_time = time.time()
    main_logger.info(f"查詢外資持股: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_shareholding(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_foreign_shareholding", elapsed_ms)
        main_logger.info(f"外資持股查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "shareholding", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢外資持股失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_securities_lending(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached securities lending query with SQLite fallback"""
    cache_key = f"securities_lending:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_securities_lending(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=3600)
    return result

def query_securities_lending(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢借券成交"""
    start_time = time.time()
    main_logger.info(f"查詢借券成交: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_securities_lending(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_securities_lending", elapsed_ms)
        main_logger.info(f"借券成交查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "securities_lending", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢借券成交失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# FinMind 基本面相關查詢 (1 week cache: Fundamental data)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=604800, show_spinner=False)  # 1 week
def _cached_month_revenue(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached month revenue query with SQLite fallback"""
    cache_key = f"month_revenue:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_month_revenue(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=604800)
    return result

def query_month_revenue(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢月營收"""
    start_time = time.time()
    main_logger.info(f"查詢月營收: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_month_revenue(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_month_revenue", elapsed_ms)
        main_logger.info(f"月營收查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "month_revenue", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢月營收失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=604800, show_spinner=False)
def _cached_financial_statement(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached financial statement query with SQLite fallback"""
    cache_key = f"financial_statement:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_financial_statement(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=604800)
    return result

def query_financial_statement(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢綜合損益表"""
    start_time = time.time()
    main_logger.info(f"查詢綜合損益表: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_financial_statement(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_financial_statement", elapsed_ms)
        main_logger.info(f"綜合損益表查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "financial_statement", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢綜合損益表失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=604800, show_spinner=False)
def _cached_balance_sheet(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached balance sheet query with SQLite fallback"""
    cache_key = f"balance_sheet:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_balance_sheet(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=604800)
    return result

def query_balance_sheet(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢資產負債表"""
    start_time = time.time()
    main_logger.info(f"查詢資產負債表: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_balance_sheet(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_balance_sheet", elapsed_ms)
        main_logger.info(f"資產負債表查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "balance_sheet", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢資產負債表失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=604800, show_spinner=False)
def _cached_dividend(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """Internal cached dividend query with SQLite fallback"""
    cache_key = f"dividend:{code}:{start_str}:{end_str}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data
        
    result = sq.query_dividend(code, start_str, end_str)
    if not result.empty:
        set_cache(cache_key, result, ttl=604800)
    return result

def query_dividend(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢股利政策"""
    start_time = time.time()
    main_logger.info(f"查詢股利政策: {code}")
    try:
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        result = _cached_dividend(code, start_str, end_str)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_dividend", elapsed_ms)
        main_logger.info(f"股利政策查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("FinMind", {"type": "dividend", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢股利政策失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# TWSE 相關查詢 (5 min cache: Real-time daily data)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_daily(code: Optional[str]) -> pd.DataFrame:
    return sq.query_twse_daily_all(code)

def query_twse_daily_all(code: Optional[str] = None) -> pd.DataFrame:
    """查詢全市場當日行情（優先本地快取）"""
    start_time = time.time()
    local = _read_twse_local("daily_all")
    if local is not None:
        if code:
            col = "Code" if "Code" in local.columns else local.columns[0]
            local = local[local[col].astype(str) == str(code)]
        add_history("工具", {"type": "twse_daily", "code": code, "source": "local"})
        return local
    main_logger.info(f"查詢 TWSE 當日行情 [API]: {code if code else '全市場'}")
    try:
        result = _cached_twse_daily(code)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_daily_all", elapsed_ms)
        add_history("工具", {"type": "twse_daily", "code": code, "source": "api"})
        return result
    except Exception as e:
        main_logger.error(f"查詢 TWSE 當日行情失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_valuation(code: Optional[str]) -> pd.DataFrame:
    return sq.query_twse_bwibbu(code)

def query_twse_valuation(code: Optional[str] = None) -> pd.DataFrame:
    """查詢本益比/殖利率/股淨比（優先本地快取）"""
    start_time = time.time()
    local = _read_twse_local("valuation")
    if local is not None:
        if code:
            col = "Code" if "Code" in local.columns else local.columns[0]
            local = local[local[col].astype(str) == str(code)]
        add_history("工具", {"type": "twse_valuation", "code": code, "source": "local"})
        return local
    main_logger.info(f"查詢本益比/殖利率 [API]: {code if code else '全市場'}")
    try:
        result = _cached_twse_valuation(code)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_valuation", elapsed_ms)
        add_history("工具", {"type": "twse_valuation", "code": code, "source": "api"})
        return result
    except Exception as e:
        main_logger.error(f"查詢本益比失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_institutional(code: Optional[str]) -> pd.DataFrame:
    return sq.query_twse_institutional(code)

def query_twse_institutional(code: Optional[str] = None) -> pd.DataFrame:
    """查詢三大法人（優先本地快取）"""
    start_time = time.time()
    local = _read_twse_local("institutional")
    if local is not None:
        if code:
            col = "Code" if "Code" in local.columns else local.columns[0]
            local = local[local[col].astype(str) == str(code)]
        add_history("工具", {"type": "twse_institutional", "code": code, "source": "local"})
        return local
    main_logger.info(f"查詢三大法人 TWSE [API]: {code if code else '全市場'}")
    try:
        result = _cached_twse_institutional(code)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_institutional", elapsed_ms)
        add_history("工具", {"type": "twse_institutional", "code": code, "source": "api"})
        return result
    except Exception as e:
        main_logger.error(f"查詢三大法人 TWSE 失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_margin() -> pd.DataFrame:
    return sq.query_twse_margin()

def query_twse_margin() -> pd.DataFrame:
    """查詢融資融券彙總（優先本地快取）"""
    start_time = time.time()
    local = _read_twse_local("margin")
    if local is not None:
        add_history("工具", {"type": "twse_margin", "source": "local"})
        return local
    main_logger.info("查詢融資融券彙總 [API]")
    try:
        result = _cached_twse_margin()
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_margin", elapsed_ms)
        add_history("工具", {"type": "twse_margin", "source": "api"})
        return result
    except Exception as e:
        main_logger.error(f"查詢融資融券彙總失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_company(code: str) -> pd.DataFrame:
    return sq.query_twse_company(code)

def query_twse_company(code: str) -> pd.DataFrame:
    """查詢公司基本資料"""
    start_time = time.time()
    main_logger.info(f"查詢 TWSE 公司基本資料: {code}")
    try:
        result = _cached_twse_company(code)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_company", elapsed_ms)
        add_history("台股市場", {"type": "twse_company", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢公司基本資料失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_disposition() -> pd.DataFrame:
    return sq.query_twse_disposition()

def query_twse_disposition() -> pd.DataFrame:
    """查詢處置有價證券清單（優先本地快取）"""
    start_time = time.time()
    local = _read_twse_local("disposition")
    if local is not None:
        add_history("台股市場", {"type": "twse_disposition", "source": "local"})
        return local
    main_logger.info("查詢 TWSE 處置股清單 [API]")
    try:
        result = _cached_twse_disposition()
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_disposition", elapsed_ms)
        add_history("台股市場", {"type": "twse_disposition", "source": "api"})
        return result
    except Exception as e:
        main_logger.error(f"查詢處置股失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_notice() -> pd.DataFrame:
    return sq.query_twse_notice()

def query_twse_notice() -> pd.DataFrame:
    """查詢注意有價證券清單（優先本地快取）"""
    start_time = time.time()
    local = _read_twse_local("notice")
    if local is not None:
        add_history("台股市場", {"type": "twse_notice", "source": "local"})
        return local
    main_logger.info("查詢 TWSE 注意股清單 [API]")
    try:
        result = _cached_twse_notice()
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_twse_notice", elapsed_ms)
        add_history("台股市場", {"type": "twse_notice", "source": "api"})
        return result
    except Exception as e:
        main_logger.error(f"查詢注意股失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# TWSE 擴充查詢（新 OpenAPI 端點，5 分鐘緩存）
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_mi_index() -> pd.DataFrame:
    return sq.query_twse_mi_index()

def query_twse_mi_index() -> pd.DataFrame:
    try:
        r = _cached_twse_mi_index()
        add_history("TWSE", {"type": "twse_mi_index"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_stock_day_avg(code) -> pd.DataFrame:
    return sq.query_twse_stock_day_avg(code)

def query_twse_stock_day_avg(code=None) -> pd.DataFrame:
    try:
        r = _cached_twse_stock_day_avg(code)
        add_history("TWSE", {"type": "twse_stock_day_avg", "code": code})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_monthly(code) -> pd.DataFrame:
    return sq.query_twse_monthly(code)

def query_twse_monthly(code=None) -> pd.DataFrame:
    try:
        r = _cached_twse_monthly(code)
        add_history("TWSE", {"type": "twse_monthly", "code": code})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_annual(code) -> pd.DataFrame:
    return sq.query_twse_annual(code)

def query_twse_annual(code=None) -> pd.DataFrame:
    try:
        r = _cached_twse_annual(code)
        add_history("TWSE", {"type": "twse_annual", "code": code})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_qfiis_cat() -> pd.DataFrame:
    return sq.query_twse_qfiis_cat()

def query_twse_qfiis_cat() -> pd.DataFrame:
    try:
        r = _cached_twse_qfiis_cat()
        add_history("TWSE", {"type": "twse_qfiis_cat"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=300, show_spinner=False)
def _cached_twse_qfiis_top20() -> pd.DataFrame:
    return sq.query_twse_qfiis_top20()

def query_twse_qfiis_top20() -> pd.DataFrame:
    try:
        r = _cached_twse_qfiis_top20()
        add_history("TWSE", {"type": "twse_qfiis_top20"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_twse_newlisting() -> pd.DataFrame:
    return sq.query_twse_newlisting()

def query_twse_newlisting() -> pd.DataFrame:
    try:
        r = _cached_twse_newlisting()
        add_history("TWSE", {"type": "twse_newlisting"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_suspend_listing() -> pd.DataFrame:
    return sq.query_twse_suspend_listing()

def query_twse_suspend_listing() -> pd.DataFrame:
    try:
        r = _cached_twse_suspend_listing()
        add_history("TWSE", {"type": "twse_suspend_listing"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_apply_listing_local() -> pd.DataFrame:
    return sq.query_twse_apply_listing_local()

def query_twse_apply_listing_local() -> pd.DataFrame:
    try:
        r = _cached_twse_apply_listing_local()
        add_history("TWSE", {"type": "twse_apply_local"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_apply_listing_foreign() -> pd.DataFrame:
    return sq.query_twse_apply_listing_foreign()

def query_twse_apply_listing_foreign() -> pd.DataFrame:
    try:
        r = _cached_twse_apply_listing_foreign()
        add_history("TWSE", {"type": "twse_apply_foreign"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=1800, show_spinner=False)
def _cached_twse_news_list() -> pd.DataFrame:
    return sq.query_twse_news_list()

def query_twse_news_list() -> pd.DataFrame:
    try:
        r = _cached_twse_news_list()
        add_history("TWSE", {"type": "twse_news"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=1800, show_spinner=False)
def _cached_twse_event_list() -> pd.DataFrame:
    return sq.query_twse_event_list()

def query_twse_event_list() -> pd.DataFrame:
    try:
        r = _cached_twse_event_list()
        add_history("TWSE", {"type": "twse_events"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_dividend_policy() -> pd.DataFrame:
    return sq.query_twse_dividend_policy()

def query_twse_dividend_policy() -> pd.DataFrame:
    try:
        r = _cached_twse_dividend_policy()
        add_history("TWSE", {"type": "twse_dividend_policy"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_fund_basic() -> pd.DataFrame:
    return sq.query_twse_fund_basic()

def query_twse_fund_basic() -> pd.DataFrame:
    try:
        r = _cached_twse_fund_basic()
        add_history("TWSE", {"type": "twse_fund_basic"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_monthly_revenue() -> pd.DataFrame:
    return sq.query_twse_monthly_revenue()

def query_twse_monthly_revenue() -> pd.DataFrame:
    try:
        r = _cached_twse_monthly_revenue()
        add_history("TWSE", {"type": "twse_monthly_revenue"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_income_statement(industry: str) -> pd.DataFrame:
    return sq.query_twse_income_statement(industry)

def query_twse_income_statement(industry: str = "ci") -> pd.DataFrame:
    try:
        r = _cached_twse_income_statement(industry)
        add_history("TWSE", {"type": "twse_income_statement", "industry": industry})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_balance_sheet_openapi(industry: str) -> pd.DataFrame:
    return sq.query_twse_balance_sheet_openapi(industry)

def query_twse_balance_sheet_openapi(industry: str = "ci") -> pd.DataFrame:
    try:
        r = _cached_twse_balance_sheet_openapi(industry)
        add_history("TWSE", {"type": "twse_balance_sheet", "industry": industry})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_etf_rank() -> pd.DataFrame:
    return sq.query_twse_etf_rank()

def query_twse_etf_rank() -> pd.DataFrame:
    try:
        r = _cached_twse_etf_rank()
        add_history("TWSE", {"type": "twse_etf_rank"})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=86400, show_spinner=False)
def _cached_twse_esg(topic_id: int) -> pd.DataFrame:
    return sq.query_twse_esg(topic_id)

def query_twse_esg(topic_id: int) -> pd.DataFrame:
    try:
        r = _cached_twse_esg(topic_id)
        add_history("TWSE", {"type": "twse_esg", "topic_id": topic_id})
        return r
    except Exception as e:
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# 期貨與匯率相關查詢 (1 hour cache: FinMind data)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_futures_daily(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    return sq.query_futures_daily(code, start_str, end_str)

def query_futures_daily(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢期貨日行情"""
    start_time = time.time()
    main_logger.info(f"查詢期貨日行情: {code}, {start_date} ~ {end_date}")
    try:
        result = _cached_futures_daily(code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_futures_daily", elapsed_ms)
        add_history("期貨/匯率", {"type": "futures_daily", "code": code, "start": str(start_date), "end": str(end_date)})
        return result
    except Exception as e:
        main_logger.error(f"查詢期貨日行情失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_futures_institutional(code: str, start_str: str, end_str: str) -> pd.DataFrame:
    return sq.query_futures_institutional(code, start_str, end_str)

def query_futures_institutional(code: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢期貨三大法人"""
    start_time = time.time()
    main_logger.info(f"查詢期貨三大法人: {code}, {start_date} ~ {end_date}")
    try:
        result = _cached_futures_institutional(code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_futures_institutional", elapsed_ms)
        add_history("期貨/匯率", {"type": "futures_institutional", "code": code, "start": str(start_date), "end": str(end_date)})
        return result
    except Exception as e:
        main_logger.error(f"查詢期貨三大法人失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_exchange_rate(currency: str, start_str: str, end_str: str) -> pd.DataFrame:
    return sq.query_exchange_rate(currency, start_str, end_str)

def query_exchange_rate(currency: str, start_date: date, end_date: date) -> pd.DataFrame:
    """查詢匯率"""
    start_time = time.time()
    main_logger.info(f"查詢匯率: {currency}, {start_date} ~ {end_date}")
    try:
        result = _cached_exchange_rate(currency, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_exchange_rate", elapsed_ms)
        add_history("期貨/匯率", {"type": "exchange_rate", "currency": currency, "start": str(start_date), "end": str(end_date)})
        return result
    except Exception as e:
        main_logger.error(f"查詢匯率失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# Futu 相關查詢 (5 min cache: Market state)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def _cached_futu_market_state() -> pd.DataFrame:
    return sq.query_futu_market_state()

def query_futu_market_state() -> pd.DataFrame:
    """查詢全球主要市場開收盤狀態"""
    start_time = time.time()
    main_logger.info("查詢 Futu 全球市場狀態")
    try:
        result = _cached_futu_market_state()
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_futu_market_state", elapsed_ms)
        return result
    except Exception as e:
        main_logger.error(f"查詢全球市場狀態失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# 新聞相關查詢 (1 hour cache: News updates)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_stock_news(code: str, limit: int) -> pd.DataFrame:
    result = sq.query_news(code, limit)
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

def query_stock_news(code: str, limit: int = 10) -> pd.DataFrame:
    """查詢個股新聞"""
    start_time = time.time()
    main_logger.info(f"查詢個股新聞: {code}, limit={limit}")
    try:
        result = _cached_stock_news(code, limit)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_stock_news", elapsed_ms)
        main_logger.info(f"個股新聞查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("新聞", {"type": "stock_news", "code": code})
        return result
    except Exception as e:
        main_logger.error(f"查詢個股新聞失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_market_news(limit: int) -> pd.DataFrame:
    result = sq.query_news(None, limit)
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

def query_market_news(limit: int = 10) -> pd.DataFrame:
    """查詢大盤新聞"""
    start_time = time.time()
    main_logger.info(f"查詢大盤新聞, limit={limit}")
    try:
        result = _cached_market_news(limit)
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_market_news", elapsed_ms)
        main_logger.info(f"大盤新聞查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("新聞", {"type": "market_news"})
        return result
    except Exception as e:
        main_logger.error(f"查詢大盤新聞失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

# ══════════════════════════════════════════════════════════
# 帳務相關查詢（需 CA 憑證）
# ══════════════════════════════════════════════════════════

def query_positions() -> pd.DataFrame:
    """查詢庫存未實現損益"""
    start_time = time.time()
    main_logger.info(f"查詢庫存未實現損益")
    try:
        result = sq.query_positions("stock")
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_positions", elapsed_ms)
        main_logger.info(f"庫存查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("帳務", {"type": "positions"})
        return result
    except Exception as e:
        main_logger.error(f"查詢庫存失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

def query_profit_loss(start_date: date, end_date: date) -> pd.DataFrame:
    """查詢已實現損益"""
    start_time = time.time()
    main_logger.info(f"查詢已實現損益: {start_date} ~ {end_date}")
    try:
        result = sq.query_profit_loss(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_profit_loss", elapsed_ms)
        main_logger.info(f"已實現損益查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("帳務", {"type": "profit_loss"})
        return result
    except Exception as e:
        main_logger.error(f"查詢已實現損益失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

def query_account_balance() -> pd.DataFrame:
    """查詢帳戶餘額"""
    start_time = time.time()
    main_logger.info(f"查詢帳戶餘額")
    try:
        result = sq.query_account_balance()
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_account_balance", elapsed_ms)
        main_logger.info(f"帳戶餘額查詢完成, 耗時 {elapsed_ms:.1f}ms")
        add_history("帳務", {"type": "account_balance"})
        return pd.DataFrame({"帳戶餘額": [result]})
    except Exception as e:
        main_logger.error(f"查詢帳戶餘額失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

def query_trading_limits() -> pd.DataFrame:
    """查詢交易額度"""
    start_time = time.time()
    main_logger.info(f"查詢交易額度")
    try:
        result = sq.query_trading_limits()
        elapsed_ms = (time.time() - start_time) * 1000
        perf_tracker.record_query_time("query_trading_limits", elapsed_ms)
        main_logger.info(f"交易額度查詢完成: {len(result)} 筆, 耗時 {elapsed_ms:.1f}ms")
        add_history("帳務", {"type": "trading_limits"})
        return result
    except Exception as e:
        main_logger.error(f"查詢交易額度失敗: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})


# ══════════════════════════════════════════════════════════
# 非同步查詢支持 (Phase 6.1)
# ══════════════════════════════════════════════════════════

# 全局線程池（避免重複建立線程）
_executor = ThreadPoolExecutor(max_workers=5)

async def _run_sync_func(func: Callable, args: Tuple = (), kwargs: Dict = None) -> pd.DataFrame:
    """在線程池中運行同步函數，避免阻塞事件循環"""
    if kwargs is None:
        kwargs = {}
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))
        return result
    except Exception as e:
        main_logger.error(f"異步查詢失敗: {func.__name__}: {str(e)}")
        return pd.DataFrame({"錯誤": [str(e)]})

async def async_batch_query(queries: List[Dict[str, Any]]) -> List[pd.DataFrame]:
    """
    並行執行多個查詢（非同步版本）

    Args:
        queries: 查詢列表，每個查詢為 {
            "func": 查詢函數,
            "args": (位置參數元組),
            "kwargs": {關鍵字參數},
            "name": "查詢名稱（用於日誌）"
        }

    Returns:
        結果列表，按輸入順序排列

    Example:
        results = await async_batch_query([
            {"func": query_snapshot, "args": (["2330"],), "name": "TSMC"},
            {"func": query_snapshot, "args": (["2412"],), "name": "TSMC美ADR"}
        ])
    """
    batch_start = time.time()
    main_logger.info(f"開始異步批量查詢: {len(queries)} 個查詢")

    tasks = []
    for idx, query in enumerate(queries):
        func = query.get("func")
        args = query.get("args", ())
        kwargs = query.get("kwargs", {})
        name = query.get("name", f"查詢{idx+1}")

        if not callable(func):
            main_logger.warning(f"跳過非法查詢: {name} (函數無效)")
            tasks.append(None)
            continue

        main_logger.debug(f"[批量查詢 {idx+1}/{len(queries)}] {name}: {func.__name__}")
        task = asyncio.create_task(_run_sync_func(func, args, kwargs))
        tasks.append(task)

    # 並行執行所有查詢，不中斷
    results = await asyncio.gather(*[t for t in tasks if t is not None], return_exceptions=True)

    # 還原原始順序
    final_results = []
    result_idx = 0
    for idx, task in enumerate(tasks):
        if task is None:
            final_results.append(pd.DataFrame({"錯誤": ["無效查詢"]}))
        elif isinstance(results[result_idx], Exception):
            final_results.append(pd.DataFrame({"錯誤": [str(results[result_idx])]}))
            result_idx += 1
        else:
            final_results.append(results[result_idx])
            result_idx += 1

    batch_elapsed = (time.time() - batch_start) * 1000
    main_logger.info(f"異步批量查詢完成: {len(queries)} 個, 總耗時 {batch_elapsed:.1f}ms")
    return final_results

def batch_query_sync(queries: List[Dict[str, Any]]) -> List[pd.DataFrame]:
    """
    並行執行多個查詢（同步包裝）
    在 Streamlit 等不支持 async 的環境中使用
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            main_logger.warning("事件循環已執行，無法直接運行異步查詢，改用同步方式")
            return [q["func"](*q.get("args", ()), **q.get("kwargs", {})) for q in queries]
    except RuntimeError:
        pass

    # 創建新的事件循環並執行
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(async_batch_query(queries))
        return results
    finally:
        loop.close()

# ══════════════════════════════════════════════════════════
# 性能監控與報告
# ══════════════════════════════════════════════════════════

def get_performance_summary() -> Dict[str, Any]:
    """取得性能摘要"""
    return perf_tracker.get_summary()

def print_performance_summary():
    """列印性能摘要到日誌"""
    summary = perf_tracker.get_summary()
    main_logger.info("═" * 60)
    main_logger.info("性能監控摘要")
    main_logger.info("═" * 60)

    # 查詢時間統計
    if summary.get("query_times"):
        main_logger.info("查詢耗時統計:")
        for func, stats in summary["query_times"].items():
            main_logger.info(
                f"  {func}: 平均 {stats['avg']:.1f}ms, "
                f"最小 {stats['min']:.1f}ms, 最大 {stats['max']:.1f}ms, "
                f"總次數 {stats['count']}"
            )

    # 緩存命中率
    if summary.get("cache_stats"):
        main_logger.info("緩存命中率:")
        for func, stats in summary["cache_stats"].items():
            main_logger.info(
                f"  {func}: {stats['hit_rate']:.1f}% "
                f"({stats['hits']} hits, {stats['misses']} misses)"
            )

    # API 調用統計
    if summary.get("api_calls"):
        main_logger.info("API 調用統計:")
        for api, count in summary["api_calls"].items():
            main_logger.info(f"  {api}: {count} 次")

    main_logger.info("═" * 60)

def save_performance_report(filepath=None):
    """儲存性能報告到檔案"""
    from pathlib import Path
    perf_tracker.save_report(filepath)
    if filepath is None:
        filepath = Path.home() / ".app_config" / "logs" / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    main_logger.info(f"性能報告已儲存至: {filepath}")
