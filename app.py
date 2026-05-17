"""
券商提供查詢工具 - Streamlit Web UI
Phase 5.3: 添加日誌和性能追蹤
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Dict, Any
import sys

from config import load_config, save_config, load_bookmarks, load_history, add_history, add_bookmark, remove_bookmark
from ui_components import (
    display_result, render_sidebar_menu, render_bookmarks_section,
    render_history_section, render_settings_panel, date_input_section, code_input_section
)
import query_wrapper as qw
from logging_config import main_logger
from health_check import HealthChecker
from preload import PreloadManager, get_preload_summary
from gemini_engine import get_gemini_engine

# ══════════════════════════════════════════════════════════
# Streamlit 配置
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="券商提供查詢工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* ── Sidebar ── */
[data-testid="stSidebar"] { width: 260px; }
[data-testid="stSidebar"] .stButton button {
    border-radius: 8px;
    font-size: 0.9rem;
    padding: 6px 10px;
    transition: all 0.15s;
}

/* ── Chat input bar ── */
[data-testid="stChatInput"] {
    border-radius: 12px;
}
[data-testid="stChatInput"] textarea {
    font-size: 1rem;
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 4px 0;
}

/* ── Main title area ── */
h1 { font-size: 1.6rem !important; margin-bottom: 0 !important; }

/* ── Remove Streamlit default top padding on main ── */
.block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# 全局預加載管理器（緩存）
# ══════════════════════════════════════════════════════════

@st.cache_resource
def _get_preload_manager_obj():
    """只建立 PreloadManager 物件，不啟動執行緒（避免拖慢首次載入）"""
    return PreloadManager()

@st.cache_resource
def _preload_kick_flag():
    """全域旗標，確保預載執行緒只啟動一次"""
    return {"started": False}

def _kick_preload_background():
    """主畫面渲染完成後才呼叫；用 cache_resource 旗標保證只啟動一次"""
    import threading
    import asyncio
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

# 只建立物件，執行緒在主畫面渲染後才啟動
preload_manager = _get_preload_manager_obj()

# ══════════════════════════════════════════════════════════
# 初始化 Session State
# ══════════════════════════════════════════════════════════

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
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = "Gemini AI"
if "gemini_chat_history" not in st.session_state:
    st.session_state.gemini_chat_history = []
if "_news_df" not in st.session_state:
    st.session_state["_news_df"] = None
if "_news_summary" not in st.session_state:
    st.session_state["_news_summary"] = None
if "_news_subject" not in st.session_state:
    st.session_state["_news_subject"] = ""

# ══════════════════════════════════════════════════════════

# ==================== ALL FUNCTION DEFINITIONS ====================

def execute_from_history(history_item: Dict[str, Any]):
    """從歷史記錄執行查詢"""
    main_logger.info(f"從歷史記錄執行: {history_item.get('tab', '')} - {history_item.get('title', '')}")
    params = history_item.get("params", {})
    query_type = params.get("type", "")

    if not query_type:
        main_logger.warning(f"查詢類型不完整: {history_item}")
        st.warning("無法執行：查詢類型不完整")
        return

    with st.spinner("執行中..."):
        try:
            # 根據查詢類型執行對應的查詢
            if query_type == "ranking":
                ranking_type = params.get("ranking_type", "up")
                limit = params.get("limit", 10)
                result = qw.query_ranking(ranking_type, limit)
                st.session_state.current_result = result
                display_result(result, f"{history_item.get('tab', '')} - {ranking_type}")

            elif query_type == "snapshot":
                codes = params.get("codes", [])
                if codes:
                    result = qw.query_snapshot(codes)
                    st.session_state.current_result = result
                    display_result(result, "個股即時快照")

            elif query_type == "kbar":
                code = params.get("code", "")
                start = params.get("start", "")
                end = params.get("end", "")
                if code and start and end:
                    from datetime import datetime
                    start_date = datetime.strptime(start, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end, "%Y-%m-%d").date()
                    result = qw.query_daily_kbar(code, start_date, end_date)
                    st.session_state.current_result = result
                    display_result(result, f"{code} 日K")

            elif query_type == "ticks":
                code = params.get("code", "")
                query_date = params.get("date", "")
                if code and query_date:
                    from datetime import datetime
                    query_date_obj = datetime.strptime(query_date, "%Y-%m-%d").date()
                    result = qw.query_ticks(code, query_date_obj)
                    st.session_state.current_result = result
                    display_result(result, f"{code} 逐筆成交")

            elif query_type == "institutional":
                code = params.get("code", "")
                start = params.get("start", "")
                end = params.get("end", "")
                if code and start and end:
                    from datetime import datetime
                    start_date = datetime.strptime(start, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end, "%Y-%m-%d").date()
                    result = qw.query_institutional_investors(code, start_date, end_date)
                    st.session_state.current_result = result
                    display_result(result, f"{code} 三大法人明細")

            main_logger.info(f"歷史查詢執行完成: {query_type}")
            st.success("✅ 查詢執行完成")
        except Exception as e:
            main_logger.error(f"歷史查詢執行失敗: {query_type}, 錯誤: {str(e)}")
            st.error(f"❌ 執行失敗: {str(e)}")

# ══════════════════════════════════════════════════════════
# Tab 對應的查詢界面
# ══════════════════════════════════════════════════════════

@st.fragment(run_every=30)
def render_dashboard_fragment():
    """儀表板自動刷新部分 (Task 7.3/7.4)"""
    
    st.subheader("🌍 全球市場狀態")
    try:
        market_state = qw.query_futu_market_state()
        if not market_state.empty:
            # 簡單顯示關鍵市場
            hk = market_state[market_state["市場"] == "market_hk"]["狀態"].values[0]
            us = market_state[market_state["市場"] == "market_us"]["狀態"].values[0]
            sz = market_state[market_state["市場"] == "market_sz"]["狀態"].values[0]
            
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            mcol1.metric("香港市場", hk, delta=None)
            mcol2.metric("美國市場", us, delta=None)
            mcol3.metric("深圳市場", sz, delta=None)
            
            # 嘗試增加台股大盤 (2330 作為指標)
            try:
                tw_snap = qw.query_snapshot(["2330"])
                if not tw_snap.empty:
                    price = tw_snap["收盤"].values[0]
                    change = tw_snap["漲跌"].values[0]
                    mcol4.metric("台股指標 (2330)", f"{price}", delta=f"{change}")
            except:
                pass
        else:
            st.info("無法獲取市場狀態")
    except Exception as e:
        st.caption(f"Futu 連線中... ({str(e)})")

    st.divider()
    
    # 熱門監控 (基於動態預載名單)
    st.subheader("🔥 關注名單即時監控")
    watchlist = preload_manager.frequent_queries["snapshots"]
    
    try:
        snapshot = qw.query_snapshot(watchlist)
        if not snapshot.empty:
            # 轉置一下方便看
            display_df = snapshot[["代號", "收盤", "漲跌", "漲跌幅%", "成交量"]].copy()
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("目前無關注名單數據")
    except Exception as e:
        st.error(f"監控數據獲取失敗: {str(e)}")
    
    st.caption(f"⏱️ 最後更新時間: {datetime.now().strftime('%H:%M:%S')} (每 30 秒自動刷新)")

def render_dashboard():
    """整合儀表板首頁 (Task 7.4)"""
    main_logger.info("渲染儀表板 Tab")
    st.markdown("### 📊 跨市場專業儀表板")
    render_dashboard_fragment()
    
    # 底部快速導航
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📈 查台股排行", use_container_width=True):
            st.info("請點選左側『台股市場』標籤")
    with col2:
        if st.button("🚀 查港美股K線", use_container_width=True):
            st.info("請點選左側『港美股』標籤")
    with col3:
        if st.button("📂 查看查詢歷史", use_container_width=True):
            st.info("請查看左側側邊欄『最近查詢』")

@st.fragment(run_every=30)
def render_snapshot_fragment(codes):
    """即時快照自動刷新片段 (Task 7.3)"""
    if codes:
        result = qw.query_snapshot(codes)
        st.session_state.current_result = result
        display_result(result, "個股即時快照")
        st.caption(f"⏱️ 自動刷新中... 最後更新: {datetime.now().strftime('%H:%M:%S')}")
    else:
        st.warning("請輸入至少一個股票代號")

def _qbtn_grid(options: list, state_key: str, n_cols: int = 4) -> str:
    """按鈕選單格：顯示 n_cols 欄的選項按鈕，當前選中顯示 primary 樣式，回傳選中項目。"""
    if state_key not in st.session_state or st.session_state[state_key] not in options:
        st.session_state[state_key] = options[0]
    current = st.session_state[state_key]
    cols = st.columns(n_cols)
    for i, opt in enumerate(options):
        with cols[i % n_cols]:
            if st.button(opt, key=f"{state_key}_{i}", use_container_width=True,
                         type="primary" if current == opt else "secondary"):
                st.session_state[state_key] = opt
                current = opt
    st.divider()
    return current


def render_taistock_market():
    """台股市場查詢"""
    main_logger.info("渲染台股市場 Tab")

    # 資料來源優先規則說明
    with st.expander("📋 資料來源優先規則", expanded=False):
        st.markdown("""
        | 優先 | 來源 | 說明 |
        |------|------|------|
        | 🥇 第一 | **Shioaji API** | 即時報價、排行、快照、日K |
        | 🥈 第二 | **TWSE 公開資訊站** | 當日全市場行情、三大法人、本益比 |
        | 🥉 最後 | **FinMind** | 歷史籌碼/基本面（有 2-3 週落後） |
        """)

    query_type = _qbtn_grid(
        ["漲幅排行", "跌幅排行", "成交量排行", "成交金額排行",
         "個股即時快照", "個股日K", "逐筆成交"],
        "taistock_q", n_cols=4
    )

    if query_type == "漲幅排行":
        st.subheader("📈 漲幅排行")
        col1, col2 = st.columns(2)
        with col1:
            count = st.slider("筆數", 5, 50, 10)
        with col2:
            st.info(f"取前 {count} 檔")
        if st.button("查詢", key="ranking_up"):
            with st.spinner("查詢中..."):
                result = qw.query_ranking("up", count)
                st.session_state.current_result = result
                display_result(result, "漲幅排行")

    elif query_type == "跌幅排行":
        st.subheader("📉 跌幅排行")
        col1, col2 = st.columns(2)
        with col1:
            count = st.slider("筆數", 5, 50, 10)
        with col2:
            st.info(f"取後 {count} 檔")
        if st.button("查詢", key="ranking_down"):
            with st.spinner("查詢中..."):
                result = qw.query_ranking("down", count)
                st.session_state.current_result = result
                display_result(result, "跌幅排行")

    elif query_type == "成交量排行":
        st.subheader("📊 成交量排行")
        count = st.slider("筆數", 5, 50, 10)
        if st.button("查詢", key="ranking_volume"):
            with st.spinner("查詢中..."):
                result = qw.query_ranking("volume", count)
                st.session_state.current_result = result
                display_result(result, "成交量排行")

    elif query_type == "成交金額排行":
        st.subheader("💰 成交金額排行")
        count = st.slider("筆數", 5, 50, 10)
        if st.button("查詢", key="ranking_amount"):
            with st.spinner("查詢中..."):
                result = qw.query_ranking("amount", count)
                st.session_state.current_result = result
                display_result(result, "成交金額排行")

    elif query_type == "個股即時快照":
        st.subheader("📊 個股即時快照")
        codes = code_input_section("輸入股票代號", single=False)
        
        col1, col2 = st.columns([1, 4])
        with col1:
            auto_refresh = st.toggle("自動刷新", value=False, key="snapshot_auto_refresh")
        with col2:
            if auto_refresh:
                st.caption("⏱️ 每 30 秒自動更新數據")

        if not auto_refresh:
            if st.button("查詢", key="snapshot"):
                if codes:
                    with st.spinner("查詢中..."):
                        result = qw.query_snapshot(codes)
                        st.session_state.current_result = result
                        display_result(result, "個股即時快照")
                else:
                    st.warning("請輸入至少一個股票代號")
        else:
            # 使用 Fragment 進行自動刷新
            render_snapshot_fragment(codes)

    elif query_type == "個股日K":
        st.subheader("📈 個股日K")
        code = code_input_section("輸入股票代號")
        start_date, end_date = date_input_section()
        if st.button("查詢", key="kbar"):
            if code:
                with st.spinner("查詢中..."):
                    result = qw.query_daily_kbar(code, start_date, end_date)
                    st.session_state.current_result = result
                    display_result(result, f"{code} 日K")
            else:
                st.warning("請輸入股票代號")

    elif query_type == "逐筆成交":
        st.subheader("📝 逐筆成交")
        code = code_input_section("輸入股票代號")
        query_date = st.date_input("選擇日期", date.today())
        if st.button("查詢", key="ticks"):
            if code:
                with st.spinner("查詢中..."):
                    result = qw.query_ticks(code, query_date)
                    st.session_state.current_result = result
                    display_result(result, f"{code} 逐筆成交")
            else:
                st.warning("請輸入股票代號")



# ── TWSE dispatch helper（模組層級，供批次查詢用） ──────────────
_TWSE_ESG_MAP = {
    1: "溫室氣體排放", 2: "能源管理", 3: "用水管理", 4: "廢棄物管理",
    5: "人力資源發展", 6: "董事會", 7: "投資人溝通", 8: "氣候相關議題管理",
    9: "功能性委員會", 10: "燃料管理", 11: "產品生命週期管理", 12: "食品安全",
    13: "供應鏈管理", 14: "產品品質與安全", 15: "社區關係", 16: "資訊安全",
    17: "普惠金融", 18: "股權與控制", 19: "風險管理政策",
    20: "反競爭行為法律爭議", 21: "職業安全衛生",
}
_TWSE_ESG_REV = {v: k for k, v in _TWSE_ESG_MAP.items()}
_TWSE_IND_MAP = {
    "綜合損益表(一般業)": "ci",  "綜合損益表(金融業)": "basi",
    "綜合損益表(證券期貨)": "bd", "綜合損益表(金控保險)": "fh",
    "綜合損益表(KY外國)": "mim", "綜合損益表(保險業)": "ins",
}
_TWSE_BS_MAP = {"資產負債表(一般業)": "ci", "資產負債表(KY外國)": "mim"}


def _twse_dispatch(qt: str, code: str = "") -> tuple:
    """根據項目名稱執行對應 TWSE 查詢，回傳 (result, needs_code)。"""
    c = code.strip() or None
    if qt == "當日全市場行情":    return qw.query_twse_daily_all(c), False
    if qt == "月均價":            return qw.query_twse_stock_day_avg(c), False
    if qt == "月成交資訊":        return qw.query_twse_monthly(c), False
    if qt == "年成交資訊":        return qw.query_twse_annual(c), False
    if qt == "大盤指數":          return qw.query_twse_mi_index(), False
    if qt == "當日三大法人":      return qw.query_twse_institutional(c), False
    if qt == "融資融券彙總":      return qw.query_twse_margin(), False
    if qt == "外資持股(產業)":    return qw.query_twse_qfiis_cat(), False
    if qt == "外資持股前20":      return qw.query_twse_qfiis_top20(), False
    if qt == "本益比/殖利率":     return qw.query_twse_valuation(c), False
    if qt == "公司基本資料":
        if not c:
            return {"error": "⚠️ 公司基本資料需輸入股票代號"}, True
        return qw.query_twse_company(c), True
    if qt == "最近上市":          return qw.query_twse_newlisting(), False
    if qt == "下市公司":          return qw.query_twse_suspend_listing(), False
    if qt == "申請上市(國內)":    return qw.query_twse_apply_listing_local(), False
    if qt == "申請上市(外國)":    return qw.query_twse_apply_listing_foreign(), False
    if qt == "處置股清單":        return qw.query_twse_disposition(), False
    if qt == "注意股清單":        return qw.query_twse_notice(), False
    if qt == "官方新聞":          return qw.query_twse_news_list(), False
    if qt == "活動公告":          return qw.query_twse_event_list(), False
    if qt == "月營收彙總":        return qw.query_twse_monthly_revenue(), False
    if qt == "股利分派":          return qw.query_twse_dividend_policy(), False
    if qt == "基金基本資訊":      return qw.query_twse_fund_basic(), False
    if qt in _TWSE_IND_MAP:       return qw.query_twse_income_statement(_TWSE_IND_MAP[qt]), False
    if qt in _TWSE_BS_MAP:        return qw.query_twse_balance_sheet_openapi(_TWSE_BS_MAP[qt]), False
    if qt == "ETF定期定額排行":   return qw.query_twse_etf_rank(), False
    if qt in _TWSE_ESG_REV:       return qw.query_twse_esg(_TWSE_ESG_REV[qt]), False
    return {"error": f"未知項目：{qt}"}, False


def render_twse_section():
    """TWSE 證交所查詢（OpenAPI 全端點）—— 複選批次模式"""
    main_logger.info("渲染 TWSE Tab")

    GROUPS = [
        ("📊 行情資訊",   ["當日全市場行情", "月均價", "月成交資訊", "年成交資訊", "大盤指數"]),
        ("🏦 法人/籌碼",  ["當日三大法人", "融資融券彙總", "外資持股(產業)", "外資持股前20"]),
        ("📈 估值",       ["本益比/殖利率"]),
        ("🏢 公司資訊",   ["公司基本資料", "最近上市", "下市公司", "申請上市(國內)", "申請上市(外國)"]),
        ("⚠️ 注意/處置", ["處置股清單", "注意股清單"]),
        ("📰 新聞公告",   ["官方新聞", "活動公告"]),
        ("💰 財報/股利",  ["月營收彙總", "股利分派", "基金基本資訊",
                           "綜合損益表(一般業)", "綜合損益表(金融業)", "綜合損益表(證券期貨)",
                           "綜合損益表(金控保險)", "綜合損益表(KY外國)", "綜合損益表(保險業)",
                           "資產負債表(一般業)", "資產負債表(KY外國)"]),
        ("📊 ETF",        ["ETF定期定額排行"]),
        ("🌱 ESG揭露",    ["溫室氣體排放", "能源管理", "用水管理", "廢棄物管理",
                           "人力資源發展", "董事會", "投資人溝通", "氣候相關議題管理",
                           "功能性委員會", "燃料管理", "產品生命週期管理", "食品安全",
                           "供應鏈管理", "產品品質與安全", "社區關係", "資訊安全",
                           "普惠金融", "股權與控制", "風險管理政策", "反競爭行為法律爭議", "職業安全衛生"]),
    ]

    # ── 上半：複選 Checkbox（左右 2 欄） ─────────────────────
    with st.container(border=True):
        col_left, col_right = st.columns(2)
        half = (len(GROUPS) + 1) // 2
        for gi, (caption, options) in enumerate(GROUPS):
            with col_left if gi < half else col_right:
                hc1, hc2 = st.columns([4, 1])
                with hc1:
                    st.caption(caption)
                with hc2:
                    if st.button("全選", key=f"twse_selall_{gi}",
                                 use_container_width=True):
                        for oi in range(len(options)):
                            st.session_state[f"twse_cb_{gi}_{oi}"] = True
                for oi, opt in enumerate(options):
                    st.checkbox(opt, key=f"twse_cb_{gi}_{oi}")

    # ── 篩選代號輸入 + 確認按鈕 ─────────────────────────────
    param_col, btn_col = st.columns([3, 1])
    with param_col:
        code_filter = st.text_input(
            "篩選代號", placeholder="例：2330（留空查全市場）",
            key="twse_batch_code", label_visibility="collapsed",
        )
    with btn_col:
        run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True)

    # 勾選摘要
    selected = [
        opt
        for gi, (_, options) in enumerate(GROUPS)
        for oi, opt in enumerate(options)
        if st.session_state.get(f"twse_cb_{gi}_{oi}", False)
    ]
    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected[:8])}{'…' if len(selected) > 8 else ''}")

    st.divider()

    # ── 下半：批次執行 + 結果統一顯示 ──────────────────────
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result, _ = _twse_dispatch(item, code_filter)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["twse_batch_results"] = results

    for item, result in st.session_state.get("twse_batch_results", []):
        with st.expander(f"📋 {item}", expanded=True):
            display_result(result, item)


def _finmind_dispatch(qt: str, code: str, start_date, end_date):
    """根據項目名稱執行對應 FinMind 查詢。"""
    if qt == "三大法人明細":  return qw.query_institutional_investors(code, start_date, end_date)
    if qt == "當沖交易量":    return qw.query_day_trading_volume(code, start_date, end_date)
    if qt == "融資融券餘額":  return qw.query_margin_short(code, start_date, end_date)
    if qt == "外資持股比例":  return qw.query_foreign_shareholding(code, start_date, end_date)
    if qt == "借券成交":      return qw.query_securities_lending(code, start_date, end_date)
    if qt == "月營收":        return qw.query_month_revenue(code, start_date, end_date)
    if qt == "綜合損益表":    return qw.query_financial_statement(code, start_date, end_date)
    if qt == "資產負債表":    return qw.query_balance_sheet(code, start_date, end_date)
    if qt == "股利政策":      return qw.query_dividend(code, start_date, end_date)
    return {"error": f"未知項目：{qt}"}


def render_finmind():
    """FinMind 查詢 —— 複選批次模式"""
    main_logger.info("渲染 FinMind Tab")

    CHIP_ITEMS = ["三大法人明細", "當沖交易量", "融資融券餘額", "外資持股比例", "借券成交"]
    FUND_ITEMS = ["月營收", "綜合損益表", "資產負債表", "股利政策"]

    # ── 上半：複選區（左=籌碼面，右=基本面，兩者均需日期） ──
    with st.container(border=True):
        col_left, col_right = st.columns(2)

        with col_left:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📌 籌碼面（需股票代號＋日期）")
            with hc2:
                if st.button("全選", key="fm_all_chip", use_container_width=True):
                    for i in range(len(CHIP_ITEMS)):
                        st.session_state[f"fm_cb_chip_{i}"] = True
            for i, opt in enumerate(CHIP_ITEMS):
                st.checkbox(opt, key=f"fm_cb_chip_{i}")

        with col_right:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📌 基本面（需股票代號＋日期）")
            with hc2:
                if st.button("全選", key="fm_all_fund", use_container_width=True):
                    for i in range(len(FUND_ITEMS)):
                        st.session_state[f"fm_cb_fund_{i}"] = True
            for i, opt in enumerate(FUND_ITEMS):
                st.checkbox(opt, key=f"fm_cb_fund_{i}")

    # ── 共用參數（所有項目均需代號＋日期） ─────────────────
    code = code_input_section()
    start_date, end_date = date_input_section(default_days=365)

    # 勾選摘要
    selected = (
        [opt for i, opt in enumerate(CHIP_ITEMS) if st.session_state.get(f"fm_cb_chip_{i}", False)] +
        [opt for i, opt in enumerate(FUND_ITEMS)  if st.session_state.get(f"fm_cb_fund_{i}",  False)]
    )
    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")

    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True,
                          key="fm_run_batch")

    st.divider()

    # ── 下半：批次執行 + 結果統一顯示 ───────────────────────
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        elif not code:
            st.warning("請輸入股票代號")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result = _finmind_dispatch(item, code, start_date, end_date)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["fm_batch_results"] = (results, code)

    stored = st.session_state.get("fm_batch_results")
    if stored:
        results, stored_code = stored
        for item, result in results:
            with st.expander(f"📋 {stored_code} — {item}", expanded=True):
                display_result(result, f"{stored_code} {item}")

def render_futures_forex():
    """期貨/匯率 (Phase 7 實作完成)"""
    main_logger.info("渲染期貨/匯率 Tab")

    query_type = _qbtn_grid(
        ["期貨日行情", "期貨三大法人", "台銀匯率查詢"],
        "futures_q", n_cols=3
    )

    if query_type == "期貨日行情":
        st.subheader("📉 期貨日行情")
        code = st.selectbox("選擇品種", ["TX", "MTX"], help="TX: 大台, MTX: 小台")
        start_date, end_date = date_input_section(default_days=30)
        
        if st.button("查詢期貨行情", key="futures_daily"):
            with st.spinner("查詢中..."):
                result = qw.query_futures_daily(code, start_date, end_date)
                st.session_state.current_result = result
                display_result(result, f"{code} 期貨日行情")

    elif query_type == "期貨三大法人":
        st.subheader("🏦 期貨三大法人買賣超")
        code = st.selectbox("選擇品種", ["TX", "MTX"])
        start_date, end_date = date_input_section(default_days=30)
        
        if st.button("查詢法人部位", key="futures_inst"):
            with st.spinner("查詢中..."):
                result = qw.query_futures_institutional(code, start_date, end_date)
                st.session_state.current_result = result
                display_result(result, f"{code} 三大法人部位")

    elif query_type == "台銀匯率查詢":
        st.subheader("💱 台銀匯率查詢")
        currency = st.selectbox(
            "選擇幣別", 
            ["USD", "JPY", "EUR", "CNY", "HKD", "GBP", "AUD", "CAD", "SGD", "ZAR"],
            index=0
        )
        start_date, end_date = date_input_section(default_days=30)
        
        if st.button("查詢匯率", key="exchange_rate"):
            with st.spinner("查詢中..."):
                result = qw.query_exchange_rate(currency, start_date, end_date)
                st.session_state.current_result = result
                display_result(result, f"{currency}/TWD 歷史匯率")

def render_hk_us_stocks():
    """港美股查詢 (Futu OpenAPI)"""
    main_logger.info("渲染港美股 Tab")
    st.info("港美股查詢需要本機運行 FutuOpenD (https://openapi.futunn.com)")

    query_type = _qbtn_grid(
        ["市場開收盤狀態", "港/美股日K", "股票基本資訊",
         "資金分布", "資金流向", "板塊列表", "板塊成分股", "股票所屬板塊"],
        "hkus_q", n_cols=4
    )

    if query_type == "市場開收盤狀態":
        st.subheader("🌍 全球市場開收盤狀態")
        if st.button("查詢市場狀態", key="futu_market_state"):
            with st.spinner("查詢中..."):
                try:
                    result = qw.query_futu_market_state()
                    st.session_state.current_result = result
                    if result is not None:
                        display_result(result, "全球市場開收盤狀態")
                        add_history({
                            "tab": "港美股",
                            "title": "市場開收盤狀態",
                            "params": {"type": "futu_market_state"}
                        })
                    else:
                        st.info("無市場狀態資料")
                except Exception as e:
                    st.error(f"查詢失敗: {str(e)}")

    elif query_type == "港/美股日K":
        st.subheader("📊 港/美股日K")
        col1, col2 = st.columns([1, 2])
        with col1:
            market = st.selectbox("選擇市場", ["HK", "US"], key="futu_market")
        with col2:
            code = st.text_input("輸入股票代號", placeholder="例：HK.00700（騰訊）或 US.AAPL", key="futu_kbar_code")

        start_date, end_date = date_input_section(default_days=365)

        if st.button("查詢K線", key="futu_kbar_btn"):
            if code:
                with st.spinner("查詢中..."):
                    try:
                        result = qw.query_futu_kbar(code, start_date, end_date)
                        st.session_state.current_result = result
                        if not result.empty:
                            display_result(result, f"{code} 日K ({start_date} ~ {end_date})")
                            add_history({
                                "tab": "港美股",
                                "title": f"{code} 日K",
                                "params": {"type": "futu_kbar", "code": code, "start": str(start_date), "end": str(end_date)}
                            })
                        else:
                            st.info("無K線資料")
                    except Exception as e:
                        st.error(f"查詢失敗: {str(e)}")
            else:
                st.warning("請輸入股票代號")

    elif query_type == "股票基本資訊":
        st.subheader("ℹ️ 股票基本資訊")
        market = st.selectbox("選擇市場", ["HK", "US"], key="futu_basicinfo_market")
        codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：HK.00700,HK.09988", key="futu_basicinfo_codes")

        if st.button("查詢基本資訊", key="futu_basicinfo_btn"):
            codes = [c.strip() for c in codes_str.split(",") if c.strip()]
            if codes:
                with st.spinner("查詢中..."):
                    try:
                        result = qw.query_futu_basicinfo(market, codes)
                        st.session_state.current_result = result
                        if result is not None:
                            display_result(result, f"股票基本資訊 ({market})")
                            add_history({
                                "tab": "港美股",
                                "title": "股票基本資訊",
                                "params": {"type": "futu_basicinfo", "market": market, "codes": codes}
                            })
                        else:
                            st.info("無基本資訊")
                    except Exception as e:
                        st.error(f"查詢失敗: {str(e)}")
            else:
                st.warning("請輸入至少一個股票代號")

    elif query_type == "資金分布":
        st.subheader("💰 資金分布 (大/中/小戶)")
        code = st.text_input("輸入股票代號", placeholder="例：HK.00700", key="futu_capital_dist_code")

        if st.button("查詢資金分布", key="futu_capital_dist_btn"):
            if code:
                with st.spinner("查詢中..."):
                    try:
                        result = qw.query_futu_capital_distribution(code)
                        st.session_state.current_result = result
                        if result is not None:
                            display_result(result, f"{code} 資金分布")
                            add_history({
                                "tab": "港美股",
                                "title": "資金分布",
                                "params": {"type": "futu_capital_dist", "code": code}
                            })
                        else:
                            st.info("無資金分布資料")
                    except Exception as e:
                        st.error(f"查詢失敗: {str(e)}")
            else:
                st.warning("請輸入股票代號")

    elif query_type == "資金流向":
        st.subheader("📈 資金流向（分鐘級）")
        code = st.text_input("輸入股票代號", placeholder="例：HK.00700", key="futu_capital_flow_code")

        if st.button("查詢資金流向", key="futu_capital_flow_btn"):
            if code:
                with st.spinner("查詢中..."):
                    try:
                        result = qw.query_futu_capital_flow(code)
                        st.session_state.current_result = result
                        if result is not None:
                            display_result(result, f"{code} 資金流向")
                            add_history({
                                "tab": "港美股",
                                "title": "資金流向",
                                "params": {"type": "futu_capital_flow", "code": code}
                            })
                        else:
                            st.info("無資金流向資料")
                    except Exception as e:
                        st.error(f"查詢失敗: {str(e)}")
            else:
                st.warning("請輸入股票代號")

    elif query_type == "板塊列表":
        st.subheader("📋 板塊列表")
        market = st.selectbox("選擇市場", ["HK", "US"], key="futu_plate_market")

        if st.button("查詢板塊列表", key="futu_plate_list_btn"):
            with st.spinner("查詢中..."):
                try:
                    result = qw.query_futu_plate_list(market)
                    st.session_state.current_result = result
                    if result is not None:
                        display_result(result, f"板塊列表 ({market})")
                        add_history({
                            "tab": "港美股",
                            "title": "板塊列表",
                            "params": {"type": "futu_plate_list", "market": market}
                        })
                    else:
                        st.info("無板塊列表")
                except Exception as e:
                    st.error(f"查詢失敗: {str(e)}")

    elif query_type == "板塊成分股":
        st.subheader("📊 板塊成分股")
        plate_code = st.text_input("輸入板塊代號", placeholder="例：HK.BK1000（藍籌股）", key="futu_plate_stocks_code")

        if st.button("查詢成分股", key="futu_plate_stocks_btn"):
            if plate_code:
                with st.spinner("查詢中..."):
                    try:
                        result = qw.query_futu_plate_stocks(plate_code)
                        st.session_state.current_result = result
                        if result is not None:
                            display_result(result, f"板塊成分股 ({plate_code})")
                            add_history({
                                "tab": "港美股",
                                "title": "板塊成分股",
                                "params": {"type": "futu_plate_stocks", "plate_code": plate_code}
                            })
                        else:
                            st.info("無成分股資料")
                    except Exception as e:
                        st.error(f"查詢失敗: {str(e)}")
            else:
                st.warning("請輸入板塊代號")

    elif query_type == "股票所屬板塊":
        st.subheader("🏷️ 股票所屬板塊")
        codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：HK.00700,HK.09988", key="futu_owner_plate_codes")

        if st.button("查詢所屬板塊", key="futu_owner_plate_btn"):
            codes = [c.strip() for c in codes_str.split(",") if c.strip()]
            if codes:
                with st.spinner("查詢中..."):
                    try:
                        result = qw.query_futu_owner_plate(codes)
                        st.session_state.current_result = result
                        if result is not None:
                            display_result(result, "股票所屬板塊")
                            add_history({
                                "tab": "港美股",
                                "title": "股票所屬板塊",
                                "params": {"type": "futu_owner_plate", "codes": codes}
                            })
                        else:
                            st.info("無板塊資料")
                    except Exception as e:
                        st.error(f"查詢失敗: {str(e)}")
            else:
                st.warning("請輸入至少一個股票代號")

def _render_news_cards(df: pd.DataFrame):
    """把新聞 DataFrame 渲染成卡片列表"""
    if df is None or df.empty:
        st.info("查無新聞資料（可能非交易日或代號有誤）")
        return

    for _, row in df.iterrows():
        title   = row.get("標題", "")
        summary = row.get("摘要", "")
        time_   = row.get("時間", "")
        source  = row.get("來源", "")
        url     = row.get("連結", "")

        with st.container():
            st.markdown(
                f"""<div style="
                    border:1px solid #333; border-radius:10px;
                    padding:14px 18px; margin-bottom:10px;
                    background:#1a1a2e;
                ">
                <div style="font-size:1rem; font-weight:600; margin-bottom:6px; color:#e0e0e0;">
                    {title}
                </div>
                <div style="font-size:0.82rem; color:#888; margin-bottom:6px;">
                    🕐 {time_} &nbsp;|&nbsp; 📰 {source}
                </div>
                {"<div style='font-size:0.88rem; color:#bbb; margin-bottom:8px;'>"+summary+"</div>" if summary else ""}
                {"<a href='"+url+"' target='_blank' style='font-size:0.82rem; color:#5b9bd5;'>🔗 閱讀原文</a>" if url else ""}
                </div>""",
                unsafe_allow_html=True,
            )


def _news_to_text(df: pd.DataFrame) -> str:
    """把新聞 DataFrame 轉成純文字給 Gemini 摘要"""
    lines = []
    for i, row in df.iterrows():
        lines.append(f"[{i+1}] {row.get('時間','')}  {row.get('來源','')}")
        lines.append(f"    標題：{row.get('標題','')}")
        if row.get("摘要"):
            lines.append(f"    摘要：{row.get('摘要','')}")
        lines.append("")
    return "\n".join(lines)


def render_news():
    """新聞（Yahoo Finance + Gemini AI 摘要）"""
    main_logger.info("渲染新聞 Tab")

    query_type = _qbtn_grid(["個股新聞", "大盤新聞"], "news_q", n_cols=2)

    # ── 個股新聞 ─────────────────────────────────────────────
    if query_type == "個股新聞":
        col_code, col_count = st.columns([2, 1])
        with col_code:
            code = st.text_input("股票代號", placeholder="例：2330（台積電）、AAPL、0700.HK", key="news_code")
        with col_count:
            count = st.slider("筆數", 3, 20, 10, key="news_count_stock")

        if st.button("查詢新聞", key="news_stock_btn", type="primary"):
            if not code:
                st.warning("請輸入股票代號")
            else:
                with st.spinner("查詢中…"):
                    df = qw.query_stock_news(code.strip(), count)
                st.session_state["_news_df"]      = df
                st.session_state["_news_subject"] = f"{code.strip()}"
                st.session_state["_news_summary"] = None

        df = st.session_state.get("_news_df")
        if df is not None:
            _render_news_cards(df)
            _news_ai_summary_btn(df, st.session_state.get("_news_subject", ""))

    # ── 大盤新聞 ─────────────────────────────────────────────
    elif query_type == "大盤新聞":
        count = st.slider("筆數", 3, 20, 10, key="news_count_market")

        if st.button("查詢大盤新聞", key="news_market_btn", type="primary"):
            with st.spinner("查詢中…"):
                df = qw.query_market_news(count)
            st.session_state["_news_df"]      = df
            st.session_state["_news_subject"] = "台股大盤（^TWII）"
            st.session_state["_news_summary"] = None

        df = st.session_state.get("_news_df")
        if df is not None:
            _render_news_cards(df)
            _news_ai_summary_btn(df, st.session_state.get("_news_subject", "台股大盤"))


def _news_ai_summary_btn(df: pd.DataFrame, subject: str):
    """在新聞列表下方顯示 Gemini 摘要按鈕與結果"""
    st.divider()
    col_btn, col_hint = st.columns([2, 5])
    with col_btn:
        do_summary = st.button("🤖 Gemini AI 摘要＆翻譯", key="news_ai_btn", use_container_width=True)
    with col_hint:
        st.caption("一鍵將英文新聞翻譯成繁體中文，並給出投資觀點")

    # 顯示已有的摘要
    if st.session_state.get("_news_summary"):
        with st.expander("📊 Gemini AI 分析結果", expanded=True):
            st.markdown(st.session_state["_news_summary"])

    if do_summary:
        engine = get_gemini_engine()
        if not engine:
            st.warning("請先在左側欄 ⚙️ 設定中填入 Gemini API Key")
            return
        news_text = _news_to_text(df)
        with st.spinner("🤖 Gemini AI 翻譯與分析中…"):
            result = engine.summarize_news(news_text, subject)
        if "error" in result:
            st.error(result["error"])
        else:
            st.session_state["_news_summary"] = result["analysis"]
            st.rerun()

def render_tools():
    """工具"""
    main_logger.info("渲染工具 Tab")
    st.subheader("🛠️ 工具集合")

    with st.expander("📈 K線圖工具"):
        code = code_input_section()
        start_date, end_date = date_input_section()
        if st.button("繪製 K線圖"):
            st.info("功能在 Phase 3 實現")

    with st.expander("🔄 對比工具"):
        st.markdown("並排對比多檔股票")

        compare_type = st.selectbox(
            "選擇對比方式",
            ["個股快照對比", "技術面對比", "基本面對比"],
            key="compare_type"
        )

        if compare_type == "個股快照對比":
            st.subheader("📊 個股快照對比")
            codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：2330,2412,3008", key="compare_snapshot_codes")
            use_async = st.checkbox("使用非同步並行查詢（更快）", value=True, key="compare_snapshot_async")

            if st.button("執行對比", key="compare_snapshot_btn"):
                codes = [c.strip() for c in codes_str.split(",") if c.strip()]
                if codes:
                    with st.spinner("查詢中..."):
                        try:
                            if use_async and len(codes) > 1:
                                # 非同步批量查詢
                                queries = [
                                    {"func": qw.query_snapshot, "args": ([code],), "name": code}
                                    for code in codes
                                ]
                                results_list = qw.batch_query_sync(queries)
                                results = [(codes[i], results_list[i]) for i in range(len(codes)) if not results_list[i].empty]
                            else:
                                # 同步查詢
                                results = []
                                for code in codes:
                                    result = qw.query_snapshot([code])
                                    if not result.empty:
                                        results.append((code, result))

                            if results:
                                st.subheader("📈 對比結果")
                                cols = st.columns(len(results))
                                for idx, (code, result) in enumerate(results):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        st.dataframe(result.head(5), use_container_width=True)
                            else:
                                st.warning("無可用結果")
                        except Exception as e:
                            st.error(f"對比失敗: {str(e)}")
                else:
                    st.warning("請輸入至少一個股票代號")

        elif compare_type == "技術面對比":
            st.subheader("📊 技術面對比")
            st.info("比較多檔股票的籌碼面數據（三大法人、融資融券等）")
            codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：2330,2412", key="compare_technical_codes")
            metric = st.selectbox("選擇比較指標", ["三大法人", "融資融券", "外資持股"], key="compare_metric")
            use_async = st.checkbox("使用非同步並行查詢（更快）", value=True, key="compare_technical_async")

            start_date, end_date = date_input_section(default_days=60)

            if st.button("執行對比", key="compare_technical_btn"):
                codes = [c.strip() for c in codes_str.split(",") if c.strip()]
                if codes:
                    with st.spinner("查詢中..."):
                        try:
                            st.markdown(f"**對比指標**: {metric}")

                            if use_async and len(codes) > 1:
                                # 非同步批量查詢
                                if metric == "三大法人":
                                    func = qw.query_institutional_investors
                                elif metric == "融資融券":
                                    func = qw.query_margin_short
                                else:
                                    func = qw.query_foreign_shareholding

                                queries = [
                                    {"func": func, "args": (code, start_date, end_date), "name": code}
                                    for code in codes
                                ]
                                results_list = qw.batch_query_sync(queries)

                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        result = results_list[idx]
                                        if not result.empty:
                                            st.dataframe(result.head(10), use_container_width=True)
                                        else:
                                            st.warning("無數據")
                            else:
                                # 同步查詢
                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        try:
                                            if metric == "三大法人":
                                                result = qw.query_institutional_investors(code, start_date, end_date)
                                            elif metric == "融資融券":
                                                result = qw.query_margin_short(code, start_date, end_date)
                                            else:  # 外資持股
                                                result = qw.query_foreign_shareholding(code, start_date, end_date)

                                            if not result.empty:
                                                st.dataframe(result.head(10), use_container_width=True)
                                            else:
                                                st.warning("無數據")
                                        except Exception as e:
                                            st.error(f"查詢失敗: {str(e)}")
                        except Exception as e:
                            st.error(f"對比失敗: {str(e)}")
                else:
                    st.warning("請輸入至少一個股票代號")

        elif compare_type == "基本面對比":
            st.subheader("📊 基本面對比")
            st.info("比較多檔股票的基本面數據（月營收、財報等）")
            codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：2330,2412", key="compare_fundamental_codes")
            metric = st.selectbox("選擇比較指標", ["月營收", "財務報表"], key="compare_fundamental_metric")
            use_async = st.checkbox("使用非同步並行查詢（更快）", value=True, key="compare_fundamental_async")

            start_date, end_date = date_input_section(default_days=365)

            if st.button("執行對比", key="compare_fundamental_btn"):
                codes = [c.strip() for c in codes_str.split(",") if c.strip()]
                if codes:
                    with st.spinner("查詢中..."):
                        try:
                            st.markdown(f"**對比指標**: {metric}")

                            if use_async and len(codes) > 1:
                                # 非同步批量查詢
                                if metric == "月營收":
                                    func = qw.query_month_revenue
                                else:
                                    func = qw.query_financial_statement

                                queries = [
                                    {"func": func, "args": (code, start_date, end_date), "name": code}
                                    for code in codes
                                ]
                                results_list = qw.batch_query_sync(queries)

                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        result = results_list[idx]
                                        if not result.empty:
                                            st.dataframe(result.head(10), use_container_width=True)
                                        else:
                                            st.warning("無數據")
                            else:
                                # 同步查詢
                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        try:
                                            if metric == "月營收":
                                                result = qw.query_month_revenue(code, start_date, end_date)
                                            else:  # 財務報表
                                                result = qw.query_financial_statement(code, start_date, end_date)

                                            if not result.empty:
                                                st.dataframe(result.head(10), use_container_width=True)
                                            else:
                                                st.warning("無數據")
                                        except Exception as e:
                                            st.error(f"查詢失敗: {str(e)}")
                        except Exception as e:
                            st.error(f"對比失敗: {str(e)}")
                else:
                    st.warning("請輸入至少一個股票代號")

    with st.expander("📊 資料匯出"):
        st.markdown("將查詢結果匯出或儲存到 Notion")
        df_to_export = st.session_state.current_result
        if df_to_export is not None and not df_to_export.empty:
            from utils import export_csv, export_excel, export_to_notion
            export_title = st.text_input("匯出標題", value="查詢結果", key="export_title")
            col_csv, col_excel, col_notion = st.columns(3)

            with col_csv:
                csv_bytes = export_csv(df_to_export)
                st.download_button("⬇️ 下載 CSV", csv_bytes, file_name=f"{export_title}.csv", mime="text/csv", key="dl_csv")

            with col_excel:
                excel_bytes = export_excel(df_to_export)
                st.download_button("⬇️ 下載 Excel", excel_bytes, file_name=f"{export_title}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_excel")

            with col_notion:
                if st.button("📝 儲存到 Notion", key="save_notion"):
                    cfg = st.session_state.config
                    token = cfg.get("notion_token", "")
                    db_id = cfg.get("notion_database_id", "")
                    if not token or not db_id:
                        st.warning("請先在設定中填入 Notion Token 與 Database ID")
                    else:
                        with st.spinner("儲存到 Notion..."):
                            ok, msg = export_to_notion(df_to_export, export_title, token, db_id)
                            if ok:
                                st.success(f"✅ 已儲存到 Notion")
                                if msg:
                                    st.markdown(f"[開啟頁面]({msg})", unsafe_allow_html=False)
                            else:
                                st.error(f"❌ 儲存失敗：{msg}")
        else:
            st.info("請先執行查詢，再進行匯出")

    with st.expander("🔖 書籤管理"):
        st.markdown("管理常用查詢")
        bookmark_name = st.text_input("書籤名稱", key="bookmark_input")
        if st.button("新增書籤", key="add_bookmark_btn"):
            if bookmark_name and st.session_state.current_result is not None:
                success = add_bookmark(
                    bookmark_name,
                    selected_tab,
                    {"type": "custom"}
                )
                if success:
                    st.session_state.bookmarks = load_bookmarks()
                    st.success(f"✅ 書籤 '{bookmark_name}' 已保存")
                    st.rerun()
                else:
                    st.error("❌ 書籤名稱已存在")
            else:
                st.warning("⚠️ 請先執行查詢並輸入書籤名稱")

        if bookmarks:
            st.markdown("**已有書籤：**")
            for bm in bookmarks:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.caption(f"⭐ {bm['name']}")
                with col2:
                    if st.button("🗑️", key=f"delete_{bm['name']}"):
                        remove_bookmark(bm['name'])
                        st.session_state.bookmarks = load_bookmarks()
                        st.rerun()

# ══════════════════════════════════════════════════════════
# 結果保存功能（在主內容區）
# ══════════════════════════════════════════════════════════

if st.session_state.current_result is not None and not st.session_state.current_result.empty:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 💾 快速保存")
        quick_bookmark = st.text_input("快速書籤名稱", key="quick_bookmark")
        if st.button("💾 保存為書籤", key="quick_save"):
            if quick_bookmark:
                success = add_bookmark(
                    quick_bookmark,
                    selected_tab,
                    {"type": "quick_save"}
                )
                if success:
                    st.session_state.bookmarks = load_bookmarks()
                    st.success(f"✅ 書籤已保存")
                else:
                    st.error("❌ 書籤名稱已存在")
            else:
                st.warning("⚠️ 請輸入書籤名稱")

if __name__ == "__main__":
    pass


def render_gemini_chat():
    """Gemini AI 智能對話 — Chat UI"""
    main_logger.info("渲染 Gemini AI Chat Tab")

    engine = get_gemini_engine()
    if not engine:
        st.markdown("## 🤖 Gemini AI")
        st.warning("請先在左側欄 **⚙️ 系統設定** 中填入 Gemini API Key 與模型名稱，儲存後重新整理頁面。")
        with st.expander("如何取得 API Key？"):
            st.markdown(
                "1. 前往 [Google AI Studio](https://aistudio.google.com/app/apikey)\n"
                "2. 建立 API Key（免費）\n"
                "3. 複製後貼入左側欄 ⚙️ 設定，模型選 `gemini-2.5-flash`\n"
                "4. 按儲存後重新整理"
            )
        return

    history = st.session_state.gemini_chat_history

    # ── 空白狀態：置中歡迎畫面 ─────────────────────────────
    if not history:
        st.markdown(
            """
            <div style="
                display:flex; flex-direction:column; align-items:center;
                justify-content:center; min-height:55vh;
                color:#aaa; gap:12px;
            ">
                <div style="font-size:3rem">🤖</div>
                <div style="font-size:1.4rem; font-weight:600; color:#ddd;">Gemini AI 智能助手</div>
                <div style="font-size:0.95rem; text-align:center; max-width:480px; line-height:1.8;">
                    可自動調用台股、港美股、FinMind、匯率等本地工具<br/>
                    並搜尋網路即時資訊。直接用中文提問。
                </div>
                <div style="
                    margin-top:8px; font-size:0.85rem; color:#666;
                    border:1px solid #333; border-radius:8px;
                    padding:10px 20px; text-align:center; line-height:2;
                ">
                    台積電最新法人買賣超？<br/>
                    今日美股/港股開盤狀況？<br/>
                    USD 匯率近一個月走勢？
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # ── 清除按鈕（右對齊，只在有對話時顯示）─────────────
        st.markdown(
            "<div style='display:flex; justify-content:flex-end; margin-bottom:4px;'>",
            unsafe_allow_html=True,
        )
        if st.button("🗑️ 清除對話", key="clear_gemini_chat"):
            st.session_state.gemini_chat_history = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 對話泡泡 ─────────────────────────────────────────
        for msg in history:
            avatar = "🧑" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # ── 輸入框（Streamlit 原生，自動固定底部）────────────────
    user_input = st.chat_input("輸入問題，按 Enter 或點傳送鍵…", key="gemini_input")

    if user_input:
        st.session_state.gemini_chat_history.append({"role": "user", "content": user_input})

        with st.spinner("🤖 Gemini AI 思考中，正在調用工具與搜尋…"):
            try:
                response = engine.smart_query(user_input)
            except Exception as exc:
                response = {"error": str(exc)}

        ai_text = (
            f"❌ 發生錯誤：{response['error']}"
            if "error" in response
            else (response.get("analysis") or "（AI 無回應，請重試）")
        )

        st.session_state.gemini_chat_history.append({"role": "assistant", "content": ai_text})
        add_history("Gemini AI", {"type": "gemini_chat", "query": user_input[:40]})
        st.rerun()


