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
/* ═══════════════════════════════════════════════
   台股查詢工具 — 全域設計系統
   主色調：#e63946（紅）  輔色：rgba(255,255,255,0.08)
   ═══════════════════════════════════════════════ */

/* ── 字型 & 基礎 ── */
html, body, [class*="css"] { font-family: 'Inter','Segoe UI',-apple-system,sans-serif; }
.block-container { padding-top: 1.4rem !important; }
h1 { font-size: 1.45rem !important; margin-bottom: 0 !important; font-weight: 700 !important; letter-spacing: -0.01em; }
h2 { font-size: 1.1rem !important; font-weight: 600 !important; }
h3 { font-size: 0.95rem !important; font-weight: 600 !important; }

/* ════════════════════ SIDEBAR ════════════════════ */
[data-testid="stSidebar"] {
    width: 250px !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] .stButton button {
    width: 100%;
    border-radius: 8px !important;
    font-size: 0.86rem !important;
    padding: 7px 14px !important;
    text-align: left !important;
    transition: all 0.15s ease !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    background: rgba(255,255,255,0.04) !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.07) !important;
    margin-bottom: 3px !important;
}
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
    background: rgba(255,255,255,0.09) !important;
    border-color: rgba(255,255,255,0.18) !important;
    box-shadow: 0 4px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.10) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stSidebar"] .stButton button[kind="secondary"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.4), inset 0 2px 4px rgba(0,0,0,0.2) !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    box-shadow: 0 3px 8px rgba(230,57,70,0.5), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(230,57,70,0.6) !important;
    margin-bottom: 3px !important;
}

/* ════════ BORDERED CONTAINER（複選框區） ════════ */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    background: rgba(255,255,255,0.015) !important;
}

/* ════════════════ CAPTION（分組標題） ════════════ */
[data-testid="stCaptionContainer"] p {
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.09em !important;
    text-transform: uppercase !important;
    color: #6b7280 !important;
    margin-bottom: 2px !important;
}

/* ══════════════════ CHECKBOX ══════════════════ */
[data-testid="stCheckbox"] { margin: 1px 0 !important; }
[data-testid="stCheckbox"] label {
    font-size: 0.84rem !important;
    padding: 3px 8px 3px 4px !important;
    border-radius: 6px !important;
    transition: background 0.12s !important;
}
[data-testid="stCheckbox"] label:hover { background: rgba(255,255,255,0.05) !important; }

/* ════════════════════ BUTTONS ════════════════ */
/* 主要按鈕（確認查詢） */
button[kind="primary"] {
    background: linear-gradient(135deg,#e63946 0%,#c1121f 100%) !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.025em !important;
    box-shadow: 0 2px 14px rgba(230,57,70,0.32) !important;
    transition: all 0.15s ease !important;
}
button[kind="primary"]:hover {
    box-shadow: 0 4px 20px rgba(230,57,70,0.50) !important;
    transform: translateY(-1px) !important;
}
button[kind="primary"]:active { transform: translateY(0) !important; }

/* 次要按鈕（全選等小按鈕） */
button[kind="secondary"] {
    border-radius: 6px !important;
    font-size: 0.73rem !important;
    padding: 2px 10px !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    color: rgba(255,255,255,0.6) !important;
    transition: all 0.12s ease !important;
}
button[kind="secondary"]:hover {
    border-color: rgba(255,255,255,0.32) !important;
    color: rgba(255,255,255,0.9) !important;
    background: rgba(255,255,255,0.07) !important;
}

/* ════════════ TEXT INPUT / DATE INPUT ═══════════ */
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input {
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    font-size: 0.87rem !important;
    transition: border-color 0.15s,box-shadow 0.15s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stDateInput"] input:focus {
    border-color: #e63946 !important;
    box-shadow: 0 0 0 2px rgba(230,57,70,0.18) !important;
}

/* ══════════════════ SELECTBOX ═══════════════ */
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    border-radius: 8px !important;
    border-color: rgba(255,255,255,0.12) !important;
    font-size: 0.87rem !important;
}

/* ══════════════════ SLIDER ═════════════════ */
[data-testid="stSlider"] [role="slider"] {
    background: #e63946 !important;
    border-color: #e63946 !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stThumbValue"] {
    background: #e63946 !important;
}

