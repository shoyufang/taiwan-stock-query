"""
券商提供查詢工具 - Streamlit Web UI 主程式
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Dict, Any
import sys
import threading
import asyncio

from config import load_config, save_config, load_bookmarks, load_history, add_history, add_bookmark, remove_bookmark
from ui_components import (
    display_result, render_sidebar_menu, render_bookmarks_section,
    render_history_section, render_settings_panel, date_input_section, code_input_section
)
import query_wrapper as qw
from logging_config import main_logger
from health_check import HealthChecker
from preload import PreloadManager, get_preload_summary
from theme import THEMES, inject_theme_css

# 導入分派路由與執行器
from dispatch import execute_from_history, execute_query_by_params, QUERY_DISPATCH

# 導入各 Tab 渲染器
from tabs.dashboard import render_dashboard
from tabs.taistock import render_taistock_market
from tabs.twse import render_twse_section
from tabs.finmind import render_finmind
from tabs.futures_forex import render_futures_forex
from tabs.hk_stocks import render_hk_us_stocks
from tabs.us_stocks import render_us_stocks
from tabs.news import render_news
from tabs.tools import render_tools
from tabs.ai_chat import render_deepseek_chat
from tabs.us_calendar_tab import render_us_calendar_consensus
from tabs.screener_tab import render_screener
from tabs.technical import render_technical_analysis

# Streamlit 配置
st.set_page_config(
    page_title="券商提供查詢工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 背景預載管理器
@st.cache_resource
def _get_preload_manager_obj():
    return PreloadManager()

@st.cache_resource
def _preload_kick_flag():
    return {"started": False}

def _kick_preload_background():
    flag = _preload_kick_flag()
    if flag["started"]:
        return
    flag["started"] = True
    main_logger.info("主畫面渲染完成，啟動背景預載執行緒...")

    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(preload_manager.run_all_preloads())
        except Exception as e:
            main_logger.warning(f"背景預加載執行出錯: {str(e)}")

    threading.Thread(target=_run, daemon=True).start()

preload_manager = _get_preload_manager_obj()

# 初始化 Session State
if "config" not in st.session_state:
    st.session_state.config = load_config()
if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = load_bookmarks()
if "history" not in st.session_state:
    st.session_state.history = load_history()
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "execute_bookmark" not in st.session_state:
    st.session_state.execute_bookmark = None
if "execute_history" not in st.session_state:
    st.session_state.execute_history = None
if "active_dashboard_query" not in st.session_state:
    st.session_state.active_dashboard_query = None
if "last_query" not in st.session_state:
    st.session_state.last_query = None
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = "DeepSeek AI"
if "deepseek_chat_history" not in st.session_state:
    st.session_state.deepseek_chat_history = []
if "_news_df" not in st.session_state:
    st.session_state["_news_df"] = None
if "_news_summary" not in st.session_state:
    st.session_state["_news_summary"] = None
if "_news_subject" not in st.session_state:
    st.session_state["_news_subject"] = ""
if "theme" not in st.session_state:
    st.session_state["theme"] = "🌅 Claude 暖橘"

# 注入當前主題的 CSS
inject_theme_css(st.session_state["theme"])
st.session_state["_theme_cfg"] = THEMES.get(st.session_state["theme"], THEMES["🌅 Claude 暖橘"])

# 導航按鈕與側邊欄設定
SINOPAC_TABS = ["儀表板", "台股市場", "技術分析"]
TWSE_TABS = ["TWSE"]
OTHER_TABS = ["DeepSeek AI", "🇺🇸 美股專區", "📅 美股日曆 & 共識", "FinMind", "期貨/匯率", "選股", "新聞", "📈 技術掃描器", "👁️ 自選股監控", "💼 投資組合", "📄 PDF 報告", "工具", "⚡ 效能監控"]

def _nav_btn(label: str, icon: str = ""):
    current = st.session_state.selected_tab
    display = f"{icon} {label}".strip() if icon else label
    btn_type = "primary" if current == label else "secondary"
    if st.button(display, key=f"nav_{label}", use_container_width=True, type=btn_type):
        st.session_state.selected_tab = label
        st.rerun()

with st.sidebar:
    # 主題切換器
    theme_names = list(THEMES.keys())
    st.markdown(
        '<p style="font-size:0.68rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;'
        'color:var(--claude-text-2);margin:4px 0 6px 2px;">🎨 介面主題</p>',
        unsafe_allow_html=True
    )
    cols_t = st.columns(len(theme_names))
    for i, tn in enumerate(theme_names):
        emoji = tn.split()[0]
        is_active = (tn == st.session_state.get("theme"))
        btn_type = "primary" if is_active else "secondary"
        if cols_t[i].button(emoji, key=f"theme_btn_{i}", type=btn_type, help=tn, use_container_width=True):
            st.session_state["theme"] = tn
            st.rerun()
    st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)
    st.divider()

    # 導航按鈕
    for t in SINOPAC_TABS:
        _nav_btn(t)
    for t in TWSE_TABS:
        _nav_btn(t)
    for t in OTHER_TABS:
        _nav_btn(t)

# 快速保存結果功能（在主內容區或側邊欄顯示）
if st.session_state.current_result is not None and not st.session_state.current_result.empty:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 💾 快速保存")
        quick_bookmark = st.text_input("快速書籤名稱", key="quick_bookmark")
        if st.button("💾 保存為書籤", key="quick_save"):
            if quick_bookmark:
                success = add_bookmark(
                    quick_bookmark,
                    st.session_state.selected_tab,
                    {"type": "quick_save"}
                )
                if success:
                    st.session_state.bookmarks = load_bookmarks()
                    st.success(f"✅ 書籤已保存")
                else:
                    st.error("❌ 書籤名稱已存在")
            else:
                st.warning("⚠️ 請輸入書籤名稱")

# 書籤管理區域
st.sidebar.markdown("---")
st.sidebar.markdown("### ⭐ 釘選功能")
bookmarks = st.session_state.bookmarks
if bookmarks:
    selected_bookmark = st.sidebar.selectbox(
        "選擇書籤",
        options=bookmarks,
        format_func=lambda x: x.get("name", "未命名"),
        key="bookmark_select",
        label_visibility="collapsed"
    )
    if st.sidebar.button("▶️ 執行書籤", key="run_bookmark"):
        if selected_bookmark:
            st.session_state.execute_bookmark = selected_bookmark
            st.rerun()
else:
    st.sidebar.caption("暫無書籤")

# 查詢歷史區域
st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 最近查詢")
history = st.session_state.history
if history:
    selected_history = st.sidebar.selectbox(
        "最近查詢",
        options=history[:10],
        format_func=lambda x: f"{x.get('tab', '')} - {x.get('timestamp', '')[:10]}",
        key="history_select",
        label_visibility="collapsed"
    )
    if st.sidebar.button("▶️ 重複查詢", key="repeat_history"):
        if selected_history:
            st.session_state.execute_history = selected_history
            st.rerun()
else:
    st.sidebar.caption("暫無歷史")

# 預加載狀態
st.sidebar.markdown("---")
preload_summary = preload_manager.get_status_summary()
st.sidebar.caption(f"📦 {preload_summary}")

# 系統設定彈窗
st.sidebar.markdown("---")
with st.sidebar.popover("⚙️ 系統設定", use_container_width=True):
    st.session_state.config = render_settings_panel(st.session_state.config, in_sidebar=False)

# 健康檢查狀態
st.sidebar.markdown("---")
st.sidebar.markdown("### 🏥 系統狀態")
with st.sidebar.expander("健康檢查", expanded=False):
    health_status = HealthChecker.get_health_status()
    col1, col2 = st.columns(2)
    with col1:
        ok, msg = health_status["shioaji"]
        st.write(f"**API 連線**")
        st.caption(msg)
    with col2:
        ok, msg = health_status["config"]
        st.write(f"**配置檢查**")
        st.caption(msg)
    ok, msg = health_status["filesystem"]
    st.write(f"**檔案系統**")
    st.caption(msg)
    st.divider()
    emoji, summary = HealthChecker.get_summary_status()
    st.metric("系統狀態", summary, emoji)
    st.divider()
    st.caption("🚀 v1.1 | Phase 7 智慧版")
    st.caption("✅ 非同步預載 | SQLite 快取 | DeepSeek AI")

# 處理書籤/歷史執行
if st.session_state.execute_bookmark:
    st.info(f"正在執行書籤: {st.session_state.execute_bookmark['name']}")
    st.session_state.execute_bookmark = None
elif st.session_state.execute_history:
    st.info(f"正在重複查詢: {st.session_state.execute_history['tab']}")
    execute_from_history(st.session_state.execute_history)
    st.session_state.execute_history = None

# 全域搜尋列（除 AI 和美股專區外都顯示）
selected_tab = st.session_state.selected_tab
if selected_tab not in ["DeepSeek AI", "🇺🇸 美股專區", "📅 美股日曆 & 共識"]:
    with st.container():
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            global_search = st.text_input(
                "🔍 快速搜尋",
                placeholder="輸入股票代號、中文名稱或功能...",
                label_visibility="collapsed",
                key="global_search"
            )
        with search_col2:
            st.markdown("<div style='height: 38px'></div>", unsafe_allow_html=True)
            if st.button("⚡ 快速查詢", use_container_width=True, key="quick_search_btn"):
                if global_search:
                    from stock_lookup import resolve_code
                    code = resolve_code(global_search)
                    if code:
                        st.session_state.quick_search_code = code
                        st.session_state.quick_search_raw = global_search
                        st.rerun()
                    else:
                        st.warning(f"找不到 '{global_search}' 對應的股票代號")

        if hasattr(st.session_state, 'quick_search_code') and st.session_state.get('quick_search_code'):
            code = st.session_state.quick_search_code
            raw = st.session_state.get('quick_search_raw', code)
            st.success(f"✅ 已解析: **{raw}** → **{code}**")
            try:
                result = qw.query_snapshot([code])
                if not result.empty:
                    display_result(result, f"快速搜尋 - {raw}")
            except Exception as e:
                st.warning(f"查詢失敗: {e}")
            st.session_state.quick_search_code = None
            st.session_state.quick_search_raw = None

# Tab 渲染器分發對照表
TAB_RENDERERS = {
    "儀表板": render_dashboard,
    "台股市場": render_taistock_market,
    "技術分析": render_technical_analysis,
    "TWSE": render_twse_section,
    "DeepSeek AI": render_deepseek_chat,
    "🇺🇸 美股專區": render_us_stocks,
    "📅 美股日曆 & 共識": render_us_calendar_consensus,
    "FinMind": render_finmind,
    "期貨/匯率": render_futures_forex,
    "選股": render_screener,
    "新聞": render_news,
    "工具": render_tools,
    "📈 技術掃描器": lambda: __import__("tabs.technical_scanner", fromlist=["render_technical_scanner"]).render_technical_scanner(),
    "👁️ 自選股監控": lambda: __import__("tabs.watchlist_monitor", fromlist=["render_watchlist_monitor"]).render_watchlist_monitor(),
    "💼 投資組合": lambda: __import__("tabs.portfolio_tracker", fromlist=["render_portfolio_tracker"]).render_portfolio_tracker(),
    "📄 PDF 報告": lambda: __import__("tabs.pdf_export", fromlist=["render_pdf_export"]).render_pdf_export(),
    "⚡ 效能監控": lambda: __import__("tabs.health_monitor", fromlist=["render_health_monitor"]).render_health_monitor(),
}

# 執行主要渲染
if selected_tab in ["DeepSeek AI", "🇺🇸 美股專區", "📅 美股日曆 & 共識"]:
    if selected_tab in TAB_RENDERERS:
        TAB_RENDERERS[selected_tab]()
else:
    st.title(f"📊 {selected_tab}")
    st.markdown("---")
    if selected_tab in TAB_RENDERERS:
        TAB_RENDERERS[selected_tab]()

# 一鍵釘選到儀表板首頁
if st.session_state.get("last_query") is not None:
    st.markdown("---")
    lq = st.session_state.last_query
    with st.expander(f"📌 釘選本次查詢「{lq.get('default_name')}」到儀表板首頁", expanded=False):
        col_name, col_btn = st.columns([3, 1])
        with col_name:
            bm_name = st.text_input("書籤自訂名稱", value=lq.get("default_name", ""), key="pin_bm_name")
        with col_btn:
            st.write("")
            st.write("")
            if st.button("💾 儲存並釘選", key="pin_bm_btn", type="primary", use_container_width=True):
                if bm_name:
                    from config import add_bookmark, load_bookmarks
                    success = add_bookmark(bm_name, lq["tab"], lq["params"])
                    if success:
                        st.session_state.bookmarks = load_bookmarks()
                        st.success(f"🎉 成功釘選「{bm_name}」到儀表板！")
                        st.session_state.last_query = None
                        st.rerun()
                    else:
                        st.error("❌ 書籤名稱已存在")
                else:
                    st.warning("⚠️ 請輸入書籤名稱")

# 主畫面渲染完成，啟動背景預載
_kick_preload_background()
