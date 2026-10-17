"""
錯誤處理裝飾器 — 統一 API 錯誤處理、重試機制、使用者提示
"""
import time
import functools
from logging_config import main_logger
from typing import Optional, Callable, Any
import streamlit as st


def handle_api_error(
    max_retries: int = 2,
    retry_delay: float = 1.0,
    fallback: Optional[Any] = None,
    show_user_message: bool = True,
    error_prefix: str = "查詢失敗"
):
    """
    統一 API 錯誤處理裝飾器
    
    Args:
        max_retries: 最大重試次數
        retry_delay: 重試間隔（秒）
        fallback: 失敗時的回傳值
        show_user_message: 是否顯示 Streamlit 錯誤提示
        error_prefix: 錯誤訊息前綴
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        main_logger.info(f"✅ {func.__name__} 重試成功 (attempt {attempt + 1})")
                    return result
                except Exception as e:
                    last_exception = e
                    main_logger.warning(
                        f"❌ {func.__name__} 失敗 (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                    )
                    if attempt < max_retries:
                        time.sleep(retry_delay)
            
            # 所有重試都失敗
            error_msg = f"{error_prefix}: {func.__name__} — {str(last_exception)}"
            main_logger.error(error_msg)
            
            if show_user_message:
                try:
                    st.error(f"⚠️ {error_msg}")
                except:
                    pass  # 可能不在 Streamlit 上下文中
            
            return fallback
        return wrapper
    return decorator


def safe_query(func_name: str = ""):
    """簡化版安全查詢裝飾器（預設 1 次重試，回傳空 DataFrame）"""
    import pandas as pd
    return handle_api_error(
        max_retries=1,
        retry_delay=0.5,
        fallback=pd.DataFrame(),
        error_prefix=func_name or "查詢"
    )
