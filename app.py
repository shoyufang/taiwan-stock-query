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
from deepseek_engine import get_deepseek_engine
from theme import THEMES, inject_theme_css

# ══════════════════════════════════════════════════════════
# Streamlit 配置
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="券商提供查詢工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ── 注入當前主題的 CSS ──
inject_theme_css(st.session_state["theme"])
# 將主題色彩設定寫入 session_state，讓 ui_components.display_kbar 可取用
st.session_state["_theme_cfg"] = THEMES.get(st.session_state["theme"], THEMES["🌅 Claude 暖橘"])

# ══════════════════════════════════════════════════════════

# ==================== ALL FUNCTION DEFINITIONS ====================

# ─── 查詢分派 Registry ───
# 統一查詢分派，消除 execute_from_history 與 execute_query_by_params 的重复 if/elif

def _handle_ranking(params: dict) -> tuple:
    """處理排行查詢，回傳 (result, title)"""
    ranking_type = params.get("ranking_type", "up")
    limit = params.get("limit", 10)
    result = qw.query_ranking(ranking_type, limit)
    return result, f"台股排行 - {ranking_type}"

def _handle_snapshot(params: dict) -> tuple:
    """處理快照查詢，回傳 (result, title)"""
    codes = params.get("codes", [])
    if not codes:
        return pd.DataFrame(), "個股即時快照"
    result = qw.query_snapshot(codes)
    return result, "個股即時快照"

def _handle_kbar(params: dict) -> tuple:
    """處理日K查詢，回傳 (result, title)"""
    code = params.get("code", "")
    start = params.get("start", "")
    end = params.get("end", "")
    if not (code and start and end):
        return pd.DataFrame(), f"{code} 日K"
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    result = qw.query_daily_kbar(code, start_date, end_date)
    return result, f"{code} 日K"

def _handle_ticks(params: dict) -> tuple:
    """處理逐筆成交查詢，回傳 (result, title)"""
    code = params.get("code", "")
    query_date = params.get("date", "")
    if not (code and query_date):
        return pd.DataFrame(), f"{code} 逐筆成交"
    query_date_obj = datetime.strptime(query_date, "%Y-%m-%d").date()
    result = qw.query_ticks(code, query_date_obj)
    return result, f"{code} 逐筆成交"

def _handle_institutional(params: dict) -> tuple:
    """處理三大法人查詢，回傳 (result, title)"""
    code = params.get("code", "")
    start = params.get("start", "")
    end = params.get("end", "")
    if not (code and start and end):
        return pd.DataFrame(), f"{code} 三大法人明細"
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    result = qw.query_institutional_investors(code, start_date, end_date)
    return result, f"{code} 三大法人明細"

QUERY_DISPATCH = {
    "ranking": _handle_ranking,
    "snapshot": _handle_snapshot,
    "kbar": _handle_kbar,
    "ticks": _handle_ticks,
    "institutional": _handle_institutional,
}

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
            handler = QUERY_DISPATCH.get(query_type)
            if handler:
                result, title = handler(params)
                if not result.empty:
                    st.session_state.current_result = result
                    display_result(result, f"{history_item.get('tab', '')} - {title.split(' - ')[-1] if ' - ' in title else title}")
            else:
                st.warning(f"⚠️ 暫不支援的查詢類型: {query_type}")

            main_logger.info(f"歷史查詢執行完成: {query_type}")
            st.success("✅ 查詢執行完成")
        except Exception as e:
            main_logger.error(f"歷史查詢執行失敗: {query_type}, 錯誤: {str(e)}")
            st.error(f"❌ 執行失敗: {str(e)}")


