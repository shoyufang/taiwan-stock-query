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

# 新分頁渲染器
from tabs.market_overview import render_market_overview
from tabs.stock_page import render_stock_page
from tabs.screener_hub import render_screener_hub
from tabs.global_markets import render_global_markets
from tabs.calendar_tab import render_calendar_tab

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
    st.session_state.selected_tab = "市場總覽"
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

# ──────────────────────────────────────────────
# 導航架構（Phase A）
# ──────────────────────────────────────────────

# 一級導航：8 組
PRIMARY_TABS = [
    "市場總覽",
    "個股全景",
    "自選股",
    "選股中心",
    "全球市場",
    "投資行事曆",
    "AI 助理",
    "投資組合",
]

# 舊鍵 → 新鍵的相容映射（書籤/歷史點擊能正確導向）
TAB_COMPAT_MAP = {
    "儀表板": "市場總覽",
    "台股市場": "台股市場",
    "技術分析": "技術分析",
    "TWSE": "TWSE",
    "DeepSeek AI": "AI 助理",
    "🇺🇸 美股專區": "全球市場",
    "📅 美股日曆 & 共識": "全球市場",
    "FinMind": "FinMind",
    "期貨/匯率": "全球市場",
    "選股": "選股中心",
    "新聞": "新聞",
    "📈 技術掃描器": "選股中心",
    "👁️ 自選股監控": "自選股",
    "💼 投資組合": "投資組合",
    "📄 PDF 報告": "PDF 報告",
    "工具": "工具",
    "⚡ 效能監控": "效能監控",
}

# 進階查詢群組（舊分頁，收進 expander）
ADVANCED_TABS = ["台股市場", "TWSE", "FinMind", "技術分析", "期貨/匯率", "新聞"]

# 設定與工具群組
UTILITY_TABS = ["工具", "PDF 報告", "效能監控"]


# ──────────────────────────────────────────────
# Tab 渲染器分發對照表
# ──────────────────────────────────────────────

def _render_technical_scanner():
    return __import__("tabs.technical_scanner", fromlist=["render_technical_scanner"]).render_technical_scanner()

def _render_watchlist_monitor():
    return __import__("tabs.watchlist_monitor", fromlist=["render_watchlist_monitor"]).render_watchlist_monitor()

def _render_portfolio_tracker():
    return __import__("tabs.portfolio_tracker", fromlist=["render_portfolio_tracker"]).render_portfolio_tracker()

def _render_pdf_export():
    return __import__("tabs.pdf_export", fromlist=["render_pdf_export"]).render_pdf_export()

def _render_health_monitor():
    return __import__("tabs.health_monitor", fromlist=["render_health_monitor"]).render_health_monitor()


TAB_RENDERERS = {
    # 新分頁
    "市場總覽": render_market_overview,
    "個股全景": render_stock_page,
    "自選股": _render_watchlist_monitor,
    "選股中心": render_screener_hub,
    "全球市場": render_global_markets,
    "投資行事曆": render_calendar_tab,
    "AI 助理": render_deepseek_chat,
    "投資組合": _render_portfolio_tracker,
    # 舊分頁（進階查詢 / 設定工具）
    "台股市場": render_taistock_market,
    "技術分析": render_technical_analysis,
    "TWSE": render_twse_section,
    "FinMind": render_finmind,
    "期貨/匯率": render_futures_forex,
    "新聞": render_news,
    "工具": render_tools,
    "PDF 報告": _render_pdf_export,
    "效能監控": _render_health_monitor,
    # 舊鍵相容映射（書籤/歷史點擊）
    "儀表板": render_market_overview,
}


def _resolve_tab(key: str) -> str:
    """相容映射：舊 tab 鍵 → 新 tab 鍵"""
    return TAB_COMPAT_MAP.get(key, key)


# ──────────────────────────────────────────────
# 側邊欄
# ──────────────────────────────────────────────

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

    # ── 看盤 ──
    st.markdown(
        '<p style="font-size:0.68rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;'
        'color:var(--claude-text-2);margin:8px 0 4px 2px;">看盤</p>',
        unsafe_allow_html=True
    )
    for t in ["市場總覽", "個股全景", "自選股"]:
        _nav_btn(t)

    # ── 決策 ──
    st.markdown(
        '<p style="font-size:0.68rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;'
        'color:var(--claude-text-2);margin:8px 0 4px 2px;">決策</p>',
        unsafe_allow_html=True
    )
    for t in ["選股中心", "全球市場", "投資行事曆"]:
        _nav_btn(t)

    # ── 管理 ──
    st.markdown(
        '<p style="font-size:0.68rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;'
        'color:var(--claude-text-2);margin:8px 0 4px 2px;">管理</p>',
        unsafe_allow_html=True
    )
    for t in ["AI 助理", "投資組合"]:
        _nav_btn(t)

    st.divider()

    # ── 🗂️ 進階查詢 ──
    with st.expander("🗂️ 進階查詢", expanded=False):
        for t in ADVANCED_TABS:
            if t in TAB_RENDERERS:
                _nav_btn(t)

    # ── ⚙️ 設定與工具 ──
    with st.expander("⚙️ 設定與工具", expanded=False):
        for t in UTILITY_TABS:
            if t in TAB_RENDERERS:
                _nav_btn(t)

    st.divider()

    # 系統設定彈窗
    with st.popover("⚙️ 系統設定", use_container_width=True):
        st.session_state.config = render_settings_panel(st.session_state.config, in_sidebar=False)

    st.divider()

    # 健康檢查狀態
    st.markdown("### 🏥 系統狀態")
    with st.expander("健康檢查", expanded=False):
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

    st.divider()

    # 預加載狀態
    st.caption(f"📦 {preload_manager.get_status_summary()}")


# ──────────────────────────────────────────────
# 快速保存結果功能
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# 書籤管理區域
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# 查詢歷史區域
# ──────────────────────────────────────────────
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


# ──────────────────────────────────────────────
# 處理書籤/歷史執行
# ──────────────────────────────────────────────
if st.session_state.execute_bookmark:
    st.info(f"正在執行書籤: {st.session_state.execute_bookmark['name']}")
    st.session_state.execute_bookmark = None
elif st.session_state.execute_history:
    st.info(f"正在重複查詢: {st.session_state.execute_history['tab']}")
    execute_from_history(st.session_state.execute_history)
    st.session_state.execute_history = None

# ──────────────────────────────────────────────
# 全域搜尋列（移到側邊欄後已移除主畫面搜尋）
# ──────────────────────────────────────────────
# Phase B.3 將在市場總覽內嵌入搜尋，此處不再顯示


# ──────────────────────────────────────────────
# 執行主要渲染
# ──────────────────────────────────────────────
selected_tab = st.session_state.selected_tab
# 相容映射：若 session state 是舊鍵，自動轉換
selected_tab = _resolve_tab(selected_tab)
st.session_state.selected_tab = selected_tab

# 執行主要渲染
if selected_tab in TAB_RENDERERS:
    TAB_RENDERERS[selected_tab]()
else:
    st.title(f"📊 {selected_tab}")
    st.info("此頁面尚未實作，請選擇其他導航項目。")

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
