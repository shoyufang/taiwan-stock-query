"""
自選股即時監控 — 使用者輸入 watchlist，每 30 秒自動刷新快照
"""
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from logging_config import main_logger
import query_wrapper as qw
from ui_components import display_result


def render_watchlist_monitor():
    """渲染自選股即時監控"""
    st.subheader("👁️ 自選股即時監控")
    st.caption("輸入股票代號，每 30 秒自動刷新快照")
    
    # 初始化 session state
    if "watchlist_codes" not in st.session_state:
        st.session_state.watchlist_codes = []
    if "watchlist_data" not in st.session_state:
        st.session_state.watchlist_data = None
    if "watchlist_last_update" not in st.session_state:
        st.session_state.watchlist_last_update = None
    
    # 輸入區域
    col1, col2 = st.columns([3, 1])
    with col1:
        new_code = st.text_input(
            "新增股票代號",
            placeholder="例：2330, 2317, 2454",
            key="watchlist_input",
            label_visibility="collapsed"
        )
    with col2:
        if st.button("➕ 新增", use_container_width=True, key="watchlist_add"):
            if new_code:
                codes = [c.strip() for c in new_code.split(",") if c.strip()]
                for code in codes:
                    if code not in st.session_state.watchlist_codes:
                        st.session_state.watchlist_codes.append(code)
                st.rerun()
    
    # 顯示當前監控列表
    if st.session_state.watchlist_codes:
        st.markdown("---")
        st.markdown("**📋 監控列表**")
        
        # 顯示代號標籤
        cols = st.columns(min(len(st.session_state.watchlist_codes), 5))
        for idx, code in enumerate(st.session_state.watchlist_codes):
            with cols[idx % 5]:
                st.caption(f"🔹 {code}")
        
        # 移除按鈕
        col_remove1, col_remove2 = st.columns([4, 1])
        with col_remove2:
            if st.button("🗑️ 清空列表", use_container_width=True, key="watchlist_clear"):
                st.session_state.watchlist_codes = []
                st.session_state.watchlist_data = None
                st.rerun()
        
        # 自動刷新控制
        col_auto1, col_auto2 = st.columns([3, 1])
        with col_auto2:
            auto_refresh = st.checkbox("⏱️ 自動刷新", value=True, key="watchlist_auto_refresh")
        
        if auto_refresh:
            _auto_refresh_watchlist()
        else:
            if st.button("🔄 手動刷新", type="primary", use_container_width=True, key="watchlist_manual_refresh"):
                _refresh_watchlist_data()
        
        # 顯示資料
        if st.session_state.watchlist_data is not None:
            display_result(st.session_state.watchlist_data, "自選股監控")
            if st.session_state.watchlist_last_update:
                st.caption(f"⏱️ 最後更新: {st.session_state.watchlist_last_update}")


def _auto_refresh_watchlist():
    """自動刷新監控資料"""
    # 使用 st.fragment 實現局部刷新
    _refresh_fragment()


@st.fragment(run_every=30)
def _refresh_fragment():
    """30 秒自動刷新片段"""
    _refresh_watchlist_data()


def _refresh_watchlist_data():
    """刷新監控資料"""
    if not st.session_state.watchlist_codes:
        return
    
    try:
        codes = st.session_state.watchlist_codes
        main_logger.info(f"刷新自選股監控: {codes}")
        
        # 查詢快照
        result = qw.query_snapshot(codes)
        
        if not result.empty:
            st.session_state.watchlist_data = result
            st.session_state.watchlist_last_update = datetime.now().strftime("%H:%M:%S")
        else:
            st.warning("無法獲取監控資料")
    except Exception as e:
        main_logger.error(f"自選股監控刷新失敗: {e}")
        st.error(f"刷新失敗: {e}")
