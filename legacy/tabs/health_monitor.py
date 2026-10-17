"""
效能監控儀表板 — 顯示快取命中率、API 延遲、系統狀態
"""
import streamlit as st
import pandas as pd
import time
import os
from pathlib import Path
from logging_config import main_logger


def render_health_monitor():
    """渲染效能監控儀表板"""
    st.subheader("⚡ 系統效能監控")
    
    # 1. 快取統計
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📦 SQLite 快取大小", _get_cache_size())
    
    with col2:
        st.metric("📝 查詢歷史筆數", _get_history_count())
    
    with col3:
        st.metric("⭐ 書籤數量", _get_bookmark_count())
    
    st.divider()
    
    # 2. 檔案系統狀態
    st.subheader("📁 檔案系統狀態")
    
    file_stats = _get_file_stats()
    if not file_stats.empty:
        st.dataframe(file_stats, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # 3. 效能建議
    st.subheader("💡 效能建議")
    suggestions = _generate_suggestions()
    for suggestion in suggestions:
        st.info(suggestion)


def _get_cache_size() -> str:
    """取得 SQLite 快取大小"""
    try:
        cache_dir = Path.home() / ".app_config"
        cache_db = cache_dir / "cache.db"
        if cache_db.exists():
            size_bytes = cache_db.stat().st_size
            if size_bytes > 1024 * 1024:
                return f"{size_bytes / (1024*1024):.1f} MB"
            elif size_bytes > 1024:
                return f"{size_bytes / 1024:.1f} KB"
            return f"{size_bytes} B"
        return "未建立"
    except:
        return "無法讀取"


def _get_history_count() -> str:
    """取得查詢歷史筆數"""
    try:
        from config import load_history
        history = load_history()
        return str(len(history))
    except:
        return "無法讀取"


def _get_bookmark_count() -> str:
    """取得書籤數量"""
    try:
        from config import load_bookmarks
        bookmarks = load_bookmarks()
        return str(len(bookmarks))
    except:
        return "無法讀取"


def _get_file_stats() -> pd.DataFrame:
    """取得主要檔案統計"""
    stats = []
    
    # 檢查主要模組
    modules = [
        "app.py", "ui_components.py", "query_wrapper.py", 
        "sinopac_query.py", "theme.py", "error_handler.py"
    ]
    
    for module in modules:
        try:
            path = Path(module)
            if path.exists():
                size_kb = path.stat().st_size / 1024
                stats.append({
                    "檔案": module,
                    "大小 (KB)": f"{size_kb:.1f}",
                    "狀態": "✅ 存在"
                })
            else:
                stats.append({
                    "檔案": module,
                    "大小 (KB)": "-",
                    "狀態": "❌ 不存在"
                })
        except:
            stats.append({
                "檔案": module,
                "大小 (KB)": "-",
                "狀態": "⚠️ 錯誤"
            })
    
    return pd.DataFrame(stats)


def _generate_suggestions() -> list:
    """產生效能建議"""
    suggestions = []
    
    # 檢查快取大小
    try:
        cache_dir = Path.home() / ".app_config"
        cache_db = cache_dir / "cache.db"
        if cache_db.exists():
            size_mb = cache_db.stat().st_size / (1024 * 1024)
            if size_mb > 100:
                suggestions.append(f"⚠️ SQLite 快取已達 {size_mb:.1f} MB，建議定期清理舊資料")
    except:
        pass
    
    # 檢查 app.py 大小
    try:
        app_size = Path("app.py").stat().st_size / 1024
        if app_size > 200:
            suggestions.append(f"📝 app.py 已達 {app_size:.1f} KB，建議繼續拆分 tabs/ 子模組")
    except:
        pass
    
    if not suggestions:
        suggestions.append("✅ 系統狀態良好，無需特別優化")
    
    return suggestions