def execute_query_by_params(tab: str, params: dict):
    """根據參數執行查詢並直接就地渲染結果，支援跨分頁所有功能 (Pinned widgets)"""
    q_type = params.get("type", "")
    if not q_type:
        st.warning("⚠️ 捷徑參數不完整，無法執行")
        return

    try:
        # 1. 使用 registry 執行基本查詢類型
        handler = QUERY_DISPATCH.get(q_type)
        if handler:
            res, title = handler(params)
            if not res.empty:
                display_result(res, title)
        # 2. 新增的跨模組捷徑執行
        elif q_type == "technical_analysis":
            code = params.get("code", "")
            from datetime import datetime
            start_date = datetime.strptime(params["start"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end"], "%Y-%m-%d").date()
            indicators = params.get("indicators", [])
            import technical_analysis as ta
            with st.spinner("正在繪製互動式技術指標圖表..."):
                kbar_df = qw.query_daily_kbar(code, start_date, end_date)
                if isinstance(kbar_df, pd.DataFrame) and not kbar_df.empty:
                    theme_name = st.session_state.get("theme", "🌅 Claude 暖橘")
                    t_cfg = THEMES.get(theme_name, THEMES["🌅 Claude 暖橘"])
                    
                    tab_tv, tab_plotly = st.tabs(["📊 TradingView 專業 Canvas 終端 (推薦)", "📈 Plotly 綜合指標圖 (含 RSI/MACD/BB)"])
                    with tab_tv:
                        tv_html = ta.render_tradingview_chart(
                            kbar_df,
                            code,
                            theme_cfg=t_cfg,
                            indicators=indicators if indicators else ["MA5", "MA20"],
                            height=520
                        )
                        st.components.v1.html(tv_html, height=540)
                        st.caption("💡 提示：本終端支援極速 Canvas 渲染（含 MA/EMA/布林帶）。若需要查看 RSI、MACD、ATR 等獨立副圖指標，請切換至上方【📈 Plotly 綜合指標圖】。")
                        st.caption("💡 提示：使用滑鼠滾輪進行【縮放】，拖曳圖表進行【平移】，十字游標會顯示精確價格與成交量。")
                        
                    with tab_plotly:
                        fig = ta.plot_kbar_with_indicators(
                            kbar_df,
                            code,
                            indicators=indicators if indicators else ["MA5", "MA20"],
                            theme_cfg=t_cfg,
                            height=750
                        )
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("無法獲取K線數據，繪圖失敗")
                    
        elif q_type == "taistock_batch":
            from datetime import datetime
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
            query_date = datetime.strptime(params["query_date"], "%Y-%m-%d").date()
            results = []
            for item in params["selected"]:
                kwargs = {}
                if "resolution" in params:
                    kwargs["resolution"] = params["resolution"]
                if "threshold_vol" in params:
                    kwargs["threshold_vol"] = params["threshold_vol"]
                if "threshold_amt" in params:
                    kwargs["threshold_amt"] = params["threshold_amt"]
                res = _taistock_dispatch(
                    item, params["code"], params["codes"], start_date, end_date, query_date, params["count"],
                    **kwargs
                )
                results.append((item, res))
            # 存入臨時狀態以利渲染結果
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")

        elif q_type == "twse_batch":
            results = []
            for item in params["selected"]:
                res, _ = _twse_dispatch(item, params["code"])
                results.append((item, res))
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
            
        elif q_type == "finmind_batch":
            from datetime import datetime
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
            results = []
            for item in params["selected"]:
                res = _finmind_dispatch(item, params["code"], start_date, end_date)
                results.append((item, res))
            st.session_state["db_batch_results"] = (results, params["code"])
            _render_batch_results(
                "db_batch_results",
                label_fn=lambda item, extra: f"📋 {extra} — {item}" if extra else f"📋 {item}",
            )
            
        elif q_type == "futures_forex_batch":
            from datetime import datetime
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
            results = []
            for item in params["selected"]:
                res = _futures_forex_dispatch(
                    item, params.get("futures_code"), params.get("currency"), start_date, end_date)
                results.append((item, res))
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
            
        elif q_type == "screener_us":
            import us_screener as usc
            with st.spinner("正在執行美股多因子選股篩選..."):
                df_all = usc.get_us_screener_data(force_refresh=False)
                res_df = usc.filter_us_stocks(df_all, params["filters"])
                _us_screener_result_block(res_df, "美股多因子選股")
                
        elif q_type == "us_stock_batch":
            from datetime import datetime
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date() if params.get("start_date") else None
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date() if params.get("end_date") else None
            results = []
            for item in params["selected"]:
                res = _us_stock_dispatch(item, params["ticker"], start_date, end_date)
                results.append((item, res))
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
            
        elif q_type == "us_calendar_consensus":
            import us_calendar as usc
            with st.spinner("正在加載美股日曆與華爾街共識數據..."):
                df_cal = usc.get_us_calendar_consensus_data(force_refresh=False)
                if not df_cal.empty:
                    # 顯示華爾街評等共識排名
                    display_cols = ["代號", "名稱", "行業板塊", "最新價", "共識評等", "平均目標價", "潛在漲幅%", "分析師人數"]
                    st.dataframe(df_cal[display_cols].sort_values("潛在漲幅%", ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.warning("無數據可顯示")
        else:
            st.warning(f"⚠️ 暫不支援的捷徑類型: {q_type}")
    except Exception as exc:
        st.error(f"❌ 捷徑執行失敗: {exc}")
        main_logger.error(f"捷徑執行出錯 params={params}: {exc}")


# ══════════════════════════════════════════════════════════
# Tab 對應的查詢界面
# ══════════════════════════════════════════════════════════

@st.fragment(run_every=30)
def render_dashboard_fragment():
    """儀表板自動刷新部分 (Task 7.3/7.4)"""

    # ⚖️ 台美 ADR 溢折價即時監控
    st.subheader("⚖️ 台美 ADR 溢折價即時監控")
    try:
        from adr_query import get_adr_snapshots
        adr_data = get_adr_snapshots()
        rate = adr_data["rate"]
        ts_cached = adr_data["timestamp"]
        
        # 建立 3 欄
        cols = st.columns(3)
        for idx, item in enumerate(adr_data["data"]):
            key = item["key"]
            name = item["name"]
            adr_ticker = item["adr_ticker"]
            adr_price = item["adr_price"]
            tw_code = item["tw_code"]
            tw_price = item["tw_price"]
            adr_twd_equiv = item["adr_twd_equiv"]
            premium_pct = item["premium_pct"]
            
            # 溢價顏色 (正為暖橘，負為藍色)
            badge_color = "var(--claude-primary)" if premium_pct >= 0 else "#1976d2"
            badge_bg = "rgba(217, 119, 87, 0.12)" if premium_pct >= 0 else "rgba(25, 118, 210, 0.12)"
            
            # 使用 HTML 繪製高質感的 Glassmorphic 卡片
            with cols[idx]:
                st.markdown(f"""
                <div style="
                    background: #FFFFFF;
                    border-radius: 12px;
                    padding: 16px;
                    border: 1px solid var(--claude-border);
                    box-shadow: 0 2px 8px var(--claude-shadow);
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-weight: 700; font-size: 0.95rem; color: var(--claude-text);">{name} {key}</span>
                        <div style="
                            background: {badge_bg};
                            border-radius: 6px;
                            padding: 3px 8px;
                            color: {badge_color};
                            font-weight: 700;
                            font-size: 0.85rem;
                        ">
                            {premium_pct:+.2f}%
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <div>
                            <span style="font-size: 0.72rem; color: var(--claude-text-2);">美股 {adr_ticker}</span><br/>
                            <strong style="font-size: 1.05rem; color: var(--claude-text);">${adr_price:.2f}</strong>
                        </div>
                        <div style="text-align: right;">
                            <span style="font-size: 0.72rem; color: var(--claude-text-2);">台股 {tw_code}</span><br/>
                            <strong style="font-size: 1.05rem; color: var(--claude-text);">{tw_price:.1f}元</strong>
                        </div>
                    </div>
                    <div style="
                        border-top: 1px solid var(--claude-border-light);
                        padding-top: 8px;
                        margin-top: 8px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <span style="font-size: 0.72rem; color: var(--claude-text-2);">ADR 折合台幣</span>
                        <strong style="font-size: 1.0rem; color: var(--claude-primary);">{adr_twd_equiv:.2f}元</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown(f"""
        <div style="text-align: right; margin-top: 6px; margin-bottom: 15px;">
            <span style="font-size: 0.72rem; color: var(--claude-text-2); font-weight: 500;">
                💵 美元對台幣匯率: <strong>{rate:.4f}</strong> | ⏱️ ADR 快取更新: <strong>{ts_cached}</strong>
            </span>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.warning(f"無法載入台美 ADR 監控數據: {e}")
        main_logger.error(f"儀表板 ADR 監控渲染出錯: {e}")
        
    st.divider()
    
    # 熱門監控 (基於動態預載名單)
    st.subheader("🔥 關注名單即時監控")
    watchlist = preload_manager.frequent_queries["snapshots"]
    
    try:
        snapshot = qw.query_snapshot(watchlist)
        if not snapshot.empty:
            # 轉置一下方便看
            display_df = snapshot[["代號", "收盤", "漲跌", "漲跌幅%", "成交量"]].copy()
            
            # 加入漲跌視覺化
            def highlight_change(val):
                try:
                    if isinstance(val, (int, float)) and not pd.isna(val):
                        if val > 0:
                            return 'color: #e63946; font-weight: 600'
                        elif val < 0:
                            return 'color: #2a9d8f; font-weight: 600'
                except:
                    pass
                return ''
            
            styled = display_df.style.applymap(highlight_change, subset=["漲跌", "漲跌幅%"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("目前無關注名單數據")
    except Exception as e:
        st.error(f"監控數據獲取失敗: {str(e)}")
    
    st.caption(f"⏱️ 最後更新時間: {datetime.now().strftime('%H:%M:%S')} (每 30 秒自動刷新)")

def render_dashboard():
    """整合儀表板首頁 (Task 7.4)"""
    main_logger.info("渲染儀表板 Tab")
    st.markdown("### 📊 跨市場專業儀表板")
    
    # 1. 頂部：自動刷新的 ADR 與 關注名單 監控
    render_dashboard_fragment()
    
    st.divider()
    
    # 2. 中部：我的常用釘選查詢 (Favorites & Pinned widgets)
    st.subheader("📌 我的常用釘選查詢")
    
    # 初始化 active_dashboard_query
    if "active_dashboard_query" not in st.session_state:
        st.session_state.active_dashboard_query = None
        
    bookmarks = st.session_state.get("bookmarks", [])
    if not bookmarks:
        st.info("💡 您目前還沒有釘選任何查詢。在其他分頁查詢完成後，可使用下方的「📌 釘選此查詢到儀表板首頁」將其新增至此！")
    else:
        # 每行 3 個卡片
        cols = st.columns(3)
        for idx, bm in enumerate(bookmarks):
            name = bm["name"]
            tab = bm["tab"]
            params = bm["params"]
            
            # 根據捷徑類型顯示 Emoji
            q_type = params.get("type", "")
            emoji = "📋"
            if q_type == "technical_analysis": emoji = "📈"
            elif q_type in ["taistock_batch", "twse_batch", "finmind_batch", "us_stock_batch", "us_stock_query"]: emoji = "📊"
            elif q_type == "futures_forex_batch": emoji = "💱"
            elif q_type == "screener_us": emoji = "🔍"
            elif q_type == "us_calendar_consensus": emoji = "📅"
            
            # 參數摘要
            param_desc = ""
            if "code" in params and params["code"]: param_desc += f"代號: {params['code']} "
            elif "codes" in params and params["codes"]: param_desc += f"代號: {','.join(params['codes'][:2])} "
            elif "ticker" in params and params["ticker"]: param_desc += f"美股: {params['ticker']} "
            
            if "selected" in params:
                param_desc += f"| 項目: {len(params['selected'])}個"
                
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{emoji} {name}**")
                    st.caption(f"分頁: {tab} | {param_desc}")
                    
                    c_run, c_del = st.columns([3, 1])
                    with c_run:
                        if st.button("⚡ 快速查詢", key=f"run_bm_db_{idx}", type="primary", use_container_width=True):
                            st.session_state.active_dashboard_query = bm
                            st.rerun()
                    with c_del:
                        if st.button("🗑️", key=f"del_bm_db_{idx}", use_container_width=True, help="移除釘選"):
                            from config import remove_bookmark, load_bookmarks
                            remove_bookmark(name)
                            st.session_state.bookmarks = load_bookmarks()
                            st.success("已移除釘選")
                            if st.session_state.active_dashboard_query and st.session_state.active_dashboard_query["name"] == name:
                                st.session_state.active_dashboard_query = None
                            st.rerun()

    # 3. 原位查詢結果容器
    active_q = st.session_state.get("active_dashboard_query")
    if active_q:
        st.markdown("---")
        
        # 標題與關閉按鈕
        col_t, col_c = st.columns([5, 1])
        with col_t:
            st.markdown(f"### ⚡ 釘選查詢結果 - **{active_q['name']}**")
        with col_c:
            if st.button("❌ 關閉結果", key="close_active_db_q", type="secondary", use_container_width=True):
                st.session_state.active_dashboard_query = None
                st.rerun()
                
        # 執行並原地渲染結果
        with st.container(border=True):
            execute_query_by_params(active_q["tab"], active_q["params"])

    # 底部快速導航
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📈 查台股排行", use_container_width=True, key="quick_ts_ranking"):
            st.info("請點選左側『台股市場』標籤")
    with col2:
        if st.button("📂 查看查詢歷史", use_container_width=True, key="quick_view_history"):
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
        valid = []
        for it, r in results:
            if isinstance(r, pd.DataFrame):
                if not r.empty:
                    valid.append((it, r))
            elif isinstance(r, dict):
                # 處理美股特規結果字典與其他可能的分級數據
                rtype = r.get("type")
                rdata = r.get("data")
                if rtype == "us_profile" and isinstance(rdata, dict):
                    df_profile = pd.DataFrame(list(rdata.items()), columns=["欄位名稱", "內容"])
                    valid.append((f"{it}_基本資料", df_profile))
                elif rtype == "us_financials" and isinstance(rdata, dict):
                    name_map = {
                        "income_annual": "年度損益表",
                        "income_quarterly": "季度損益表",
                        "balance_annual": "年度資產負債表",
                        "balance_quarterly": "季度資產負債表",
                        "cashflow_annual": "年度現金流量表",
                        "cashflow_quarterly": "季度現金流量表"
                    }
                    for fk, fdf in rdata.items():
                        if isinstance(fdf, pd.DataFrame) and not fdf.empty:
                            fdf_with_index = fdf.copy()
                            idx_name = fdf_with_index.index.name or "財務項目"
                            fdf_with_index.reset_index(inplace=True)
                            if "index" in fdf_with_index.columns:
                                fdf_with_index.rename(columns={"index": idx_name}, inplace=True)
                            lbl = name_map.get(fk, fk)
                            valid.append((f"財報_{lbl}", fdf_with_index))
                elif rtype == "us_holders" and isinstance(rdata, dict):
                    for hk, hdf in rdata.items():
                        if isinstance(hdf, pd.DataFrame) and not hdf.empty:
                            lbl = "機構持股" if hk == "institutional" else "共同基金持股"
                            valid.append((f"股東_{lbl}", hdf))
                elif rtype == "us_analyst_info" and isinstance(rdata, dict):
                    df_analyst = pd.DataFrame(list(rdata.items()), columns=["評等指標", "數值"])
                    valid.append((f"{it}_分析師評等", df_analyst))
                elif rtype == "us_news" and isinstance(rdata, list):
                    news_list = []
                    for n in rdata:
                        news_list.append({
                            "標題": n.get("title", ""),
                            "媒體": n.get("publisher", ""),
                            "連結": n.get("link", ""),
                            "發布時間戳": n.get("providerPublishTime", 0)
                        })
                    if news_list:
                        df_news = pd.DataFrame(news_list)
                        valid.append((f"{it}_相關新聞", df_news))

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
                        
                        # 複製 DataFrame 並清除時區資訊，避免 openpyxl 導出失敗
                        df_clean = dfx.copy()
                        # 確保欄位名稱全部為字串，防止 openpyxl 因 DatetimeIndex 欄位而崩潰
                        df_clean.columns = [str(c) for c in df_clean.columns]
                        
                        for col in df_clean.columns:
                            try:
                                if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                                    if getattr(df_clean[col], "dt", None) is not None and df_clean[col].dt.tz is not None:
                                        df_clean[col] = df_clean[col].dt.tz_localize(None)
                                else:
                                    # 處理可能含有時區的 object 類型日期
                                    df_clean[col] = df_clean[col].apply(
                                        lambda val: val.tz_localize(None) if hasattr(val, "tz_localize") and getattr(val, "tz", None) is not None else val
                                    )
                            except Exception:
                                pass
                        df_clean.to_excel(writer, sheet_name=sheet, index=False)
                
                # 確保 local 範圍內使用正確的 datetime
                from datetime import datetime as dt_local
                ts = dt_local.now().strftime("%Y%m%d_%H%M%S")
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
    # extra 若為字串（股票代號），傳入 display_result 供 K線圖使用
    batch_code = extra if isinstance(extra, str) else ""
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
            display_result(result, item, enable_export=False, code=batch_code)


def _taistock_dispatch(qt, code, codes, start_date, end_date, query_date, count, **kwargs):
    """分派台股市場查詢。"""
    resolution = kwargs.get("resolution", "1min")
    threshold_vol = kwargs.get("threshold_vol", 50)
    threshold_amt = kwargs.get("threshold_amt", 5000000.0)

    if qt == "漲幅排行":      return qw.query_ranking("up", count)
    if qt == "跌幅排行":      return qw.query_ranking("down", count)
    if qt == "成交量排行":    return qw.query_ranking("volume", count)
    if qt == "成交金額排行":  return qw.query_ranking("amount", count)
    if qt == "個股即時快照":
        if not codes:
            return {"error": "⚠️ 個股快照需輸入股票代號"}
        return qw.query_snapshot(codes)
    if qt == "即時快照與最佳五檔 (永豐金)":
        if not codes:
            return {"error": "⚠️ 即時快照與最佳五檔需輸入股票代號"}
        return qw.query_shioaji_snapshot(codes)
    if qt == "股票合約與交易限制 (永豐金)":
        if not code:
            return {"error": "⚠️ 股票合約與交易限制需輸入股票代號"}
        return qw.query_shioaji_contract(code)
    if qt == "個股日K":
        if not code:
            return {"error": "⚠️ 個股日K需輸入股票代號"}
        return qw.query_daily_kbar(code, start_date, end_date)
    if qt == "盤中/歷史分K線 (永豐金)":
        if not code:
            return {"error": "⚠️ 盤中/歷史分K線需輸入股票代號"}
        return qw.query_shioaji_kbars(code, start_date, end_date, resolution)
    if qt == "逐筆成交":
        if not code:
            return {"error": "⚠️ 逐筆成交需輸入股票代號"}
        return qw.query_ticks(code, query_date)
    if qt == "逐筆成交與大單分析 (永豐金)":
        if not code:
            return {"error": "⚠️ 逐筆成交與大單分析需輸入股票代號"}
        return qw.analyze_shioaji_big_orders(code, query_date, threshold_vol, threshold_amt)
    if qt == "台股法說與除息日曆":
        import tw_calendar as twc
        df = twc.get_tw_calendar_consensus_data(force_refresh=False)
        if df.empty:
            return {"error": "無法獲取台股日曆數據"}
        # 按照財報公佈日排序，N/A排後面，有日期的排前面
        df_has_date = df[df["財報公佈日"] != "N/A"].copy()
        df_no_date = df[df["財報公佈日"] == "N/A"].copy()
        df_has_date = df_has_date.sort_values("財報公佈日", ascending=True)
        return pd.concat([df_has_date, df_no_date]).reset_index(drop=True)
    return {"error": f"未知項目：{qt}"}


def render_taistock_market():
    """台股市場查詢 —— 複選批次模式"""
    main_logger.info("渲染台股市場 Tab")

    NO_DATE_ITEMS = [
        "漲幅排行", "跌幅排行", "成交量排行", "成交金額排行", "個股即時快照", 
        "即時快照與最佳五檔 (永豐金)", "股票合約與交易限制 (永豐金)", "台股法說與除息日曆"
    ]
    DATE_ITEMS    = [
        "個股日K", "盤中/歷史分K線 (永豐金)", "逐筆成交", "逐筆成交與大單分析 (永豐金)"
    ]

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

    has_ranking          = any(x in selected for x in ["漲幅排行", "跌幅排行", "成交量排行", "成交金額排行"])
    has_snapshot         = "個股即時快照" in selected
    has_shioaji_snapshot = "即時快照與最佳五檔 (永豐金)" in selected
    has_shioaji_contract = "股票合約與交易限制 (永豐金)" in selected
    has_kbar             = "個股日K" in selected
    has_shioaji_kbar     = "盤中/歷史分K線 (永豐金)" in selected
    has_ticks            = "逐筆成交" in selected
    has_shioaji_big      = "逐筆成交與大單分析 (永豐金)" in selected
    
    needs_code   = has_snapshot or has_shioaji_snapshot or has_shioaji_contract or has_kbar or has_shioaji_kbar or has_ticks or has_shioaji_big

    count = 10
    if has_ranking:
        count = st.slider("排行筆數", 5, 50, 10, key="ts_count")

    code, codes = "", []
    if needs_code:
        if has_snapshot or has_shioaji_snapshot:
            codes = code_input_section("輸入股票代號（快照可多碼，逗號分隔）", single=False)
            code = codes[0] if codes else ""
        else:
            code = code_input_section("輸入股票代號")
            codes = [code] if code else []

    start_date = end_date = date.today()
    if has_kbar or has_shioaji_kbar:
        start_date, end_date = date_input_section(key_prefix="ts_")

    query_date = date.today()
    if has_ticks or has_shioaji_big:
        query_date = st.date_input("逐筆日期", date.today(), key="ts_tick_date")

    resolution = "1min"
    if has_shioaji_kbar:
        res_label_map = {
            "1分K": "1min", "5分K": "5min", "15分K": "15min", 
            "30分K": "30min", "60分K": "60min"
        }
        res_sel = st.selectbox("分K線週期 (永豐金)", list(res_label_map.keys()), index=0, key="ts_shioaji_res")
        resolution = res_label_map[res_sel]

    threshold_vol = 50
    threshold_amount = 5000000.0
    if has_shioaji_big:
        col_big1, col_big2 = st.columns(2)
        with col_big1:
            threshold_vol = st.number_input("大單張數門檻 (張)", min_value=1, value=50, step=5, key="ts_big_vol")
        with col_big2:
            threshold_amt_w = st.number_input("大單金額門檻 (萬元)", min_value=1, value=500, step=50, key="ts_big_amt")
            threshold_amount = threshold_amt_w * 10000.0

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
                        item, code, codes, start_date, end_date, query_date, count,
                        resolution=resolution, threshold_vol=threshold_vol, threshold_amt=threshold_amount
                    )
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["ts_batch_results"] = (results, code)

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "台股市場",
                "params": {
                    "type": "taistock_batch",
                    "selected": selected,
                    "code": code,
                    "codes": codes,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "query_date": query_date.isoformat(),
                    "count": count,
                    "resolution": resolution,
                    "threshold_vol": threshold_vol,
                    "threshold_amt": threshold_amount
                },
                "default_name": f"台股批次 ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

    _render_batch_results("ts_batch_results")



# ── TWSE dispatch helper（模組層級，供批次查詢用） ──────────────
_TWSE_ESG_MAP = {  # 保留供 dispatch 參照，UI 已不顯示
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
    if qt == "融資融券彙總":      return qw.query_twse_margin(c), False
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

    # ── 今日快取狀態欄 ─────────────────────────────────────
    try:
        cache_info = qw.twse_cache_status()
        ready = [c for c, v in cache_info.items() if v["exists"]]
        total = len(cache_info)
        if len(ready) == total:
            st.success(f"✅ 今日 TWSE 資料已快取（{total}/{total} 項）— 查詢速度更快", icon="⚡")
        elif ready:
            st.info(
                f"📦 今日快取：{len(ready)}/{total} 項已就緒  "
                f"（{', '.join(ready)}）\n\n"
                "未快取項目將即時呼叫 API。快取每天 20:05 自動更新。",
                icon="📡",
            )
        else:
            st.warning(
                "📡 今日尚無本地快取，所有查詢將即時呼叫 TWSE API。\n\n"
                "快取將於今日 20:05 自動下載（或週末/假日無資料）。",
                icon="⏳",
            )
    except Exception:
        pass  # 狀態顯示失敗不影響主功能

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

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "TWSE",
                "params": {
                    "type": "twse_batch",
                    "selected": selected,
                    "code": code_filter
                },
                "default_name": f"TWSE批次 ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

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
    start_date, end_date = date_input_section(default_days=365, key_prefix="fm_")

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

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "FinMind",
                "params": {
                    "type": "finmind_batch",
                    "selected": selected,
                    "code": code,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "default_name": f"FinMind批次 - {code} ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

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

    start_date, end_date = date_input_section(default_days=30, key_prefix="ff_")

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

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "期貨/匯率",
                "params": {
                    "type": "futures_forex_batch",
                    "selected": selected,
                    "futures_code": futures_code,
                    "currency": currency,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "default_name": f"期指匯率批次 ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

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




def render_us_stocks():
    """美股專區 — 整合 yfinance 與 FinMind (批次查詢模式)"""
    main_logger.info("渲染美股專區 Tab")
    st.markdown("## 🇺🇸 美股專區")
    
    NO_DATE_ITEMS = [
        "大盤指數快照", 
        "個股基本資料", 
        "最新相關新聞", 
        "個股財務報表", 
        "大股東與機構持股", 
        "分析師評等與目標價", 
        "美股板塊與大盤表現",
        "美股代號總表 (FinMind)"
    ]
    DATE_ITEMS    = ["個股歷史K線", "個股歷史K線 (FinMind)"]
    
    # ── 上半：複選區 ─────────────
    with st.container(border=True):
        col_left, col_right = st.columns(2)
        with col_left:
            st.caption("📊 綜合資訊 (不需選擇日期)")
            for i, opt in enumerate(NO_DATE_ITEMS):
                st.checkbox(opt, key=f"us_cb_nd_{i}")
        with col_right:
            st.caption("📅 歷史行情 (需選擇日期範圍)")
            for i, opt in enumerate(DATE_ITEMS):
                st.checkbox(opt, key=f"us_cb_d_{i}")

    selected_nd = [opt for i, opt in enumerate(NO_DATE_ITEMS) if st.session_state.get(f"us_cb_nd_{i}", False)]
    selected_d  = [opt for i, opt in enumerate(DATE_ITEMS)    if st.session_state.get(f"us_cb_d_{i}",  False)]
    selected    = selected_nd + selected_d

    has_snapshot = "大盤指數快照" in selected
    has_profile  = "個股基本資料" in selected
    has_news     = "最新相關新聞" in selected
    has_kbar     = "個股歷史K線" in selected
    has_list     = "美股代號總表 (FinMind)" in selected
    has_fm_kbar  = "個股歷史K線 (FinMind)" in selected
    has_fin      = "個股財務報表" in selected
    has_holders  = "大股東與機構持股" in selected
    has_analyst  = "分析師評等與目標價" in selected
    
    needs_code   = has_profile or has_news or has_kbar or has_fm_kbar or has_fin or has_holders or has_analyst
    
    ticker = ""
    if needs_code:
        from ui_components import us_code_input_section
        ticker = us_code_input_section("搜尋美股 (支援中文名稱、代號)", single=True)
        
    start_date, end_date = None, None
    if has_kbar or has_fm_kbar:
        from ui_components import date_input_section
        start_date, end_date = date_input_section(default_days=180, key_prefix="us_")

    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")
        
    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True, key="us_run_batch")
    
    st.divider()
    
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        elif needs_code and not ticker:
            st.warning("請輸入代號才能查詢個股資料")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result = _us_stock_dispatch(item, ticker, start_date, end_date)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["us_batch_results"] = (results, ticker)

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "🇺🇸 美股專區",
                "params": {
                    "type": "us_stock_batch",
                    "selected": selected,
                    "ticker": ticker,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "default_name": f"美股批次 - {ticker} ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

    _render_batch_results("us_batch_results")

    # ── AI 投資研究報告 ──────────────────────────────────
    if ticker:
        st.divider()
        st.markdown(f"### 🤖 AI 一鍵美股健檢與投資報告")
        
        # 報告快取金鑰，防範重新整理時消失
        report_key = f"us_ai_report_{ticker}"
        
        col1, col2 = st.columns([1, 4])
        with col1:
            generate_btn = st.button("✨ 生成 AI 健檢報告", type="primary", use_container_width=True, key=f"btn_ai_rep_{ticker}")
        
        if generate_btn:
            with st.spinner(f"正在為您抓取數據並由 AI 生成 {ticker} 深度投資研究報告..."):
                from deepseek_engine import generate_us_stock_report
                report_content = generate_us_stock_report(ticker)
                st.session_state[report_key] = report_content
                
        if report_key in st.session_state:
            report_content = st.session_state[report_key]
            
            # 使用高質感邊框包起報告
            with st.container(border=True):
                st.markdown(report_content)
                
                # 下載按鈕
                st.download_button(
                    "📥 下載 Markdown 投資報告",
                    data=report_content,
                    file_name=f"{ticker}_AI_Investment_Report.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key=f"dl_ai_rep_{ticker}"
                )

def _us_stock_dispatch(item: str, ticker: str, start_date, end_date):
    """分派美股市場查詢。"""
    if item == "大盤指數快照":
        import yfinance as yf
        indices = {"S&P 500": "^GSPC", "那斯達克": "^IXIC", "道瓊工業": "^DJI"}
        res = []
        for name, symbol in indices.items():
            try:
                tkr = yf.Ticker(symbol)
                hist = tkr.history(period="2d")
                if len(hist) >= 2:
                    prev_c = hist['Close'].iloc[0]
                    curr_c = hist['Close'].iloc[1]
                    res.append({"指數名稱": name, "最新報價": curr_c, "漲跌": curr_c - prev_c, "漲跌幅(%)": (curr_c - prev_c)/prev_c*100})
                elif len(hist) == 1:
                    res.append({"指數名稱": name, "最新報價": hist['Close'].iloc[0], "漲跌": 0.0, "漲跌幅(%)": 0.0})
            except Exception:
                pass
        import pandas as pd
        return pd.DataFrame(res)

    from us_stock_query import (
        get_us_stock_info, get_us_stock_history, get_us_stock_news,
        get_us_financials, get_us_holders, get_us_analyst_info, get_us_sector_performance
    )
    
    if item == "個股基本資料":
        info = get_us_stock_info(ticker)
        return {"type": "us_profile", "data": info} if info else {"error": "無法獲取基本資料"}

    if item == "個股財務報表":
        fin = get_us_financials(ticker)
        return {"type": "us_financials", "data": fin} if fin else {"error": "無法獲取財務報表"}

    if item == "大股東與機構持股":
        holders = get_us_holders(ticker)
        return {"type": "us_holders", "data": holders} if holders else {"error": "無法獲取股東結構"}

    if item == "分析師評等與目標價":
        analyst = get_us_analyst_info(ticker)
        return {"type": "us_analyst_info", "data": analyst} if analyst else {"error": "無法獲取分析師評等"}

    if item == "美股板塊與大盤表現":
        perf = get_us_sector_performance()
        return perf if not perf.empty else {"error": "無法獲取板塊表現"}
        
    if item == "最新相關新聞":
        news = get_us_stock_news(ticker)
        return {"type": "us_news", "data": news} if news else {"error": "無法獲取相關新聞"}
        
    if item == "個股歷史K線":
        # 優先走 query_wrapper 統一路徑（含快取策略與時區處理）
        if start_date and end_date:
            try:
                result = qw.query_daily_kbar(ticker, start_date, end_date)
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # query_daily_kbar 回傳 DatetimeIndex，重設為欄位以便 display_kbar 辨識
                    if result.index.name == 'Date' or isinstance(result.index, pd.DatetimeIndex):
                        result = result.reset_index()
                    if 'Date' in result.columns:
                        result['Date'] = pd.to_datetime(result['Date']).dt.date
                    return result
            except Exception:
                pass  # fallback to direct yfinance below

        # 無日期範圍時，直接抓最近 180 天（不走快取，確保最新）
        try:
            import yfinance as yf
            from datetime import timedelta as _td2, date as _date2
            tkr = yf.Ticker(ticker)
            _sd = (_date2.today() - _td2(days=180)).strftime('%Y-%m-%d')
            _ed = (_date2.today() + _td2(days=1)).strftime('%Y-%m-%d')
            df_history = tkr.history(start=_sd, end=_ed)
            if df_history is not None and not df_history.empty:
                if hasattr(df_history.index, "tz") and df_history.index.tz is not None:
                    df_history.index = df_history.index.tz_localize(None)
                df_history.reset_index(inplace=True)
                if 'Date' in df_history.columns:
                    df_history['Date'] = pd.to_datetime(df_history['Date']).dt.date
                return df_history
        except Exception as e:
            return {"error": f"獲取 K 線資料失敗：{e}"}
        return {"error": "無法獲取 K 線資料"}
        
    if item == "美股代號總表 (FinMind)":
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            df = dl.us_stock_info()
            if df is not None and not df.empty:
                return df
            return {"error": "無法獲取 FinMind 美股代號表"}
        except Exception as e:
            return {"error": f"FinMind 查詢失敗: {e}"}

    if item == "個股歷史K線 (FinMind)":
        try:
            from FinMind.data import DataLoader
            import pandas as pd
            dl = DataLoader()
            sd = start_date.strftime('%Y-%m-%d') if start_date else "2023-01-01"
            df = dl.us_stock_price(stock_id=ticker, start_date=sd)
            if df is not None and not df.empty:
                # 欄位整理成 display_kbar() 喜歡的格式 (首字大寫)
                df = df.rename(columns={
                    "date": "Date",
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                })
                df['Date'] = pd.to_datetime(df['Date']).dt.date
                return df
            return {"error": "無 K 線資料 (FinMind)"}
        except Exception as e:
            return {"error": f"FinMind K線查詢失敗: {e}"}
        
    return {"error": f"未知項目：{item}"}

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
        start_date, end_date = date_input_section(default_days=365, key_prefix="hk_")

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
            st.session_state["hk_batch_results"] = (results, codes[0] if codes else "")

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
    """把新聞 DataFrame 轉成純文字給 DeepSeek 摘要"""
    lines = []
    for i, row in df.iterrows():
        lines.append(f"[{i+1}] {row.get('時間','')}  {row.get('來源','')}")
        lines.append(f"    標題：{row.get('標題','')}")
        if row.get("摘要"):
            lines.append(f"    摘要：{row.get('摘要','')}")
        lines.append("")
    return "\n".join(lines)


def render_news():
    """新聞（Yahoo Finance + DeepSeek AI 摘要）"""
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
    """在新聞列表下方顯示 DeepSeek 摘要按鈕與結果"""
    st.divider()
    col_btn, col_hint = st.columns([2, 5])
    with col_btn:
        do_summary = st.button("🤖 DeepSeek AI 摘要＆翻譯", key="news_ai_btn", use_container_width=True)
    with col_hint:
        st.caption("一鍵將英文新聞翻譯成繁體中文，並給出投資觀點")

    # 顯示已有的摘要
    if st.session_state.get("_news_summary"):
        with st.expander("📊 DeepSeek AI 分析結果", expanded=True):
            st.markdown(st.session_state["_news_summary"])

    if do_summary:
        engine = get_deepseek_engine()
        if not engine:
            st.warning("請先在左側欄 ⚙️ 設定中填入 DeepSeek API Key")
            return
        news_text = _news_to_text(df)
        with st.spinner("🤖 DeepSeek AI 翻譯與分析中…"):
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
        start_date, end_date = date_input_section(key_prefix="tool_kbar_")
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

            start_date, end_date = date_input_section(default_days=60, key_prefix="cmp_tech_")

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

            start_date, end_date = date_input_section(default_days=365, key_prefix="cmp_fund_")

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
                    st.session_state.selected_tab,
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


def render_deepseek_chat():
    """DeepSeek AI 智能對話 — Chat UI"""
    main_logger.info("渲染 DeepSeek AI Chat Tab")

    engine = get_deepseek_engine()
    if not engine:
        st.markdown("## 🤖 DeepSeek AI")
        st.warning("請先在左側欄 **⚙️ 系統設定** 中填入 DeepSeek API Key 與模型名稱，儲存後重新整理頁面。")
        with st.expander("如何取得 API Key？"):
            st.markdown(
                "1. 前往 [Google AI Studio](https://aistudio.google.com/app/apikey)\n"
                "2. 建立 API Key（免費）\n"
                "3. 複製後貼入左側欄 ⚙️ 設定，模型選 `deepseek-2.5-flash`\n"
                "4. 按儲存後重新整理"
            )
        return

    history = st.session_state.deepseek_chat_history

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
                <div style="font-size:1.4rem; font-weight:600; color:#ddd;">DeepSeek AI 智能助手</div>
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
        if st.button("🗑️ 清除對話", key="clear_deepseek_chat"):
            st.session_state.deepseek_chat_history = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 對話泡泡 ─────────────────────────────────────────
        for msg in history:
            avatar = "🧑" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # ── 輸入框（Streamlit 原生，自動固定底部）────────────────
    user_input = st.chat_input("輸入問題，按 Enter 或點傳送鍵…", key="deepseek_input")

    if user_input:
        st.session_state.deepseek_chat_history.append({"role": "user", "content": user_input})

        with st.spinner("🤖 DeepSeek AI 思考中，正在調用工具與搜尋…"):
            try:
                response = engine.smart_query(user_input)
            except Exception as exc:
                response = {"error": str(exc)}

        # 若有模型自動回退，顯示提示
        if "model_fallback" in response:
            st.info(
                f"⚠️ 原設定模型不可用，已自動切換至 `{response['model_fallback']}`。\n\n"
                "建議在 **⚙️ 系統設定** 中將模型名稱更新為 `deepseek-2.5-flash`。",
                icon="🔄",
            )

        ai_text = (
            f"❌ 發生錯誤：{response['error']}"
            if "error" in response
            else (response.get("analysis") or "（AI 無回應，請重試）")
        )

        st.session_state.deepseek_chat_history.append({"role": "assistant", "content": ai_text})
        add_history("DeepSeek AI", {"type": "deepseek_chat", "query": user_input[:40]})
        st.rerun()


# ==================== 選股引擎 ====================

def _us_screener_result_block(df: pd.DataFrame, label: str):
    """顯示美股選股結果並提供 Excel 下載"""
    if df is None or df.empty:
        st.info("無符合條件的美股")
        return
    st.success(f"找到 **{len(df)}** 檔符合「{label}」")
    
    # 格式化 UI 顯示 (市值改為 $XXX.X B)
    display_df = df.copy()
    if "市值" in display_df.columns:
        display_df["市值"] = display_df["市值"].apply(lambda x: f"${x / 10**9:.1f} B" if pd.notna(x) and x > 0 else "$0 B")
        
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.markdown("💡 **操作提示**：複製股票代號 (例如 `NVDA`, `TSM`) 至 **【技術分析】** 或 **【美股專區】** 可查看即時 K 線圖與 AI 智能分析報告！")
    
    try:
        import io
        import openpyxl
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="美股選股結果", index=False)
        st.download_button("⬇ 下載美股選股 Excel", data=buf.getvalue(),
                           file_name=f"美股選股_{label}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        main_logger.error(f"美股選股結果匯出 Excel 失敗: {str(e)}")


def render_us_calendar_consensus():
    """美股財報日曆與華爾街共識 UI"""
    st.markdown("### 📅 美股日曆 & 華爾街共識")
    st.caption("基於 50 檔美股巨頭/藍籌股，提供即將公佈之財報日曆與華爾街目標價空間、評等共識排名")
    
    import us_calendar as usc
    
    # 1. 取得數據 (預設使用快取，24小時永久快取)
    with st.spinner("正在加載美股日曆與華爾街共識數據..."):
        try:
            df_all = usc.get_us_calendar_consensus_data(force_refresh=False)
        except Exception as e:
            st.error(f"加載數據失敗: {e}")
            return
            
    if df_all.empty:
        st.error("❌ 無法取得美股日曆與共識數據。請檢查網路或稍後再試。")
        return
        
    # 操作與刷新按鈕
    col_l, col_r = st.columns([4, 1])
    with col_r:
        force_refresh = st.button("🔄 強制重新整理", key="us_cal_refresh", use_container_width=True, help="清空 24 小時快取並重新抓取 50 檔美股最新數據")
        
    if force_refresh:
        with st.spinner("正在背景抓取 50 檔最新數據（預計耗時 5-8 秒）..."):
            try:
                df_all = usc.get_us_calendar_consensus_data(force_refresh=True)
                st.success("🔄 數據更新成功，已寫入 24 小時 SQLite 快取！")
                st.rerun()
            except Exception as e:
                st.error(f"更新失敗: {e}")
                return

    # 提供兩個分頁
    tab_cal, tab_con = st.tabs(["📅 財報公佈日曆 (Earnings Calendar)", "🎯 華爾街共識與潛在空間 (Wall Street Consensus)"])
    
    with tab_cal:
        st.markdown("#### 即將公佈之財報日程")
        st.caption("依照財報公佈日由近到遠排序")
        
        df_cal = df_all.copy()
        
        # 提取有日期的
        df_has_date = df_cal[df_cal["財報公佈日"] != "N/A"].copy()
        df_no_date = df_cal[df_cal["財報公佈日"] == "N/A"].copy()
        
        # 對有日期的按日期排序
        df_has_date = df_has_date.sort_values("財報公佈日", ascending=True)
        df_cal_sorted = pd.concat([df_has_date, df_no_date]).reset_index(drop=True)
        
        # 顯示特定欄位
        display_cols = ["代號", "名稱", "行業板塊", "最新價", "財報公佈日", "預估下季EPS", "預估營收(B)"]
        df_cal_disp = df_cal_sorted[display_cols]
        
        st.dataframe(df_cal_disp, use_container_width=True, hide_index=True)
        
        # 匯出按鈕
        try:
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_cal_disp.to_excel(writer, sheet_name="美股財報行事曆", index=False)
            st.download_button("⬇ 下載財報行事曆 Excel", data=buf.getvalue(),
                               file_name="美股財報行事曆.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="us_cal_dl")
        except Exception:
            pass
            
    with tab_con:
        st.markdown("#### 華爾街目標價潛在漲幅與評等排名")
        st.caption("按照潛在漲幅由高到低排序，協助尋找低估或具備高安全邊際之優質資產")
        
        df_con = df_all.copy()
        
        # 排序：潛在漲幅由高到低
        df_con = df_con.sort_values("潛在漲幅%", ascending=False).reset_index(drop=True)
        
        # 過濾與 Slider 篩選
        col_fil1, col_fil2 = st.columns(2)
        with col_fil1:
            min_upside = st.slider("最低潛在漲幅 (%)", min_value=-50, max_value=100, value=0, step=5, key="us_con_min_upside")
        with col_fil2:
            sectors = sorted(list(df_con["行業板塊"].unique()))
            sector_sel = st.multiselect("板塊篩選", options=["All"] + sectors, default=["All"], key="us_con_sector_sel")
            
        # 套用過濾
        df_filtered = df_con[df_con["潛在漲幅%"] >= min_upside]
        if sector_sel and "All" not in sector_sel:
            df_filtered = df_filtered[df_filtered["行業板塊"].isin(sector_sel)]
            
        display_con_cols = ["代號", "名稱", "行業板塊", "最新價", "共識評等", "平均目標價", "潛在漲幅%", "目標最低價", "目標最高價", "分析師人數"]
        df_con_disp = df_filtered[display_con_cols]
        
        st.dataframe(df_con_disp, use_container_width=True, hide_index=True)
        
        st.markdown("💡 **操作提示**：複製潛在漲幅居前的美股代號 (如 `NVDA`, `AAPL`) 至 **【技術分析】** 或 **【美股專區】**，可查看即時技術 K 線圖與 AI 智能分析報告！")
        
        # 匯出按鈕
        try:
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_con_disp.to_excel(writer, sheet_name="華爾街共識排名", index=False)
            st.download_button("⬇ 下載共識排名 Excel", data=buf.getvalue(),
                               file_name="美股華爾街共識排名.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="us_con_dl")
        except Exception:
            pass

        # 保存當前查詢參數供一鍵釘選
        st.session_state.last_query = {
            "tab": "📅 美股日曆 & 共識",
            "params": {
                "type": "us_calendar_consensus"
            },
            "default_name": "美股日曆與共識"
        }


def render_us_screener():
    """美股多因子選股頁面"""
    st.caption("基於 50 檔美股巨頭/藍籌股，提供中長期基本面與安全邊際多因子量化篩選")
    
    import us_screener as usc
    
    # 1. 取得美股數據 (使用快取，TTL 為 12 小時)
    with st.spinner("正在加載美股指標數據..."):
        try:
            df_all = usc.get_us_screener_data(force_refresh=False)
        except Exception as e:
            st.error(f"加載美股數據失敗: {e}")
            return
            
    if df_all.empty:
        st.error("❌ 無法取得美股篩選數據。請檢查網路或稍後再試。")
        return
        
    # 動態抓取行業板塊
    sectors = sorted(list(df_all["行業板塊"].unique()))
    
    # 因子配置面板
    st.markdown("#### ⚙️ 多因子篩選配置")
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**🔍 估值與規模**")
        mcap_sel = st.selectbox("市值門檻 (Market Cap)", ["All", "> 100B", "> 50B", "> 10B"], index=0, key="us_sc_mcap")
        
        pe_on = st.checkbox("本益比 (PE) ≤", value=False, key="us_sc_pe_on")
        pe_val = st.number_input("PE 上限", value=30.0, min_value=1.0, step=1.0, key="us_sc_pe_val", disabled=not pe_on)
        
        fpe_on = st.checkbox("預期本益比 (Forward PE) ≤", value=False, key="us_sc_fpe_on")
        fpe_val = st.number_input("Forward PE 上限", value=25.0, min_value=1.0, step=1.0, key="us_sc_fpe_val", disabled=not fpe_on)
        
        sectors_sel = st.multiselect("行業板塊篩選", options=["All"] + sectors, default=["All"], key="us_sc_sectors")
        
    with col_r:
        st.markdown("**📊 財務回報與安全邊際**")
        roe_on = st.checkbox("股東權益報酬率 (ROE%) ≥", value=False, key="us_sc_roe_on")
        roe_val = st.number_input("ROE% 下限", value=15.0, min_value=0.0, step=1.0, key="us_sc_roe_val", disabled=not roe_on)
        
        yield_on = st.checkbox("股利殖利率% ≥", value=False, key="us_sc_yield_on")
        yield_val = st.number_input("殖利率% 下限", value=2.0, min_value=0.0, step=0.1, key="us_sc_yield_val", disabled=not yield_on)
        
        pullback_on = st.checkbox("距離 52 週高點拉回區間", value=False, key="us_sc_pb_on")
        pullback_val = st.slider(
            "拉回幅度區間 (%)",
            min_value=-100,
            max_value=0,
            value=(-30, -5),
            step=1,
            key="us_sc_pb_val",
            disabled=not pullback_on,
            help="拉回 -10% 代表目前價格比 52 週高點低 10%"
        )

    # 動作按鈕
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        run_screener = st.button("🔍 開始選股篩選", type="primary", key="us_sc_run", use_container_width=True)
    with col_btn2:
        force_refresh_btn = st.button("🔄 強制更新數據", key="us_sc_refresh", use_container_width=True, help="清空 SQLite 快取並重新背景抓取 50 檔股票最新指標")

    # 如果點擊強制更新
    if force_refresh_btn:
        with st.spinner("正在重新下載 50 檔美股最新數據（並行下載預計需 5-8 秒）..."):
            try:
                df_all = usc.get_us_screener_data(force_refresh=True)
                st.success("🔄 數據更新成功並已寫入 12 小時永久快取！")
                st.rerun()
            except Exception as e:
                st.error(f"數據更新失敗: {e}")
                return

    # 初始化 session state 中的美股選股結果
    if "us_screener_result" not in st.session_state:
        st.session_state["us_screener_result"] = None

    if run_screener:
        # 構造過濾條件
        filters = {
            "min_mcap": mcap_sel,
            "max_pe": pe_val if pe_on else None,
            "max_forward_pe": fpe_val if fpe_on else None,
            "min_roe": roe_val if roe_on else None,
            "min_yield": yield_val if yield_on else None,
            "pullback_min": pullback_val[0] if pullback_on else None,
            "pullback_max": pullback_val[1] if pullback_on else None,
            "sectors": sectors_sel
        }
        res_df = usc.filter_us_stocks(df_all, filters)
        st.session_state["us_screener_result"] = res_df

        # 保存當前查詢參數供一鍵釘選
        st.session_state.last_query = {
            "tab": "選股",
            "params": {
                "type": "screener_us",
                "filters": filters
            },
            "default_name": "美股多因子選股"
        }

    # 渲染結果
    res_df = st.session_state.get("us_screener_result")
    if res_df is not None:
        _us_screener_result_block(res_df, "美股多因子篩選")


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
    
    # 選擇選股市場
    market_mode = st.radio("選擇選股市場", ["台股選股", "美股選股"], horizontal=True, key="screener_market_mode")
    
    if market_mode == "美股選股":
        render_us_screener()
        return

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


# ==================== 技術分析 Tab ====================

def render_technical_analysis():
    """技術分析 — K線圖 + 技術指標（Plotly互動式）"""
    main_logger.info("渲染技術分析 Tab")

    st.markdown("""
    ### 📈 K 線圖分析
    使用 **Plotly** 互動式圖表，支援各項技術指標。
    """)

    import technical_analysis as ta

    # ── 輸入參數 ──────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        try:
            from stock_lookup import resolve_code, get_name_hint, resolve_us_stock
            _raw_ta = st.text_input("股票代號", value="2330", placeholder="例：2330、台積電、AAPL", key="ta_code")
            code = resolve_code(_raw_ta) if _raw_ta else "2330"
            
            # 美股/港股別名及 AI 翻譯 fallback（如果 resolve_code 沒匹配到且輸入含有中文）
            if _raw_ta and code == _raw_ta.strip() and any('\u4e00' <= char <= '\u9fff' for char in _raw_ta):
                code = resolve_us_stock(_raw_ta)
                
            _hint = get_name_hint(_raw_ta)
            if _hint:
                st.caption(f"✅ 已解析：{_hint}")
            elif _raw_ta and code != _raw_ta.strip():
                st.caption(f"✅ 已解析：{_raw_ta.strip()} ➡️ **{code}**")
        except ImportError:
            code = st.text_input("股票代號", value="2330", key="ta_code")
    with col2:
        chart_type = st.selectbox(
            "圖表類型",
            options=["日K", "5分K", "1小時K"],
            key="ta_chart_type",
            help="日K：歷史價格；分鐘K：需要當日數據"
        )

    # ── 日期範圍 ──────────────────────────────────────────
    # 強制修正：瀏覽器重連後會還原舊 session 值，若結束日期超過 30 天前自動重設
    # 同時更名 ta_end → ta_end_v2 強制清除瀏覽器快取的舊值
    if "ta_end_v2" in st.session_state:
        _te = st.session_state["ta_end_v2"]
        if isinstance(_te, date) and _te < date.today() - timedelta(days=30):
            del st.session_state["ta_end_v2"]

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("開始日期", value=date.today() - timedelta(days=120),
                                   key="ta_start_v2")
    with col2:
        end_date = st.date_input("結束日期", value=date.today(), key="ta_end_v2")

    # 若結束日期超過 7 天前，顯示提示並提供快速重設（isinstance 保護）
    if isinstance(end_date, date) and end_date < date.today() - timedelta(days=7):
        _c1, _c2 = st.columns([3, 1])
        with _c1:
            st.warning(f"⚠️ 結束日期 {end_date} 超過 7 天前，查詢到的 K 線資料可能不是最新。")
        with _c2:
            if st.button("📅 設為今日", key="ta_reset_end", use_container_width=True):
                st.session_state["ta_end_v2"] = date.today()
                st.rerun()

    # ── 技術指標選擇 ──────────────────────────────────────
    st.markdown("**選擇技術指標（可複選）**")
    col1, col2, col3 = st.columns(3)
    with col1:
        show_ma = st.checkbox("移動平均線 (MA)", value=True, key="ta_ma")
        show_rsi = st.checkbox("RSI", value=False, key="ta_rsi")
    with col2:
        show_macd = st.checkbox("MACD", value=False, key="ta_macd")
        show_bb = st.checkbox("布林帶 (BB)", value=False, key="ta_bb")
    with col3:
        show_ema = st.checkbox("指數移動平均 (EMA)", value=False, key="ta_ema")
        show_atr = st.checkbox("ATR", value=False, key="ta_atr")

    # ── 移動平均線參數 ────────────────────────────────────
    if show_ma or show_ema:
        st.markdown("**移動平均線參數**")
        col1, col2 = st.columns(2)
        with col1:
            ma_periods = st.multiselect(
                "MA 周期",
                options=[5, 10, 20, 60, 120],
                default=[5, 20],
                key="ta_ma_periods"
            )
        with col2:
            ema_periods = st.multiselect(
                "EMA 周期",
                options=[5, 10, 12, 26],
                default=[12],
                key="ta_ema_periods"
            )
    else:
        ma_periods = []
        ema_periods = []

    # ── 查詢按鈕 ──────────────────────────────────────────
    if st.button("🔍 繪製K線圖", type="primary", use_container_width=True, key="ta_plot"):
        if not code:
            st.warning("⚠️ 請輸入股票代號")
        elif start_date >= end_date:
            st.warning("⚠️ 開始日期必須早於結束日期")
        else:
            with st.spinner(f"正在獲取 {code} 的K線數據..."):
                try:
                    # 確保日期是 datetime.date 類型
                    if isinstance(start_date, str):
                        start_date = pd.to_datetime(start_date).date()
                    if isinstance(end_date, str):
                        end_date = pd.to_datetime(end_date).date()

                    # 根據圖表類型查詢數據
                    if chart_type == "日K":
                        kbar_df = qw.query_daily_kbar(code, start_date, end_date)
                    else:
                        # 分鐘K 需要特殊處理
                        st.info("分鐘K 圖表開發中，目前支援日K。")
                        kbar_df = qw.query_daily_kbar(code, start_date, end_date)

                    if isinstance(kbar_df, dict) and "error" in kbar_df:
                        st.error(f"❌ 查詢失敗：{kbar_df['error']}")
                    elif isinstance(kbar_df, pd.DataFrame) and kbar_df.empty:
                        st.warning(f"⚠️ {code} 無可用數據")
                    else:
                        # 構建指標列表
                        indicators = []
                        for p in ma_periods:
                            indicators.append(f"MA{p}")
                        for p in ema_periods:
                            indicators.append(f"EMA{p}")
                        if show_rsi:
                            indicators.append("RSI")
                        if show_macd:
                            indicators.append("MACD")
                        if show_bb:
                            indicators.append("BB")
                        if show_atr:
                            indicators.append("ATR")

                        # 取得當前主題色彩設定，實現全網一體化視覺
                        theme_name = st.session_state.get("theme", "🌅 Claude 暖橘")
                        t_cfg = THEMES.get(theme_name, THEMES["🌅 Claude 暖橘"])

                        # 建立高質感雙 Tab 視圖，震撼使用者！
                        tab_tv, tab_plotly = st.tabs(["📊 TradingView 專業 Canvas 終端 (推薦)", "📈 Plotly 綜合指標圖 (含 RSI/MACD/BB)"])
                        
                        with tab_tv:
                            # 渲染 TradingView 終端 (Lightweight Charts)
                            tv_html = ta.render_tradingview_chart(
                                kbar_df,
                                code,
                                theme_cfg=t_cfg,
                                indicators=indicators if indicators else ["MA5", "MA20"],
                                height=520
                            )
                            st.components.v1.html(tv_html, height=540)
                            st.caption("💡 提示：本終端支援極速 Canvas 渲染（含 MA/EMA/布林帶）。若需要查看 RSI、MACD、ATR 等獨立副圖指標，請切換至上方【📈 Plotly 綜合指標圖】。")
                            st.caption("💡 提示：使用滑鼠滾輪進行【縮放】，拖曳圖表進行【平移】，十字游標會顯示精確價格與成交量。")
                            
                        with tab_plotly:
                            # 繪製與美化 Plotly 圖表，傳入 t_cfg 實現主題色彩自適應
                            fig = ta.plot_kbar_with_indicators(
                                kbar_df,
                                code,
                                indicators=indicators if indicators else ["MA5", "MA20"],
                                theme_cfg=t_cfg,
                                height=750
                            )
                            # 顯示圖表
                            st.plotly_chart(fig, use_container_width=True)

                        # 顯示統計信息
                        st.success(f"✅ 成功繪製 {code} K線圖（{len(kbar_df)} 根K線）")

                        # 添加到歷史記錄
                        add_history("技術分析", {
                            "type": "technical_analysis",
                            "code": code,
                            "start": start_date.isoformat(),
                            "end": end_date.isoformat(),
                            "indicators": indicators
                        })

                        # 保存當前查詢參數供一鍵釘選
                        st.session_state.last_query = {
                            "tab": "技術分析",
                            "params": {
                                "type": "technical_analysis",
                                "code": code,
                                "start": start_date.isoformat(),
                                "end": end_date.isoformat(),
                                "indicators": indicators
                            },
                            "default_name": f"{code} 技術分析圖表"
                        }

                        # 基礎統計信息
                        with st.expander("📊 統計信息", expanded=False):
                            col1, col2, col3, col4 = st.columns(4)
                            latest = kbar_df.iloc[-1] if not kbar_df.empty else {}

                            with col1:
                                st.metric("最新收盤價", f"${latest.get('close', 'N/A'):.2f}"
                                         if 'close' in latest else "N/A")
                            with col2:
                                if 'open' in latest and 'close' in latest:
                                    chg = latest['close'] - latest['open']
                                    st.metric("日漲跌", f"{chg:+.2f}",
                                             delta=f"{chg/latest['open']*100:+.2f}%")
                                else:
                                    st.metric("日漲跌", "N/A")
                            with col3:
                                if 'high' in latest and 'low' in latest:
                                    st.metric("日高低",
                                             f"${latest['high']:.2f} / ${latest['low']:.2f}")
                            with col4:
                                st.metric("成交量", f"{latest.get('volume', 0):,.0f}")

                except Exception as e:
                    main_logger.error(f"技術分析繪圖失敗：{str(e)}")
                    st.error(f"❌ 繪圖失敗：{str(e)}")


# ==================== SIDEBAR AND MAIN LOGIC ====================

# 三組導航按鈕（永豐金 / TWSE / 其他）
SINOPAC_TABS = ["儀表板", "台股市場", "技術分析"]
TWSE_TABS    = ["TWSE"]
OTHER_TABS   = ["DeepSeek AI", "🇺🇸 美股專區", "📅 美股日曆 & 共識", "FinMind", "期貨/匯率", "選股", "新聞", "📈 技術掃描器", "👁️ 自選股監控", "💼 投資組合", "📄 PDF 報告", "工具", "⚡ 效能監控"]

def _nav_btn(label: str, icon: str = ""):
    """渲染一個導航按鈕，當前選中顯示 primary 樣式"""
    current = st.session_state.selected_tab
    display = f"{icon} {label}".strip() if icon else label
    btn_type = "primary" if current == label else "secondary"
    if st.button(display, key=f"nav_{label}", use_container_width=True, type=btn_type):
        st.session_state.selected_tab = label
        st.rerun()

with st.sidebar:
    # ── 主題切換器 ──
    theme_names = list(THEMES.keys())
    current_idx = theme_names.index(st.session_state.get("theme", "🌅 Claude 暖橘"))
    st.markdown(
        '<p style="font-size:0.68rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;'
        'color:var(--claude-text-2);margin:4px 0 6px 2px;">🎨 介面主題</p>',
        unsafe_allow_html=True
    )
    cols_t = st.columns(len(theme_names))
    for i, tn in enumerate(theme_names):
        emoji = tn.split()[0]  # 取 emoji 部分
        is_active = (tn == st.session_state.get("theme"))
        # 用 button type 區分選中狀態
        btn_type = "primary" if is_active else "secondary"
        if cols_t[i].button(emoji, key=f"theme_btn_{i}", type=btn_type,
                            help=tn, use_container_width=True):
            st.session_state["theme"] = tn
            st.rerun()
    st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)
    st.divider()
    # ── 導航按鈕 ──
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
    st.caption("✅ 非同步預載 | SQLite 快取 | DeepSeek AI")

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

# 全域搜尋列（除 AI 和美股專區外都顯示）
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

        # 顯示搜尋結果
        if hasattr(st.session_state, 'quick_search_code') and st.session_state.get('quick_search_code'):
            code = st.session_state.quick_search_code
            raw = st.session_state.get('quick_search_raw', code)
            st.success(f"✅ 已解析: **{raw}** → **{code}**")
            # 自動執行快照查詢
            try:
                result = qw.query_snapshot([code])
                if not result.empty:
                    display_result(result, f"快速搜尋 - {raw}")
            except Exception as e:
                st.warning(f"查詢失敗: {e}")
            # 清除狀態
            st.session_state.quick_search_code = None
            st.session_state.quick_search_raw = None

if selected_tab == "DeepSeek AI":
    render_deepseek_chat()
elif selected_tab == "🇺🇸 美股專區":
    render_us_stocks()
elif selected_tab == "📅 美股日曆 & 共識":
    render_us_calendar_consensus()
else:
    st.title(f"📊 {selected_tab}")
    st.markdown("---")
    if selected_tab == "儀表板":
        render_dashboard()
    elif selected_tab == "台股市場":
        render_taistock_market()
    elif selected_tab == "技術分析":
        render_technical_analysis()
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
    elif selected_tab == "📈 技術掃描器":
        from tabs.technical_scanner import render_technical_scanner
        render_technical_scanner()
    elif selected_tab == "工具":
        render_tools()
    elif selected_tab == "📄 PDF 報告":
        from tabs.pdf_export import render_pdf_export
        render_pdf_export()
    elif selected_tab == "👁️ 自選股監控":
        from tabs.watchlist_monitor import render_watchlist_monitor
        render_watchlist_monitor()
    elif selected_tab == "💼 投資組合":
        from tabs.portfolio_tracker import render_portfolio_tracker
        render_portfolio_tracker()
    elif selected_tab == "⚡ 效能監控":
        from tabs.health_monitor import render_health_monitor
        render_health_monitor()

# ── 中央：一鍵釘選到儀表板首頁 ─────────────────────────────────
if st.session_state.get("last_query") is not None:
    st.markdown("---")
    lq = st.session_state.last_query
    
    # 建立一個精美的 Glassmorphic 卡片樣式 expander
    with st.expander(f"📌 釘選本次查詢「{lq.get('default_name')}」到儀表板首頁", expanded=False):
        col_name, col_btn = st.columns([3, 1])
        with col_name:
            bm_name = st.text_input("書籤自訂名稱", value=lq.get("default_name", ""), key="pin_bm_name")
        with col_btn:
            st.write("") # 垂直對齊用的空白
            st.write("") # 垂直對齊用的空白
            if st.button("💾 儲存並釘選", key="pin_bm_btn", type="primary", use_container_width=True):
                if bm_name:
                    from config import add_bookmark, load_bookmarks
                    success = add_bookmark(bm_name, lq["tab"], lq["params"])
                    if success:
                        st.session_state.bookmarks = load_bookmarks()
                        st.success(f"🎉 成功釘選「{bm_name}」到儀表板！")
                        # 釘選後清除以防重複顯示
                        st.session_state.last_query = None
                        st.rerun()
                    else:
                        st.error("❌ 書籤名稱已存在")
                else:
                    st.warning("⚠️ 請輸入書籤名稱")

# 主畫面渲染完成 → 啟動背景預載（只啟動一次）
_kick_preload_background()