# ==================== SIDEBAR AND MAIN LOGIC ====================

# 三組導航按鈕（永豐金 / TWSE / 其他）
SINOPAC_TABS = ["儀表板", "台股市場"]
TWSE_TABS    = ["TWSE"]
OTHER_TABS   = ["Gemini AI", "FinMind", "期貨/匯率", "港美股", "新聞", "工具"]

def _nav_btn(label: str, icon: str = ""):
    """渲染一個導航按鈕，當前選中顯示 primary 樣式"""
    current = st.session_state.selected_tab
    display = f"{icon} {label}".strip() if icon else label
    btn_type = "primary" if current == label else "secondary"
    if st.button(display, key=f"nav_{label}", use_container_width=True, type=btn_type):
        st.session_state.selected_tab = label
        st.rerun()

with st.sidebar:
    for t in SINOPAC_TABS:
        _nav_btn(t)
    st.markdown("---")
    for t in TWSE_TABS:
        _nav_btn(t)
    st.markdown("---")
    for t in OTHER_TABS:
        _nav_btn(t)

selected_tab = st.session_state.selected_tab

# 書籤區域
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
        options=history[:10],  # 只顯示最近 10 筆
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

# 設定齒輪
st.sidebar.markdown("---")
with st.sidebar.popover("⚙️ 系統設定", use_container_width=True):
    st.session_state.config = render_settings_panel(st.session_state.config, in_sidebar=False)

