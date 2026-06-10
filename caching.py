import functools
import time
import hashlib
import json
from datetime import date, datetime
import pandas as pd
from logging_config import main_logger
from sqlite_cache import get_cache, set_cache

# 動態偵測 Streamlit 是否可用
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

def cached_query(ttl: int = 3600, sqlite_ttl: int | None = None, name: str | None = None):
    """
    ttl: Streamlit cache_data 記憶體快取秒數
    sqlite_ttl: SQLite 永久快取秒數（None = 不落地）
    name: 快取鍵前綴，預設使用函數名稱
    """
    def decorator(func):
        func_name = name or func.__name__
        
        def _get_cache_key(*args, **kwargs):
            # 序列化參數為基本型別
            def serialize_val(v):
                if isinstance(v, (date, datetime)):
                    return v.isoformat()
                return v
            
            serializable_args = [serialize_val(a) for a in args]
            serializable_kwargs = {k: serialize_val(v) for k, v in sorted(kwargs.items())}
            
            params_str = json.dumps([serializable_args, serializable_kwargs], sort_keys=True)
            params_hash = hashlib.md5(params_str.encode("utf-8")).hexdigest()
            return f"{func_name}:{params_hash}"
            
        def _sqlite_and_api_fetch(*args, **kwargs):
            cache_key = _get_cache_key(*args, **kwargs)
            
            # 1. 查 SQLite
            if sqlite_ttl is not None:
                try:
                    cached_data = get_cache(cache_key)
                    if cached_data is not None:
                        main_logger.debug(f"[SQLITE CACHE HIT] {func_name}: {cache_key}")
                        return cached_data
                except Exception as e:
                    main_logger.warning(f"[SQLITE CACHE ERROR] 讀取快取失敗 ({func_name}): {str(e)}")
                    
            # 2. 呼叫原始 API
            main_logger.debug(f"[SQLITE CACHE MISS] {func_name}: {cache_key}")
            result = func(*args, **kwargs)
            
            # 3. 寫入 SQLite
            if sqlite_ttl is not None and result is not None and not result.empty:
                try:
                    set_cache(cache_key, result, ttl=sqlite_ttl)
                except Exception as e:
                    main_logger.warning(f"[SQLITE CACHE ERROR] 寫入快取失敗 ({func_name}): {str(e)}")
                
            return result
            
        # 在 decorator 初始化時裝飾 st.cache_data
        if HAS_STREAMLIT and hasattr(st, "cache_data") and st.cache_data is not None:
            st_cached_inner = st.cache_data(ttl=ttl, show_spinner=False)(_sqlite_and_api_fetch)
        else:
            st_cached_inner = _sqlite_and_api_fetch
            
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _get_cache_key(*args, **kwargs)
            
            # 由於此 wrapper 位於 Streamlit cache 外部，可用於檢測與記錄 Streamlit 緩存命中
            from query_wrapper import _check_cache_hit, _record_cache_hit
            is_st_hit = _check_cache_hit(func_name, cache_key)
            _record_cache_hit(func_name, cache_key, is_st_hit)
            
            return st_cached_inner(*args, **kwargs)
            
        return wrapper
    return decorator