/* ═════════════════ PROGRESS BAR ════════════ */
[data-testid="stProgressBar"] > div > div > div > div {
    background: linear-gradient(90deg,#e63946,#ff6b6b) !important;
}

/* ═══════════════════ EXPANDER ══════════════ */
[data-testid="stExpander"] {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    background: rgba(255,255,255,0.02) !important;
    margin-bottom: 8px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.87rem !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
    transition: background 0.12s !important;
}
[data-testid="stExpander"] summary:hover { background: rgba(255,255,255,0.04) !important; }

/* ══════════════════ DIVIDER ════════════════ */
hr { border:none !important; border-top:1px solid rgba(255,255,255,0.08) !important; margin:1rem 0 !important; }

/* ═══════════════ METRIC CARDS ══════════════ */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] p { font-size: 0.73rem !important; color: #6b7280 !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] div { font-size: 1.4rem !important; font-weight: 700 !important; }

/* ════════════════ DATAFRAME ═════════════════ */
[data-testid="stDataFrame"] { border-radius: 8px !important; overflow: hidden !important; }

/* ══════════════ ALERT BOXES ═════════════════ */
[data-testid="stInfo"]    { border-radius: 8px !important; border-left: 3px solid #3b82f6 !important; }
[data-testid="stWarning"] { border-radius: 8px !important; border-left: 3px solid #f59e0b !important; }
[data-testid="stError"]   { border-radius: 8px !important; border-left: 3px solid #ef4444 !important; }
[data-testid="stSuccess"] { border-radius: 8px !important; border-left: 3px solid #10b981 !important; }

/* ══════════════════ CHAT ════════════════════ */
[data-testid="stChatInput"] { border-radius: 12px !important; }
[data-testid="stChatInput"] textarea { font-size: 0.95rem !important; }
[data-testid="stChatMessage"] { border-radius: 12px !important; padding: 4px 0 !important; }
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
    import streamlit.components.v1 as components
    components.html("""
    <div class="tradingview-widget-container" style="height:500px;width:100%">
      <div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js" async>
      {
        "colorTheme": "dark",
        "dateRange": "12M",
        "showChart": false,
        "locale": "zh_TW",
        "isTransparent": false,
        "showSymbolLogo": true,
        "showFloatingTooltip": false,
        "width": "100%",
        "height": "500",
        "tabs": [
          {
            "title": "指數",
            "symbols": [
              {"s": "TVC:TWII",       "d": "台灣加權"},
              {"s": "FOREXCOM:SPXUSD","d": "S&P 500"},
              {"s": "FOREXCOM:NSXUSD","d": "Nasdaq 100"},
              {"s": "DJ:DJI",         "d": "道瓊工業"},
              {"s": "NASDAQ:SOX",     "d": "費城半導體"},
              {"s": "TVC:HSI",        "d": "恆生指數"},
              {"s": "FOREXCOM:JPN225","d": "日經 225"}
            ],
            "originalTitle": "指數"
          },
          {
            "title": "股票",
            "symbols": [
              {"s": "TWSE:2330",  "d": "台積電"},
              {"s": "TWSE:2317",  "d": "鴻海"},
              {"s": "NASDAQ:NVDA","d": "Nvidia"},
              {"s": "NASDAQ:AAPL","d": "Apple"},
              {"s": "NASDAQ:MSFT","d": "Microsoft"},
              {"s": "NASDAQ:TSM", "d": "TSM ADR"}
            ],
            "originalTitle": "股票"
          },
          {
            "title": "外匯/商品",
            "symbols": [
              {"s": "FX:USDJPY",      "d": "美元/日圓"},
              {"s": "FX:EURUSD",      "d": "歐元/美元"},
              {"s": "TVC:GOLD",       "d": "黃金"},
              {"s": "TVC:USOIL",      "d": "WTI 原油"},
              {"s": "BITSTAMP:BTCUSD","d": "比特幣"}
            ],
            "originalTitle": "外匯/商品"
          }
        ]
      }
      </script>
    </div>
    """, height=510)

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
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📈 查台股排行", use_container_width=True):
            st.info("請點選左側『台股市場』標籤")
    with col2:
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


def _render_batch_results(state_key: str, label_fn=None):
    """批次查詢結果統一渲染 helper。

    - 工具列：全部展開／全部收合／清除結果／全部匯出 Excel
    - 第一項預設展開，其餘收合（避免頁面過長）
    - label_fn(item) -> str 可自訂 expander 標題
    """
    stored = st.session_state.get(state_key)
    if not stored:
        return

    # 統一格式：list[(item, result)]
    extra = None
    if isinstance(stored, tuple) and len(stored) == 2 and isinstance(stored[0], list):
        results, extra = stored
    else:
        results = stored
    if not results:
        return

    expand_key = f"_expand_state_{state_key}"

    # ── 工具列 ──────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        if st.button("⬇️ 展開全部", key=f"_btn_expand_{state_key}", use_container_width=True):
            st.session_state[expand_key] = True
            st.rerun()
    with c2:
        if st.button("⬆️ 收合全部", key=f"_btn_collapse_{state_key}", use_container_width=True):
            st.session_state[expand_key] = False
            st.rerun()
    with c3:
        if st.button("🗑️ 清除結果", key=f"_btn_clear_{state_key}", use_container_width=True):
            del st.session_state[state_key]
            st.session_state.pop(expand_key, None)
            st.rerun()
    with c4:
        # 全部導出 Excel（多 sheet）
        valid = [(it, r) for it, r in results
                 if isinstance(r, pd.DataFrame) and not r.empty]
        if valid:
            from io import BytesIO
            try:
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    used = set()
                    for name, dfx in valid:
                        sheet = (name[:28] or "Sheet")
                        # 確保 sheet 名唯一
                        base = sheet; i = 1
                        while sheet in used:
                            sheet = f"{base[:25]}_{i}"; i += 1
                        used.add(sheet)
                        dfx.to_excel(writer, sheet_name=sheet, index=False)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    "📥 全部匯出 Excel",
                    data=buf.getvalue(),
                    file_name=f"batch_{state_key}_{ts}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"_export_all_{state_key}",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"匯出失敗：{e}")
        else:
            st.button("📥 全部匯出 Excel", disabled=True, use_container_width=True,
                      key=f"_export_all_{state_key}",
                      help="目前沒有可匯出的表格結果")

    # ── 結果列表 ────────────────────────────────────────
    expand_state = st.session_state.get(expand_key)
    for idx, (item, result) in enumerate(results):
        if expand_state is True:
            expanded = True
        elif expand_state is False:
            expanded = False
        else:
            expanded = (idx == 0)  # 預設只展開首項
        label = label_fn(item, extra) if label_fn else f"📋 {item}"
        with st.expander(label, expanded=expanded):
            display_result(result, item, enable_export=False)


def _taistock_dispatch(qt, code, codes, start_date, end_date, query_date, count):
    """分派台股市場查詢。"""
    if qt == "漲幅排行":      return qw.query_ranking("up", count)
    if qt == "跌幅排行":      return qw.query_ranking("down", count)
    if qt == "成交量排行":    return qw.query_ranking("volume", count)
    if qt == "成交金額排行":  return qw.query_ranking("amount", count)
    if qt == "個股即時快照":
        if not codes:
            return {"error": "⚠️ 個股快照需輸入股票代號"}
        return qw.query_snapshot(codes)
    if qt == "個股日K":
        if not code:
            return {"error": "⚠️ 個股日K需輸入股票代號"}
        return qw.query_daily_kbar(code, start_date, end_date)
    if qt == "逐筆成交":
        if not code:
            return {"error": "⚠️ 逐筆成交需輸入股票代號"}
        return qw.query_ticks(code, query_date)
    return {"error": f"未知項目：{qt}"}


def render_taistock_market():
    """台股市場查詢 —— 複選批次模式"""
    main_logger.info("渲染台股市場 Tab")

    NO_DATE_ITEMS = ["漲幅排行", "跌幅排行", "成交量排行", "成交金額排行", "個股即時快照"]
    DATE_ITEMS    = ["個股日K", "逐筆成交"]

    # ── 上半：複選區（左=不需日期，右=需要日期） ─────────────
    with st.container(border=True):
        col_left, col_right = st.columns(2)

        with col_left:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📊 不需日期（排行／快照）")
            with hc2:
                if st.button("全選", key="ts_all_nd", use_container_width=True):
                    for i in range(len(NO_DATE_ITEMS)):
                        st.session_state[f"ts_cb_nd_{i}"] = True
            for i, opt in enumerate(NO_DATE_ITEMS):
                st.checkbox(opt, key=f"ts_cb_nd_{i}")

        with col_right:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📅 需要日期（K線／逐筆）")
            with hc2:
                if st.button("全選", key="ts_all_d", use_container_width=True):
                    for i in range(len(DATE_ITEMS)):
                        st.session_state[f"ts_cb_d_{i}"] = True
            for i, opt in enumerate(DATE_ITEMS):
                st.checkbox(opt, key=f"ts_cb_d_{i}")

    # ── 判斷勾選內容，動態顯示對應參數 ─────────────────────
    selected_nd = [opt for i, opt in enumerate(NO_DATE_ITEMS) if st.session_state.get(f"ts_cb_nd_{i}", False)]
    selected_d  = [opt for i, opt in enumerate(DATE_ITEMS)    if st.session_state.get(f"ts_cb_d_{i}",  False)]
    selected    = selected_nd + selected_d

    has_ranking  = any(x in selected for x in ["漲幅排行", "跌幅排行", "成交量排行", "成交金額排行"])
    has_snapshot = "個股即時快照" in selected
    has_kbar     = "個股日K" in selected
    has_ticks    = "逐筆成交" in selected
    needs_code   = has_snapshot or has_kbar or has_ticks

    count = 10
    if has_ranking:
        count = st.slider("排行筆數", 5, 50, 10, key="ts_count")

    code, codes = "", []
    if needs_code:
        if has_snapshot:
            codes = code_input_section("輸入股票代號（快照可多碼，逗號分隔）", single=False)
            code = codes[0] if codes else ""
        else:
            code = code_input_section("輸入股票代號")
            codes = [code] if code else []

    start_date = end_date = date.today()
    if has_kbar:
        start_date, end_date = date_input_section()

    query_date = date.today()
    if has_ticks:
        query_date = st.date_input("逐筆日期", date.today(), key="ts_tick_date")

    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")

    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True,
                          key="ts_run_batch")

    st.divider()

    # ── 下半：批次執行 + 結果統一顯示 ───────────────────────
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result = _taistock_dispatch(
                        item, code, codes, start_date, end_date, query_date, count)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["ts_batch_results"] = results

    _render_batch_results("ts_batch_results")



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

    _render_batch_results("twse_batch_results")


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

    _render_batch_results(
        "fm_batch_results",
        label_fn=lambda item, extra: f"📋 {extra} — {item}" if extra else f"📋 {item}",
    )

def _futures_forex_dispatch(qt, futures_code, currency, start_date, end_date):
    """分派期貨/匯率查詢。"""
    if qt == "期貨日行情":    return qw.query_futures_daily(futures_code, start_date, end_date)
    if qt == "期貨三大法人":  return qw.query_futures_institutional(futures_code, start_date, end_date)
    if qt == "台銀匯率查詢":  return qw.query_exchange_rate(currency, start_date, end_date)
    return {"error": f"未知項目：{qt}"}


def render_futures_forex():
    """期貨/匯率 —— 複選批次模式"""
    main_logger.info("渲染期貨/匯率 Tab")

    FUTURES_ITEMS = ["期貨日行情", "期貨三大法人"]
    FOREX_ITEMS   = ["台銀匯率查詢"]

    # ── 上半：複選區（左=期貨，右=匯率） ────────────────────
    with st.container(border=True):
        col_left, col_right = st.columns(2)

        with col_left:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📉 期貨（需品種＋日期）")
            with hc2:
                if st.button("全選", key="ff_all_f", use_container_width=True):
                    for i in range(len(FUTURES_ITEMS)):
                        st.session_state[f"ff_cb_f_{i}"] = True
            for i, opt in enumerate(FUTURES_ITEMS):
                st.checkbox(opt, key=f"ff_cb_f_{i}")

        with col_right:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("💱 匯率（需幣別＋日期）")
            with hc2:
                if st.button("全選", key="ff_all_x", use_container_width=True):
                    for i in range(len(FOREX_ITEMS)):
                        st.session_state[f"ff_cb_x_{i}"] = True
            for i, opt in enumerate(FOREX_ITEMS):
                st.checkbox(opt, key=f"ff_cb_x_{i}")

    selected_f = [opt for i, opt in enumerate(FUTURES_ITEMS) if st.session_state.get(f"ff_cb_f_{i}", False)]
    selected_x = [opt for i, opt in enumerate(FOREX_ITEMS)   if st.session_state.get(f"ff_cb_x_{i}", False)]
    selected   = selected_f + selected_x

    # ── 共用參數（期貨品種 / 匯率幣別各自選，日期共用） ──────
    param_col1, param_col2 = st.columns(2)
    with param_col1:
        futures_code = st.selectbox("期貨品種", ["TX", "MTX"],
                                    help="TX: 大台, MTX: 小台",
                                    disabled=(not selected_f),
                                    key="ff_futures_code")
    with param_col2:
        currency = st.selectbox(
            "匯率幣別",
            ["USD", "JPY", "EUR", "CNY", "HKD", "GBP", "AUD", "CAD", "SGD", "ZAR"],
            disabled=(not selected_x),
            key="ff_currency")

    start_date, end_date = date_input_section(default_days=30)

    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")

    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True,
                          key="ff_run_batch")

    st.divider()

    # ── 下半：批次執行 + 結果統一顯示 ───────────────────────
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result = _futures_forex_dispatch(
                        item, futures_code, currency, start_date, end_date)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["ff_batch_results"] = results

    _render_batch_results("ff_batch_results")

def _hkus_dispatch(qt, market, codes, plate_code, start_date, end_date):
    """分派港美股查詢。"""
    first_code = codes[0] if codes else ""
    if qt == "市場開收盤狀態":   return qw.query_futu_market_state()
    if qt == "港/美股日K":
        if not first_code:
            return {"error": "⚠️ 港/美股日K 需輸入股票代號"}
        return qw.query_futu_kbar(first_code, start_date, end_date)
    if qt == "股票基本資訊":
        if not codes:
            return {"error": "⚠️ 股票基本資訊需輸入股票代號"}
        return qw.query_futu_basicinfo(market, codes)
    if qt == "資金分布":
        if not first_code:
            return {"error": "⚠️ 資金分布需輸入股票代號"}
        return qw.query_futu_capital_distribution(first_code)
    if qt == "資金流向":
        if not first_code:
            return {"error": "⚠️ 資金流向需輸入股票代號"}
        return qw.query_futu_capital_flow(first_code)
    if qt == "板塊列表":         return qw.query_futu_plate_list(market)
    if qt == "板塊成分股":
        if not plate_code:
            return {"error": "⚠️ 板塊成分股需輸入板塊代號"}
        return qw.query_futu_plate_stocks(plate_code)
    if qt == "股票所屬板塊":
        if not codes:
            return {"error": "⚠️ 股票所屬板塊需輸入股票代號"}
        return qw.query_futu_owner_plate(codes)
    return {"error": f"未知項目：{qt}"}


def render_hk_us_stocks():
    """港美股查詢 (Futu OpenAPI) —— 複選批次模式"""
    main_logger.info("渲染港美股 Tab")
    st.info("港美股查詢需要本機運行 FutuOpenD (https://openapi.futunn.com)")

    MARKET_ITEMS = ["市場開收盤狀態", "板塊列表", "板塊成分股"]
    STOCK_ITEMS  = ["港/美股日K", "股票基本資訊", "資金分布", "資金流向", "股票所屬板塊"]

    # ── 上半：複選區（左=市場/板塊，右=個股查詢） ─────────────
    with st.container(border=True):
        col_l, col_r = st.columns(2)
        with col_l:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("🌍 市場 / 板塊")
            with hc2:
                if st.button("全選", key="hk_all_m", use_container_width=True):
                    for i in range(len(MARKET_ITEMS)):
                        st.session_state[f"hk_cb_m_{i}"] = True
            for i, opt in enumerate(MARKET_ITEMS):
                st.checkbox(opt, key=f"hk_cb_m_{i}")
        with col_r:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📈 個股查詢")
            with hc2:
                if st.button("全選", key="hk_all_s", use_container_width=True):
                    for i in range(len(STOCK_ITEMS)):
                        st.session_state[f"hk_cb_s_{i}"] = True
            for i, opt in enumerate(STOCK_ITEMS):
                st.checkbox(opt, key=f"hk_cb_s_{i}")

    selected_m = [opt for i, opt in enumerate(MARKET_ITEMS) if st.session_state.get(f"hk_cb_m_{i}", False)]
    selected_s = [opt for i, opt in enumerate(STOCK_ITEMS)  if st.session_state.get(f"hk_cb_s_{i}", False)]
    selected   = selected_m + selected_s

    # ── 條件參數區 ────────────────────────────────────────
    needs_market = any(x in selected for x in ["股票基本資訊", "板塊列表"])
    needs_codes  = any(x in selected for x in ["港/美股日K", "股票基本資訊", "資金分布", "資金流向", "股票所屬板塊"])
    needs_plate  = "板塊成分股" in selected
    needs_date   = "港/美股日K" in selected

    market = "HK"
    if needs_market:
        market = st.selectbox("市場", ["HK", "US"], key="hk_market")

    codes = []
    if needs_codes:
        codes_str = st.text_input(
            "股票代號（逗號分隔可多碼）",
            placeholder="例：HK.00700, US.AAPL",
            key="hk_codes",
        )
        codes = [c.strip() for c in codes_str.split(",") if c.strip()]

    plate_code = ""
    if needs_plate:
        plate_code = st.text_input(
            "板塊代號", placeholder="例：HK.BK1000（藍籌股）", key="hk_plate_code"
        )

    start_date = end_date = date.today()
    if needs_date:
        start_date, end_date = date_input_section(default_days=365)

    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")

    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True,
                          key="hk_run_batch")

    st.divider()

    # ── 下半：批次執行 + 結果統一顯示 ───────────────────────
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result = _hkus_dispatch(item, market, codes, plate_code,
                                            start_date, end_date)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["hk_batch_results"] = results

    _render_batch_results("hk_batch_results")

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


# ==================== 選股引擎 ====================

import screener as sc

def _screener_result_block(df: pd.DataFrame, label: str):
    """顯示選股結果並提供 Excel 下載"""
    if df is None or df.empty:
        st.info("無符合條件的股票")
        return
    st.success(f"找到 **{len(df)}** 檔符合「{label}」")
    st.dataframe(df, use_container_width=True, hide_index=True)
    try:
        import io
        import openpyxl
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="選股結果", index=False)
        st.download_button("⬇ 下載 Excel", data=buf.getvalue(),
                           file_name=f"選股_{label}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception:
        pass


def _universe_sidebar(prefix: str):
    """股票清單過濾共用 UI，回傳 filtered DataFrame"""
    with st.expander("📋 股票清單過濾", expanded=False):
        col1, col2 = st.columns(2)
        min_p = col1.number_input("最低股價", value=10.0, min_value=0.0, key=f"{prefix}_minp")
        max_p = col2.number_input("最高股價", value=9999.0, min_value=0.0, key=f"{prefix}_maxp")
        min_v = st.number_input("最低成交量（張）", value=1000, min_value=0, key=f"{prefix}_minv")
        c1, c2 = st.columns(2)
        excl_etf  = c1.checkbox("排除 ETF", value=True, key=f"{prefix}_etf")
        excl_pref = c2.checkbox("排除特別股", value=True, key=f"{prefix}_pref")

    universe = sc.get_twse_universe()
    filtered = sc.filter_universe(universe, min_p, max_p, int(min_v), excl_etf, excl_pref)
    st.caption(f"股票池：{len(filtered)} 檔（上市 {len(universe)} 檔）")
    return filtered


def render_screener():
    """多因子選股頁面"""
    main_logger.info("渲染選股 Tab")
    st.markdown("### 🔍 多因子選股")
    st.caption("模仿 XQ XScript Preset 選股邏輯，以 Python + FinMind + TWSE 實現")

    tab_a, tab_b, tab_c, tab_d = st.tabs(["A 技術面", "B 財報面", "C 籌碼面", "D 多因子組合"])

    # ── A 技術面 ────────────────────────────────────────────────
    with tab_a:
        st.markdown("#### 技術指標選股")
        universe_a = _universe_sidebar("ta")

        st.markdown("**選擇技術條件（可複選）**")
        all_conds = list(sc.TECH_CONDITIONS.items())
        col_groups = [all_conds[i:i+3] for i in range(0, len(all_conds), 3)]
        selected_a = []
        for row_items in col_groups:
            cols = st.columns(3)
            for col, (key, label) in zip(cols, row_items):
                if col.checkbox(label, key=f"ta_cb_{key}"):
                    selected_a.append(key)

        mode_a = st.radio("條件模式", ["任一成立 (OR)", "全部成立 (AND)"],
                          horizontal=True, key="ta_mode")
        mode_str_a = "OR" if "OR" in mode_a else "AND"

        period_a = st.select_slider("歷史資料長度",
                                    options=["3mo", "6mo", "1y"], value="6mo", key="ta_period")

        if st.button("🚀 開始技術面選股", type="primary", key="ta_run", use_container_width=True):
            if not selected_a:
                st.warning("請至少勾選一個技術條件")
            else:
                prog = st.progress(0, text="準備中...")
                stat = st.empty()
                with st.spinner("技術面分析中..."):
                    result = sc.screen_technical(
                        universe_a, selected_a, mode_str_a, period_a,
                        progress_bar=prog, status_text=stat,
                    )
                st.session_state["screener_a_result"] = result

        _screener_result_block(st.session_state.get("screener_a_result"), "技術面")

    # ── B 財報面 ────────────────────────────────────────────────
    with tab_b:
        st.markdown("#### 財報/估值選股")
        universe_b = _universe_sidebar("fb")

        st.markdown("**TWSE 即時估值（設為 None 表示不篩選）**")
        col1, col2, col3 = st.columns(3)
        pe_on  = col1.checkbox("本益比 ≤", value=False, key="fb_pe_on")
        pb_on  = col2.checkbox("股淨比 ≤", value=False, key="fb_pb_on")
        yld_on = col3.checkbox("殖利率 ≥", value=False, key="fb_yld_on")
        pe_v  = col1.number_input("本益比上限", value=20.0, min_value=0.1, key="fb_pe_v",
                                   disabled=not pe_on)
        pb_v  = col2.number_input("股淨比上限", value=2.0,  min_value=0.1, key="fb_pb_v",
                                   disabled=not pb_on)
        yld_v = col3.number_input("殖利率下限 (%)", value=3.0, min_value=0.0, key="fb_yld_v",
                                   disabled=not yld_on)

        st.markdown("**FinMind 月營收**")
        col4, col5 = st.columns(2)
        ryoy_on = col4.checkbox("月營收 YOY ≥ (%)", value=False, key="fb_ryoy_on")
        rcons_on = col5.checkbox("月營收連續正成長", value=False, key="fb_rcons_on")
        ryoy_v  = col4.number_input("YOY 成長率下限 (%)", value=10.0, key="fb_ryoy_v",
                                     disabled=not ryoy_on)
        rcons_n = col5.number_input("連續正成長月數", value=3, min_value=1, max_value=12,
                                     key="fb_rcons_n", disabled=not rcons_on)

        if not (pe_on or pb_on or yld_on or ryoy_on or rcons_on):
            st.info("請至少勾選一項財報條件")

        if st.button("🚀 開始財報面選股", type="primary", key="fb_run", use_container_width=True):
            if not (pe_on or pb_on or yld_on or ryoy_on or rcons_on):
                st.warning("請至少勾選一項財報條件")
            else:
                prog = st.progress(0, text="準備中...")
                stat = st.empty()
                with st.spinner("財報面分析中..."):
                    result = sc.screen_fundamental(
                        universe_b,
                        pe_max=pe_v if pe_on else None,
                        pb_max=pb_v if pb_on else None,
                        yield_min=yld_v if yld_on else None,
                        rev_yoy_min=ryoy_v if ryoy_on else None,
                        rev_cons_n=int(rcons_n) if rcons_on else 0,
                        progress_bar=prog, status_text=stat,
                    )
                st.session_state["screener_b_result"] = result

        _screener_result_block(st.session_state.get("screener_b_result"), "財報面")

    # ── C 籌碼面 ────────────────────────────────────────────────
    with tab_c:
        st.markdown("#### 籌碼/法人選股")
        universe_c = _universe_sidebar("cp")

        st.markdown("**選擇籌碼條件（可複選）**")
        selected_c = []
        cols = st.columns(3)
        for i, (key, label) in enumerate(sc.CHIP_CONDITIONS.items()):
            if cols[i % 3].checkbox(label, key=f"cp_cb_{key}"):
                selected_c.append(key)

        mode_c = st.radio("條件模式", ["任一成立 (OR)", "全部成立 (AND)"],
                          horizontal=True, key="cp_mode")
        mode_str_c = "OR" if "OR" in mode_c else "AND"

        if "foreign_5d" in selected_c:
            st.caption("⚠️ 外資連5日買超需 FinMind Token，查詢較慢（每檔 ~0.25s）")

        if st.button("🚀 開始籌碼面選股", type="primary", key="cp_run", use_container_width=True):
            if not selected_c:
                st.warning("請至少勾選一個籌碼條件")
            else:
                prog = st.progress(0, text="準備中...")
                stat = st.empty()
                with st.spinner("籌碼面分析中..."):
                    result = sc.screen_chip(
                        universe_c, selected_c, mode_str_c,
                        progress_bar=prog, status_text=stat,
                    )
                st.session_state["screener_c_result"] = result

        _screener_result_block(st.session_state.get("screener_c_result"), "籌碼面")

    # ── D 多因子組合 ─────────────────────────────────────────────
    with tab_d:
        st.markdown("#### 多因子組合選股（漏斗式）")
        st.caption("技術面 → 籌碼面 → 財報面，逐步縮小候選池")
        universe_d = _universe_sidebar("mf")

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**技術條件**")
            selected_d_tech = []
            for key, label in sc.TECH_CONDITIONS.items():
                if st.checkbox(label, key=f"mf_t_{key}"):
                    selected_d_tech.append(key)
            mode_dt = st.radio("技術條件模式", ["任一 (OR)", "全部 (AND)"],
                                horizontal=True, key="mf_tmode")

            st.markdown("**籌碼條件**")
            selected_d_chip = []
            for key, label in sc.CHIP_CONDITIONS.items():
                if st.checkbox(label, key=f"mf_c_{key}"):
                    selected_d_chip.append(key)
            mode_dc = st.radio("籌碼條件模式", ["任一 (OR)", "全部 (AND)"],
                                horizontal=True, key="mf_cmode")

        with col_r:
            st.markdown("**財報條件**")
            pe2_on  = st.checkbox("本益比 ≤", key="mf_pe_on")
            pe2_v   = st.number_input("本益比上限", value=20.0, key="mf_pe_v", disabled=not pe2_on)
            pb2_on  = st.checkbox("股淨比 ≤", key="mf_pb_on")
            pb2_v   = st.number_input("股淨比上限", value=2.0, key="mf_pb_v", disabled=not pb2_on)
            yld2_on = st.checkbox("殖利率 ≥ (%)", key="mf_yld_on")
            yld2_v  = st.number_input("殖利率下限", value=3.0, key="mf_yld_v", disabled=not yld2_on)
            ryoy2_on = st.checkbox("月營收 YOY ≥ (%)", key="mf_ryoy_on")
            ryoy2_v  = st.number_input("YOY 下限", value=10.0, key="mf_ryoy_v", disabled=not ryoy2_on)

        if st.button("🚀 開始多因子選股", type="primary", key="mf_run", use_container_width=True):
            if not (selected_d_tech or selected_d_chip or pe2_on or pb2_on or yld2_on or ryoy2_on):
                st.warning("請至少選擇一項條件")
            else:
                prog = st.progress(0, text="準備中...")
                stat = st.empty()
                with st.spinner("多因子分析中...（可能需要 1-2 分鐘）"):
                    result = sc.screen_multi(
                        universe_d,
                        tech_conds=selected_d_tech,
                        tech_mode="OR" if "OR" in mode_dt else "AND",
                        chip_conds=selected_d_chip,
                        chip_mode="OR" if "OR" in mode_dc else "AND",
                        pe_max=pe2_v if pe2_on else None,
                        pb_max=pb2_v if pb2_on else None,
                        yield_min=yld2_v if yld2_on else None,
                        rev_yoy_min=ryoy2_v if ryoy2_on else None,
                        progress_bar=prog, status_text=stat,
                    )
                st.session_state["screener_d_result"] = result

        _screener_result_block(st.session_state.get("screener_d_result"), "多因子")


# ==================== SIDEBAR AND MAIN LOGIC ====================

# 三組導航按鈕（永豐金 / TWSE / 其他）
SINOPAC_TABS = ["儀表板", "台股市場"]
TWSE_TABS    = ["TWSE"]
OTHER_TABS   = ["Gemini AI", "FinMind", "期貨/匯率", "選股", "新聞", "工具"]

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
    for t in TWSE_TABS:
        _nav_btn(t)
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
    elif selected_tab == "選股":
        render_screener()
    elif selected_tab == "新聞":
        render_news()
    elif selected_tab == "工具":
        render_tools()

# 主畫面渲染完成 → 啟動背景預載（只啟動一次）
_kick_preload_background()