# 健康檢查面板
st.sidebar.markdown("---")
st.sidebar.markdown("### 🏥 系統狀態")
with st.sidebar.expander("健康檢查", expanded=False):
    health_status = HealthChecker.get_health_status()

    # 顯示各項檢查結果
    col1, col2 = st.columns(2)

    with col1:
        ok, msg = health_status["shioaji"]
        st.write(f"**API 連線**")
        st.caption(msg)

    with col2:
        ok, msg = health_status["config"]
        st.write(f"**配置檢查**")
        st.caption(msg)

    # 檔案系統
    ok, msg = health_status["filesystem"]
    st.write(f"**檔案系統**")
    st.caption(msg)

    # 摘要狀態
    st.divider()
    emoji, summary = HealthChecker.get_summary_status()
    st.metric("系統狀態", summary, emoji)
    st.divider()
    st.caption("🚀 v1.1 | Phase 7 智慧版")
    st.caption("✅ 非同步預載 | SQLite 快取 | Gemini AI")

# 側邊欄導航結束
# ══════════════════════════════════════════════════════════

# 處理書籤/歷史執行
if st.session_state.execute_bookmark:
    st.info(f"正在執行書籤: {st.session_state.execute_bookmark['name']}")
    st.session_state.execute_bookmark = None  # 清除標記
elif st.session_state.execute_history:
    st.info(f"正在重複查詢: {st.session_state.execute_history['tab']}")
    execute_from_history(st.session_state.execute_history)
    st.session_state.execute_history = None  # 清除標記

# ══════════════════════════════════════════════════════════
# 主內容區
# ══════════════════════════════════════════════════════════

if selected_tab == "Gemini AI":
    render_gemini_chat()
else:
    st.title(f"📊 {selected_tab}")
    st.markdown("---")
    if selected_tab == "儀表板":
        render_dashboard()
    elif selected_tab == "台股市場":
        render_taistock_market()
    elif selected_tab == "TWSE":
        render_twse_section()
    elif selected_tab == "FinMind":
        render_finmind()
    elif selected_tab == "期貨/匯率":
        render_futures_forex()
    elif selected_tab == "港美股":
        render_hk_us_stocks()
    elif selected_tab == "新聞":
        render_news()
    elif selected_tab == "工具":
        render_tools()

# 主畫面渲染完成 → 啟動背景預載（只啟動一次）
_kick_preload_background()
