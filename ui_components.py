"""
UI 元件和可復用組件
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, Callable
from utils import ResultType, detect_result_type, format_number, truncate_dataframe

def display_result(df, query_type: str = "", enable_export: bool = True, code: str = ""):
    """智能呈現結果 — 根據類型自動選擇表格 / 圖表。

    df 通常是 pd.DataFrame；若 dispatch 失敗，會收到 dict {"error": "..."}，
    本函式優先處理錯誤 dict 與 None，再做型別判斷。
    code: 股票代號（傳入時用於 K線圖配色與格式，否則自 query_type 萃取）
    """
    # 若 code 未傳入，嘗試從 query_type 萃取（例如 "2330 日K" → "2330"）
    if not code and query_type:
        first_token = query_type.strip().split()[0] if query_type.strip() else ""
        if first_token and not any(kw in first_token for kw in ["個股", "港/", "盤中", "逐筆", "歷史"]):
            code = first_token
    # 錯誤 dict（dispatch helper 失敗時回傳）或美股特規 dict
    if isinstance(df, dict):
        if "error" in df:
            st.error(df["error"])
            return
        if df.get("type") == "us_profile":
            render_us_company_profile(df.get("data", {}))
            return
        if df.get("type") == "us_news":
            import datetime
            news = df.get("data", [])
            for n in news[:5]:
                ts = n.get("providerPublishTime", 0)
                date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else ""
                with st.container(border=True):
                    st.markdown(f"**[{n.get('title', '無標題')}]({n.get('link', '#')})**")
                    st.caption(f"來源: {n.get('publisher', 'N/A')} | 時間: {date_str}")
            return
        if df.get("type") == "us_financials":
            render_us_financials(df.get("data", {}))
            return
        if df.get("type") == "us_holders":
            render_us_holders(df.get("data", {}))
            return
        if df.get("type") == "us_analyst_info":
            render_us_analyst_info(df.get("data", {}))
            return
        if "summary" in df and "detail" in df:
            render_shioaji_big_orders(df)
            return
        st.json(df)
        return

    if df is None:
        st.warning("沒有查詢結果")
        return

    if not isinstance(df, pd.DataFrame):
        st.write(df)
        return

    if query_type == "美股板塊與大盤表現":
        render_us_sector_performance_dashboard(df)
        return

    if query_type == "即時快照與最佳五檔 (永豐金)":
        render_shioaji_snapshot(df)
        return

    if query_type == "股票合約與交易限制 (永豐金)":
        render_shioaji_contract(df)
        return

    if df.empty:
        st.warning("沒有查詢結果")
        return

    result_type = detect_result_type(df, query_type)
    df_display = truncate_dataframe(df)

    # 根據類型呈現
    if result_type == ResultType.KBAR:
        display_kbar(df_display, code=code)
    elif result_type == ResultType.RANKING:
        display_ranking(df_display)
    elif result_type == ResultType.FINANCIAL:
        display_financial(df_display)
    elif result_type == ResultType.SINGLE_VALUE:
        display_single_value(df)
    else:
        display_table(df_display)

    # 導出按鈕（收合，不干擾主要查看體驗）
    if enable_export:
        st.divider()
        with st.expander("📥 匯出 / 儲存到 Notion", expanded=False):
            from utils import export_csv, export_excel, export_to_notion
            from config import load_config
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_title = st.text_input("匯出標題", value=query_type or "查詢結果", key=f"etitle_{id(df)}")
            col1, col2, col3 = st.columns(3)

            with col1:
                csv_data = export_csv(df)
                st.download_button(
                    label="⬇️ CSV",
                    data=csv_data,
                    file_name=f"{export_title}_{timestamp}.csv",
                    mime="text/csv",
                    key=f"csv_{id(df)}"
                )

            with col2:
                excel_data = export_excel(df)
                st.download_button(
                    label="⬇️ Excel",
                    data=excel_data,
                    file_name=f"{export_title}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"excel_{id(df)}"
                )

            with col3:
                if st.button("📝 Notion", key=f"notion_{id(df)}"):
                    cfg = load_config()
                    token = cfg.get("notion_token", "")
                    db_id = cfg.get("notion_database_id", "")
                    if not token or not db_id:
                        st.warning("請先在設定中填入 Notion Token 與 Database ID")
                    else:
                        with st.spinner("儲存到 Notion..."):
                            ok, msg = export_to_notion(df, export_title, token, db_id)
                            if ok:
                                st.success("✅ 已儲存到 Notion")
                                if msg:
                                    st.markdown(f"[開啟頁面]({msg})")
                            else:
                                st.error(f"❌ {msg}")

def display_table(df: pd.DataFrame):
    """顯示表格 — 自動套用漲紅跌綠條件格式"""
    st.subheader("📊 查詢結果")
    
    # 檢測是否有漲跌相關欄位
    change_cols = []
    for col in df.columns:
        cl = col.lower()
        if any(kw in cl for kw in ['change', '漲跌', 'change_percent', '漲跌幅', 'change_rate']):
            change_cols.append(col)
    
    # 如果有漲跌欄位，套用條件格式
    if change_cols:
        def color_change(val):
            """漲紅跌綠配色（改用 CSS 變數）"""
            try:
                if isinstance(val, (int, float)) and not pd.isna(val):
                    if val > 0:
                        return 'color: var(--up-color); font-weight: 600'
                    elif val < 0:
                        return 'color: var(--down-color); font-weight: 600'
            except:
                pass
            return ''
        
        styled = df.style.applymap(color_change, subset=change_cols)
        st.dataframe(styled, use_container_width=True, height=400)
    else:
        st.dataframe(df, use_container_width=True, height=400)

def display_kbar(df: pd.DataFrame, code: str = ""):
    """顯示 K線圖 + OHLC 表 — TradingView Canvas + Plotly 雙 Tab"""
    st.subheader("📈 K線圖")

    # ── 確定欄位名稱 ──────────────────────────────────────
    date_col = None
    open_col = high_col = low_col = close_col = vol_col = None

    for col in df.columns:
        cl = col.lower()
        if cl in ['date', '日期', 'ts']:
            date_col = col
        if cl in ['open', '開盤']:
            open_col = col
        if cl in ['high', '最高']:
            high_col = col
        if cl in ['low', '最低']:
            low_col = col
        if cl in ['close', '收盤']:
            close_col = col
        if cl in ['volume', '成交量', '成交量(股)']:
            vol_col = col

    if not all([open_col, high_col, low_col, close_col]):
        st.warning("K線資料不完整")
        display_table(df)
        return

    # ── 建立標準化 chart_df（index = DatetimeIndex）───────
    chart_df = df.copy()

    if date_col:
        try:
            idx = pd.to_datetime(chart_df[date_col])
            if hasattr(idx, "dt") and idx.dt.tz is not None:
                idx = idx.dt.tz_localize(None)
            chart_df.index = idx
        except Exception:
            pass
    elif isinstance(chart_df.index, pd.DatetimeIndex):
        if hasattr(chart_df.index, "tz") and chart_df.index.tz is not None:
            chart_df.index = chart_df.index.tz_localize(None)
    else:
        try:
            chart_df.index = pd.to_datetime(chart_df.index)
        except Exception:
            pass

    # 統一欄位名為 open/high/low/close/volume
    remap = {}
    for src, dst in [(open_col, "open"), (high_col, "high"), (low_col, "low"),
                     (close_col, "close"), (vol_col, "volume")]:
        if src and src != dst:
            remap[src] = dst
    if remap:
        chart_df = chart_df.rename(columns=remap)

    # ── 取得主題設定（從 session_state 快取，無則預設暗色）──
    theme_cfg = st.session_state.get("_theme_cfg", None)

    # ── 嘗試載入技術分析模組 ──────────────────────────────
    try:
        import technical_analysis as ta
        has_ta = True
    except ImportError:
        has_ta = False

    if has_ta and isinstance(chart_df.index, pd.DatetimeIndex):
        # ── TradingView + Plotly 雙 Tab ──────────────────
        tab_tv, tab_plotly = st.tabs([
            "📊 TradingView 專業 Canvas 終端 (推薦)",
            "📈 Plotly 綜合指標圖 (含 RSI/MACD/BB)"
        ])

        with tab_tv:
            try:
                tv_html = ta.render_tradingview_chart(
                    chart_df, code, theme_cfg=theme_cfg,
                    indicators=["MA5", "MA20", "MA60"], height=500
                )
                st.components.v1.html(tv_html, height=520)
                st.caption("💡 使用滑鼠滾輪縮放，拖曳平移，十字游標顯示精確價格與成交量。")
            except Exception as e:
                st.warning(f"TradingView Canvas 渲染失敗，請切換至 Plotly 圖表：{e}")

        with tab_plotly:
            try:
                fig = ta.plot_kbar_with_indicators(
                    chart_df, code,
                    indicators=["MA5", "MA20", "MA60"],
                    theme_cfg=theme_cfg, height=600
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.warning(f"指標圖渲染失敗，顯示純K線圖：{e}")
                fig = go.Figure(data=[go.Candlestick(
                    x=chart_df.index,
                    open=chart_df["open"], high=chart_df["high"],
                    low=chart_df["low"], close=chart_df["close"],
                    name="K線"
                )])
                fig.update_layout(xaxis_rangeslider_visible=False, height=500)
                st.plotly_chart(fig, use_container_width=True)
    else:
        # ── 無 technical_analysis 模組時的基礎 Plotly fallback ──
        chart_df['_date'] = chart_df.index if isinstance(chart_df.index, pd.DatetimeIndex) else range(len(chart_df))
        fig = go.Figure(data=[go.Candlestick(
            x=chart_df['_date'],
            open=chart_df["open"], high=chart_df["high"],
            low=chart_df["low"], close=chart_df["close"],
            name="K線"
        )])
        try:
            for w, clr in [(5, 'orange'), (20, 'dodgerblue'), (60, 'purple')]:
                ma = chart_df["close"].rolling(w).mean()
                fig.add_trace(go.Scatter(x=chart_df['_date'], y=ma,
                                         name=f"MA{w}", line=dict(color=clr, width=1.2)))
        except Exception:
            pass
        fig.update_layout(
            title="K線圖 (MA5/MA20/MA60)", yaxis_title="價格",
            template="plotly_white", xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── 下方 OHLC 數據表 ──────────────────────────────────
    with st.expander("📋 OHLC 詳細資料", expanded=False):
        orig_cols = [c for c in [date_col, open_col, high_col, low_col, close_col, vol_col]
                     if c is not None and c in df.columns]
        display_table(df[orig_cols] if orig_cols else df)

def display_ranking(df: pd.DataFrame):
    """顯示排行榜 — 表格 + 柱狀圖"""
    st.subheader("🏆 排行榜")

    # 顯示表格
    display_table(df)

    # 嘗試繪製柱狀圖
    try:
        # 尋找漲跌幅欄位
        pct_col = None
        for col in df.columns:
            if '漲跌幅' in col or 'change_percent' in col.lower():
                pct_col = col
                break

        if pct_col and '代號' in df.columns or 'code' in [c.lower() for c in df.columns]:
            code_col = '代號' if '代號' in df.columns else next((c for c in df.columns if c.lower() == 'code'), None)
            if code_col:
                fig = px.bar(
                    df.head(20),
                    x=pct_col,
                    y=code_col,
                    orientation='h',
                    title="漲跌幅 Top 20",
                    color=pct_col,
                    color_continuous_scale="RdYlGn"
                )
                st.plotly_chart(fig, use_container_width=True)
    except:
        pass

def display_financial(df: pd.DataFrame):
    """顯示財務資料 — 表格 + 趨勢圖"""
    st.subheader("💰 財務資料")
    display_table(df)

    # 嘗試繪製趨勢
    try:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols and len(df) > 1:
            col = st.selectbox("選擇要繪製趨勢的欄位", numeric_cols)
            if col:
                fig = px.line(df, y=col, title=f"{col} 趨勢")
                st.plotly_chart(fig, use_container_width=True)
    except:
        pass

def display_single_value(df: pd.DataFrame):
    """顯示單一數值 — 大卡片"""
    st.subheader("📌 查詢結果")
    if len(df) > 0 and len(df.columns) > 0:
        value = df.iloc[0, 0]
        col_name = df.columns[0]
        st.metric(label=col_name, value=format_number(value) if isinstance(value, float) else value)

def render_sidebar_menu(available_tabs: list) -> str:
    """渲染側邊欄選單 — 分組折疊設計，返回選中的 Tab"""
    with st.sidebar:
        st.markdown("## 📋 導航")
        
        # 定義分組
        groups = {
            "📊 市場查詢": ["台股市場", "美股專區"],
            "🔍 選股分析": ["台股選股", "美股選股"],
            "📈 技術分析": ["技術分析"],
            "📅 日曆": ["台股日曆", "美股日曆"],
            "🛠️ 工具": ["工具"],
            "🤖 AI": ["AI 對話"],
        }
        
        selected_tab = None
        
        for group_name, tabs_in_group in groups.items():
            # 過濾出實際存在的 tabs
            existing_tabs = [t for t in tabs_in_group if t in available_tabs]
            if not existing_tabs:
                continue
                
            with st.expander(group_name, expanded=True):
                for tab in existing_tabs:
                    if st.button(tab, key=f"sidebar_{tab}", use_container_width=True):
                        selected_tab = tab
        
        # 如果有其他不在分組中的 tabs
        all_grouped = [t for tabs in groups.values() for t in tabs]
        ungrouped = [t for t in available_tabs if t not in all_grouped]
        if ungrouped:
            with st.expander("其他", expanded=True):
                for tab in ungrouped:
                    if st.button(tab, key=f"sidebar_{tab}", use_container_width=True):
                        selected_tab = tab
        
        return selected_tab or available_tabs[0] if available_tabs else "台股市場"

def render_search_box() -> str:
    """渲染智能搜尋框"""
    with st.sidebar:
        st.markdown("---")
        search = st.text_input("🔍 智能搜尋", placeholder="例：查2330財報")
        return search

def render_bookmarks_section(bookmarks: list) -> Optional[Dict[str, Any]]:
    """渲染書籤區域"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⭐ 釘選功能")
        if not bookmarks:
            st.caption("暫無書籤")
            return None

        selected_bookmark = st.selectbox(
            "選擇書籤",
            options=bookmarks,
            format_func=lambda x: x.get("name", "未命名"),
            label_visibility="collapsed"
        )
        return selected_bookmark

def render_history_section(history: list) -> Optional[Dict[str, Any]]:
    """渲染查詢歷史區域 — 時間線樣式"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📋 最近查詢")
        if not history:
            st.caption("暫無歷史")
            return None

        # 顯示最近 10 筆歷史
        recent_history = history[:10]
        
        for idx, item in enumerate(recent_history):
            tab = item.get('tab', '')
            timestamp = item.get('timestamp', '')
            title = item.get('title', '')
            
            # 格式化時間
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%m/%d %H:%M')
                except:
                    time_str = timestamp[:16]
            else:
                time_str = ''
            
            # 時間線項目
            with st.container():
                col_time, col_content = st.columns([1, 4])
                with col_time:
                    st.caption(f"🕒 {time_str}")
                with col_content:
                    st.caption(f"**{tab}** — {title[:30]}{'...' if len(title) > 30 else ''}")
        
        # 選擇歷史
        selected_history = st.selectbox(
            "選擇歷史記錄",
            options=recent_history,
            format_func=lambda x: f"{x.get('tab', '')} - {x.get('title', '')[:20]}",
            key="history_select",
            label_visibility="collapsed"
        )
        return selected_history

def render_settings_panel(config: Dict[str, Any], in_sidebar: bool = True) -> Dict[str, Any]:
    """渲染設定面板"""
    container = st.sidebar if in_sidebar else st.container()
    
    with container:
        if in_sidebar:
            st.markdown("---")
            st.markdown("### ⚙️ 設定")

        with st.expander("🔑 API 金鑰", expanded=not in_sidebar):
            st.markdown("**券商提供 Shioaji**")
            api_key = st.text_input("API Key", value=config.get("api_key", ""), type="password", key="api_key_input")
            secret_key = st.text_input("Secret Key", value=config.get("secret_key", ""), type="password", key="secret_key_input")

            st.markdown("**FinMind**")
            finmind_token = st.text_input("FinMind Token", value=config.get("finmind_token", ""), type="password", key="finmind_token_input")

            st.markdown("**Notion**")
            notion_token = st.text_input("Notion Token", value=config.get("notion_token", ""), type="password", key="notion_token_input", placeholder="secret_xxx...")
            notion_db_id = st.text_input("Notion Database ID", value=config.get("notion_database_id", ""), key="notion_db_input", placeholder="32位元ID")

            st.markdown("**DeepSeek AI**")
            deepseek_api_key = st.text_input("DeepSeek API Key", value=config.get("deepseek_api_key", ""), type="password", key="deepseek_api_key_input", placeholder="sk-...")
            deepseek_base_url = st.text_input("AI Base URL", value=config.get("deepseek_base_url", "https://apihub.agnes-ai.com/v1"), key="deepseek_base_url_input", placeholder="https://apihub.agnes-ai.com/v1")
            
            # 初始化可用模型列表
            from deepseek_engine import DeepSeekEngine
            
            # 使用 session_state 暫存模型列表，避免每次 UI 刷新都重新打 API
            if "available_deepseek_models" not in st.session_state:
                st.session_state.available_deepseek_models = []
                # 如果已有 Key，嘗試初始化讀取一次
                if deepseek_api_key:
                    try:
                        st.session_state.available_deepseek_models = DeepSeekEngine.list_available_models(deepseek_api_key)
                    except:
                        pass

            col_fetch, col_info = st.columns([1, 2])
            with col_fetch:
                if st.button("🔍 獲取模型列表", key="fetch_deepseek_models"):
                    if deepseek_api_key:
                        with st.spinner("獲取中..."):
                            st.session_state.available_deepseek_models = DeepSeekEngine.list_available_models(deepseek_api_key)
                            if st.session_state.available_deepseek_models:
                                st.success("已更新清單")
                            else:
                                st.error("獲取失敗")
                    else:
                        st.warning("請先輸入 Key")

            # 準備選單內容
            current_model = config.get("deepseek_model", "")
            models_list = st.session_state.available_deepseek_models
            if not models_list:
                models_list = ["(點擊上方按鈕獲取)"]
                model_index = 0
            else:
                if current_model in models_list:
                    model_index = models_list.index(current_model)
                else:
                    model_index = 0

            deepseek_model = st.selectbox("DeepSeek 模型選擇", models_list, index=model_index, key="deepseek_model_select")

            # 已有模型時預設開啟手動輸入（避免下拉清單空白時清掉設定）
            has_existing_model = bool(current_model and current_model != "(點擊上方按鈕獲取)")
            use_custom_model = st.checkbox("手動輸入模型名稱", value=has_existing_model, key="use_custom_deepseek")
            if use_custom_model:
                custom_model_name = st.text_input("輸入自訂模型代號", value=current_model, placeholder="例：deepseek-v4-flash")
                final_model = custom_model_name
            else:
                final_model = deepseek_model if deepseek_model != "(點擊上方按鈕獲取)" else current_model

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 保存", key="save_keys"):
                    config["api_key"] = api_key
                    config["secret_key"] = secret_key
                    config["finmind_token"] = finmind_token
                    config["notion_token"] = notion_token
                    config["notion_database_id"] = notion_db_id
                    config["deepseek_api_key"] = deepseek_api_key
                    config["deepseek_base_url"] = deepseek_base_url
                    config["deepseek_model"] = final_model if final_model != "(點擊上方按鈕獲取)" else ""
                    from config import save_config
                    save_config(config)
                    st.success(f"✅ 設定已保存：{config['deepseek_model']}")
            with col2:
                if st.button("🔄 重置", key="reset_keys"):
                    from config import DEFAULT_CONFIG, save_config
                    config = DEFAULT_CONFIG.copy()
                    save_config(config)
                    st.success("✅ 已重置為預設值")

        with st.expander("⚙️ 偏好設置"):
            export_format = st.selectbox("導出格式", ["csv", "excel"], index=min(["csv", "excel"].index(config.get("export_format", "csv")) if config.get("export_format", "csv") in ["csv", "excel"] else 0, 1), key="export_format_select")
            simulation_mode = st.checkbox("模擬模式", value=config.get("simulation_mode", True), key="simulation_mode_check")

            if st.button("💾 保存偏好", key="save_prefs"):
                config["export_format"] = export_format
                config["simulation_mode"] = simulation_mode
                from config import save_config
                save_config(config)
                st.success("✅ 偏好已保存")

        with st.expander("📋 歷史管理"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 查看歷史", key="view_history"):
                    from config import load_history
                    history = load_history()
                    st.metric("查詢總數", len(history))
            with col2:
                if st.button("🗑️ 清空歷史", key="clear_history"):
                    from config import clear_history
                    clear_history()
                    st.success("✅ 歷史已清空")
                    st.rerun()

        with st.expander("📊 自選監控名單", expanded=not in_sidebar):
            from config import load_watchlist, save_watchlist
            watchlist = load_watchlist()
            
            snap_codes = st.text_input(
                "即時監控代號 (Snapshots)", 
                value=",".join(watchlist.get("snapshots", [])),
                placeholder="例：2330,0050,2454",
                help="儀表板上顯示的即時監控名單，用逗號分隔"
            )
            
            kbar_codes = st.text_input(
                "預載 K線代號 (K-bars)", 
                value=",".join(watchlist.get("kbars", [])),
                placeholder="例：2330,0050",
                help="啟動時會預先加載 30 天數據的代號"
            )
            
            if st.button("💾 保存監控名單", key="save_watchlist"):
                new_snap = [c.strip() for c in snap_codes.split(",") if c.strip()]
                new_kbar = [c.strip() for c in kbar_codes.split(",") if c.strip()]
                save_watchlist({"snapshots": new_snap, "kbars": new_kbar})
                st.success("✅ 監控名單已更新 (重啟 APP 後生效)")

    return config

def date_input_section(label: str = "選擇日期範圍", default_days: int = 30,
                        key_prefix: str = "") -> tuple:
    """日期輸入區域 — 返回 (start_date, end_date)

    key_prefix: 傳入唯一前綴以隔離不同 Tab 的 session state，
                避免切換 Tab 時日期互相覆蓋（例如 "us_", "fm_", "ts_"）
    """
    kp = key_prefix or ""
    end_key = f"{kp}date_end" if kp else None

    # ── 自動修正過期的結束日期 ──────────────────────────────
    # Streamlit widget 值存在瀏覽器並在重連後送回伺服器，
    # 若使用者先前設定的結束日期超過 30 天以前，自動重設為今日
    if end_key and end_key in st.session_state:
        _stored_end = st.session_state[end_key]
        if isinstance(_stored_end, date) and _stored_end < date.today() - timedelta(days=30):
            del st.session_state[end_key]   # 強制 widget 用 value= 預設值重新初始化

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "開始日期",
            value=date.today() - timedelta(days=default_days),
            key=f"{kp}date_start" if kp else None,
        )
    with col2:
        end_date = st.date_input(
            "結束日期",
            value=date.today(),
            key=end_key,
        )

    # 若結束日期超過 7 天前，顯示警告提示（isinstance 保護：mock/None 不進入比較）
    if isinstance(end_date, date) and end_date < date.today() - timedelta(days=7):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.warning(f"⚠️ 結束日期 {end_date} 超過 7 天前，資料可能不是最新。")
        with c2:
            if st.button("📅 設為今日", key=f"{kp}reset_end", use_container_width=True):
                if end_key:
                    st.session_state[end_key] = date.today()
                st.rerun()

    return start_date, end_date

def code_input_section(label: str = "輸入股票代號", single: bool = True) -> str | list:
    """股票代號輸入區域（支援中文名稱輸入，如：台積電、蘋果、NVIDIA）"""
    try:
        from stock_lookup import resolve_code, resolve_codes, get_name_hint
        _lookup_ok = True
    except ImportError:
        _lookup_ok = False

    if single:
        raw = st.text_input(label, placeholder="例：2330、台積電、蘋果、AAPL").strip()
        if raw and _lookup_ok:
            resolved = resolve_code(raw)
            hint = get_name_hint(raw)
            if hint:
                st.caption(f"✅ 已解析：{hint}")
            return resolved
        return raw
    else:
        codes_str = st.text_input(label, placeholder="例：2330,台積電,蘋果，用逗號分隔")
        if not codes_str:
            return []
        if _lookup_ok:
            parts = [p.strip() for p in codes_str.split(",") if p.strip()]
            resolved_list = [resolve_code(p) for p in parts]
            hints = []
            for raw_p, res_p in zip(parts, resolved_list):
                if res_p.upper() != raw_p.upper() and res_p != raw_p:
                    hints.append(f"{raw_p}→{res_p}")
            if hints:
                st.caption("✅ 已解析：" + "，".join(hints))
            return resolved_list
        return [c.strip() for c in codes_str.split(",") if c.strip()]

def us_code_input_section(label: str = "輸入美股代號或名稱", single: bool = True) -> str | list:
    """美股代號輸入區域（支援中文名稱輸入，如：蘋果、微軟）"""
    try:
        from stock_lookup import resolve_us_stock, get_us_name_hint
        _lookup_ok = True
    except ImportError:
        _lookup_ok = False

    if single:
        raw = st.text_input(label, placeholder="例：AAPL、蘋果、微軟、NVDA").strip()
        if raw and _lookup_ok:
            resolved = resolve_us_stock(raw)
            hint = get_us_name_hint(raw)
            if hint:
                st.caption(f"🤖 AI 解析：{hint}")
            return resolved
        return raw
    else:
        codes_str = st.text_input(label, placeholder="例：AAPL,微軟,TSLA，用逗號分隔")
        if not codes_str:
            return []
        if _lookup_ok:
            parts = [p.strip() for p in codes_str.split(",") if p.strip()]
            resolved_list = [resolve_us_stock(p) for p in parts]
            hints = []
            for raw_p, res_p in zip(parts, resolved_list):
                if res_p.upper() != raw_p.upper() and res_p != raw_p:
                    hints.append(f"{raw_p}→{res_p}")
            if hints:
                st.caption("🤖 AI 解析：" + "，".join(hints))
            return resolved_list
        return [c.strip() for c in codes_str.split(",") if c.strip()]

def render_us_company_profile(info: dict):
    """渲染美股基本資料卡片"""
    if not info:
        st.warning("無基本資料")
        return
        
    st.markdown(f"### {info.get('name', 'N/A')}")
    st.caption(f"{info.get('sector', 'N/A')} | {info.get('industry', 'N/A')}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        cap = info.get('market_cap', 0)
        if isinstance(cap, (int, float)) and cap > 0:
            cap_str = f"{cap / 1e9:.2f} B" if cap >= 1e9 else f"{cap / 1e6:.2f} M"
        else:
            cap_str = "N/A"
        st.metric("市值 (Market Cap)", f"{cap_str} {info.get('currency', '')}")
    with col2:
        st.metric("本益比 (PE)", info.get('pe_ratio', 'N/A'))
    with col3:
        st.metric("每股盈餘 (EPS)", info.get('eps', 'N/A'))
    with col4:
        dy = info.get('dividend_yield', 0)
        dy_str = f"{dy * 100:.2f}%" if isinstance(dy, (int, float)) and dy > 0 else "N/A"
        st.metric("殖利率 (Yield)", dy_str)
        
    with st.expander("公司簡介 (Business Summary)", expanded=False):
        st.write(info.get('summary', '無公司簡介。'))

def render_us_financials(data: dict):
    """渲染美股三大報表 (年度 / 季度)"""
    if not data:
        st.warning("無財務報表資料")
        return
        
    period_type = st.radio("選擇報表頻率", ["年度資料 (Annual)", "季度資料 (Quarterly)"], horizontal=True, key=f"us_fin_period_{id(data)}")
    is_annual = "年度" in period_type
    suffix = "annual" if is_annual else "quarterly"
    
    tab_inc, tab_bal, tab_cf = st.tabs(["📊 損益表 (Income Statement)", "🏛️ 資產負債表 (Balance Sheet)", "💸 現金流量表 (Cash Flow)"])
    
    with tab_inc:
        df = data.get(f"income_{suffix}")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("無損益表資料")
            
    with tab_bal:
        df = data.get(f"balance_{suffix}")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("無資產負債表資料")
            
    with tab_cf:
        df = data.get(f"cashflow_{suffix}")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("無現金流量表資料")

def render_us_holders(data: dict):
    """渲染美股主要持股大股東"""
    inst = data.get("institutional")
    muf = data.get("mutualfund")
    
    tab_inst, tab_muf = st.tabs(["🏛️ 機構大股東 (Institutional Holders)", "💼 基金大股東 (Mutual Fund Holders)"])
    
    with tab_inst:
        if inst is not None and not inst.empty:
            df_disp = inst.copy()
            if 'Shares' in df_disp.columns:
                df_disp['Shares'] = df_disp['Shares'].apply(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
            if 'Value' in df_disp.columns:
                df_disp['Value'] = df_disp['Value'].apply(lambda x: f"${x:,}" if isinstance(x, (int, float)) else x)
            if 'pctChange' in df_disp.columns:
                df_disp['pctChange'] = df_disp['pctChange'].apply(lambda x: f"{x * 100:.2f}%" if isinstance(x, (int, float)) else x)
            st.dataframe(df_disp, use_container_width=True)
        else:
            st.info("無機構持股資料")
            
    with tab_muf:
        if muf is not None and not muf.empty:
            df_disp = muf.copy()
            if 'Shares' in df_disp.columns:
                df_disp['Shares'] = df_disp['Shares'].apply(lambda x: f"{x:,}" if isinstance(x, (int, float)) else x)
            if 'Value' in df_disp.columns:
                df_disp['Value'] = df_disp['Value'].apply(lambda x: f"${x:,}" if isinstance(x, (int, float)) else x)
            if 'pctChange' in df_disp.columns:
                df_disp['pctChange'] = df_disp['pctChange'].apply(lambda x: f"{x * 100:.2f}%" if isinstance(x, (int, float)) else x)
            st.dataframe(df_disp, use_container_width=True)
        else:
            st.info("無共同基金持股資料")

def render_us_analyst_info(data: dict):
    """渲染美股分析師評等與目標價"""
    if not data:
        st.warning("無分析師評等資料")
        return
        
    current = data.get("current_price", "N/A")
    mean_t = data.get("target_mean", "N/A")
    high_t = data.get("target_high", "N/A")
    low_t = data.get("target_low", "N/A")
    count = data.get("analyst_count", "N/A")
    rec = str(data.get("recommendation", "N/A")).upper()
    
    st.markdown(f"#### 🎯 分析師目標價與評等共識")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("最新股價", f"${current}" if isinstance(current, (int, float)) else current)
    with col2:
        st.metric("平均目標價 (Mean)", f"${mean_t}" if isinstance(mean_t, (int, float)) else mean_t)
    with col3:
        st.metric("評等共識 (Recommendation)", rec)
    with col4:
        st.metric("評估分析師人數", count)
        
    if all(isinstance(x, (int, float)) for x in [current, mean_t, high_t, low_t]):
        # 計算與目標價的潛在空間
        upside = (mean_t - current) / current * 100
        upside_str = f"+{upside:.2f}%" if upside >= 0 else f"{upside:.2f}%"
        
        st.markdown(f"**目標價區間：** ${low_t} ——— 🎯 **${mean_t}** (潛在空間: {upside_str}) ——— ${high_t}")
        
        span = high_t - low_t
        if span > 0:
            pct = (current - low_t) / span
            pct = max(0.0, min(1.0, pct))
            st.progress(pct, text=f"當前股價在目標區間的位置: {pct*100:.1f}%")

def render_us_sector_performance_dashboard(df: pd.DataFrame):
    """渲染美股行業板塊與大盤表現"""
    st.markdown("### 🌎 美股板塊與大盤表現 (今日最新)")
    
    # 拆分大盤指數與板塊
    df_indices = df[df["分類"] == "大盤"]
    df_sectors = df[df["分類"] == "板塊"]
    
    st.markdown("#### 📈 指數行情")
    cols_ind = st.columns(len(df_indices))
    for idx, row in df_indices.reset_index(drop=True).iterrows():
        with cols_ind[idx]:
            pct = row["漲跌幅(%)"]
            label = f"🔴 {row['名稱']}" if pct >= 0 else f"🟢 {row['名稱']}" # 台灣習慣紅漲綠跌
            st.metric(
                label=label,
                value=f"${row['最新價']}",
                delta=f"{row['漲跌']} ({pct:.2f}%)",
                delta_color="normal" if pct >= 0 else "inverse"
            )
            
    st.markdown("#### 📂 11 大行業板塊 (Sector ETFs)")
    cols_sec = st.columns(3)
    for idx, row in df_sectors.reset_index(drop=True).iterrows():
        col_idx = idx % 3
        with cols_sec[col_idx]:
            pct = row["漲跌幅(%)"]
            delta_str = f"+{row['漲跌']} ({pct:.2f}%)" if pct >= 0 else f"{row['漲跌']} ({pct:.2f}%)"
            # 台灣習慣：上漲紅，下跌綠
            color = "#ff4d4f" if pct >= 0 else "#2ec4b6"
            
            with st.container(border=True):
                st.markdown(f"**{row['名稱']}**")
                st.markdown(f"最新價: `${row['最新價']}`")
                st.markdown(f"<span style='color:{color}; font-weight:bold; font-size:18px;'>{delta_str}</span>", unsafe_allow_html=True)


def render_shioaji_snapshot(df: pd.DataFrame):
    """渲染 Shioaji 快照與最佳五檔 HTML/CSS 視覺化面板"""
    if df.empty:
        st.warning("沒有快照數據")
        return
        
    def _parse_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            import ast
            try:
                return ast.literal_eval(val)
            except:
                try:
                    return [float(x.strip()) for x in val.replace("[", "").replace("]", "").split(",") if x.strip()]
                except:
                    return []
        return []

    # 對於每一檔股票進行渲染
    for idx, row in df.iterrows():
        code = row["代號"]
        name = row["名稱"]
        close = row["收盤"]
        open_p = row["開盤"]
        high = row["最高"]
        low = row["最低"]
        change = row["漲跌"]
        change_rate = row["漲跌幅(%)"]
        vol = row["單量"]
        total_vol = row["總量"]
        
        # 決定顏色
        color = "#ff4b4b" if change > 0 else ("#00cc96" if change < 0 else "#888888")
        emoji = "📈" if change > 0 else ("📉" if change < 0 else "➖")
        
        with st.container(border=True):
            # 頂部即時快照卡
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div>
                    <span style="font-size:20px; font-weight:bold; color:var(--claude-text);">{name} ({code})</span>
                    <span style="margin-left:8px; font-size:14px; color:var(--claude-text-2);">即時行情</span>
                </div>
                <div style="text-align:right;">
                    <span style="font-size:22px; font-weight:bold; color:{color};">{close}</span>
                    <span style="font-size:14px; font-weight:bold; color:{color}; margin-left:5px;">{emoji} {change:+.2f} ({change_rate:+.2f}%)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 四格基本數據
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("開盤價", f"{open_p:.2f}" if isinstance(open_p, (int, float)) else str(open_p))
            c2.metric("最高 / 最低", f"{high:.2f} / {low:.2f}" if isinstance(high, (int, float)) and isinstance(low, (int, float)) else f"{high} / {low}")
            c3.metric("單筆成交量", f"{vol} 張" if isinstance(vol, (int, float)) else str(vol))
            c4.metric("今日總成交量", f"{total_vol} 張" if isinstance(total_vol, (int, float)) else str(total_vol))
            
            # 最佳五檔解析與呈現
            bid_ps = _parse_list(row.get("委買價", []))
            bid_vs = _parse_list(row.get("委買量", []))
            ask_ps = _parse_list(row.get("委賣價", []))
            ask_vs = _parse_list(row.get("委賣量", []))
            
            if bid_ps and ask_ps:
                # 委買賣十檔總量
                total_order_vol = sum(bid_vs) + sum(ask_vs)
                if total_order_vol == 0:
                    total_order_vol = 1
                
                # 掛單比率計算與條形圖 (委買紅色，委賣綠色)
                ask_data = []
                for i in range(min(5, len(ask_ps))):
                    ask_data.append((ask_ps[i], ask_vs[i]))
                ask_data = ask_data[::-1] # 委賣五到委賣一
                
                bid_data = []
                for i in range(min(5, len(bid_ps))):
                    bid_data.append((bid_ps[i], bid_vs[i]))
                
                html = f"""
                <div style="background-color:var(--claude-surface); border-radius:10px; padding:15px; border: 1px solid var(--claude-border); font-family:monospace; max-width:600px; margin:15px auto 0 auto;">
                    <div style="text-align:center; font-weight:bold; color:var(--claude-text-2); border-bottom:1px solid var(--claude-border); padding-bottom:8px; margin-bottom:8px; display:flex; justify-content:space-between;">
                        <span style="width:30%; text-align:left;">委買量(張)</span>
                        <span style="width:40%; text-align:center;">最佳五檔報價</span>
                        <span style="width:30%; text-align:right;">委賣量(張)</span>
                    </div>
                """
                
                # 1. 委賣
                for ap, av in ask_data:
                    pct = (av / total_order_vol) * 100
                    html += f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; height:24px; margin-bottom:4px;">
                        <span style="width:30%; text-align:left; color:var(--claude-text-2);">-</span>
                        <span style="width:40%; text-align:center; color:#00cc96; font-weight:bold;">{ap:.2f}</span>
                        <div style="width:30%; display:flex; align-items:center; justify-content:flex-end;">
                            <span style="margin-right:8px; font-weight:bold; color:#00cc96;">{av}</span>
                            <div style="width:60px; background-color:var(--claude-border-light); height:8px; border-radius:4px; overflow:hidden;">
                                <div style="width:{pct:.1f}%; background-color:#00cc96; height:100%;"></div>
                            </div>
                        </div>
                    </div>
                    """
                
                # 2. 成交價
                html += f"""
                <div style="text-align:center; margin: 8px 0; border-top:1px dashed var(--claude-border); border-bottom:1px dashed var(--claude-border); padding:6px 0; background-color:var(--claude-bg);">
                    <span style="color:var(--claude-text-2); font-weight:bold; font-size:12px;">最新成交價</span>
                    <span style="color:{color}; font-weight:bold; font-size:18px; margin-left:10px;">{close:.2f}</span>
                </div>
                """
                
                # 3. 委買
                for bp, bv in bid_data:
                    pct = (bv / total_order_vol) * 100
                    html += f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; height:24px; margin-top:4px;">
                        <div style="width:30%; display:flex; align-items:center; justify-content:flex-start;">
                            <div style="width:60px; background-color:var(--claude-border-light); height:8px; border-radius:4px; overflow:hidden; margin-right:8px;">
                                <div style="width:{pct:.1f}%; background-color:#ff4b4b; height:100%;"></div>
                            </div>
                            <span style="font-weight:bold; color:#ff4b4b;">{bv}</span>
                        </div>
                        <span style="width:40%; text-align:center; color:#ff4b4b; font-weight:bold;">{bp:.2f}</span>
                        <span style="width:30%; text-align:right; color:var(--claude-text-2);">-</span>
                    </div>
                    """
                
                html += "</div>"
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.info("⚠️ 盤後或未提供最佳五檔價量資料。")


def render_shioaji_contract(df: pd.DataFrame):
    """渲染官方合約細節 (Glassmorphic 名冊)"""
    if df.empty:
        st.warning("無合約資訊。")
        return
    st.markdown("### 📜 證券官方合約與交易限制明細")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        c_dict = dict(zip(df["屬性"], df["官方設定值"]))
        
        with col1:
            st.markdown(f"**股票代號：** `{c_dict.get('股票代號', 'N/A')}`")
            st.markdown(f"**股票名稱：** `{c_dict.get('股票名稱', 'N/A')}`")
            st.markdown(f"**上市市場/交易所：** `{c_dict.get('交易所', 'N/A')}`")
            st.markdown(f"**產業類別：** `{c_dict.get('產業類別', 'N/A')}`")
            st.markdown(f"**現股當沖 / 資券互抵：** `{c_dict.get('現股當沖/資券互抵', 'N/A')}`")
            
        with col2:
            st.markdown(f"**是否可融資交易：** `{c_dict.get('是否可信用融資', 'N/A')}`")
            st.markdown(f"**是否可融券交易：** `{c_dict.get('是否可信用融券', 'N/A')}`")
            st.markdown(f"**融資成數/比率：** `{c_dict.get('融資成數/比率', 'N/A')}`")
            st.markdown(f"**融券保證金成數：** `{c_dict.get('融券保證金成數', 'N/A')}`")
            
        st.divider()
        
        c_ref, c_up, c_down = st.columns(3)
        c_ref.metric("昨日參考價", f"${c_dict.get('今日參考價', 'N/A')}")
        c_up.metric("🔴 今日漲停價", f"${c_dict.get('今日漲停價', 'N/A')}")
        c_down.metric("🟢 今日跌停價", f"${c_dict.get('今日跌停價', 'N/A')}")


def render_shioaji_big_orders(df_dict: dict):
    """渲染主力大單分析與資金流向圓餅圖"""
    summary = df_dict.get("summary", pd.DataFrame())
    detail = df_dict.get("detail", pd.DataFrame())
    
    if summary.empty:
        st.error("查無大單統計數據。")
        return
        
    sum_dict = dict(zip(summary["指標項目"], summary["數值"]))
    
    total_ticks = sum_dict.get("總成交筆數", 0)
    total_volume = sum_dict.get("總成交張數", 0)
    total_amount = sum_dict.get("總成交金額 (元)", 0.0)
    
    big_buy_cnt = sum_dict.get("主力大單買入筆數", 0)
    big_buy_vol = sum_dict.get("主力大單買入張數", 0)
    big_buy_amt = sum_dict.get("主力大單買入金額 (元)", 0.0)
    
    big_sell_cnt = sum_dict.get("主力大單賣出筆數", 0)
    big_sell_vol = sum_dict.get("主力大單賣出張數", 0)
    big_sell_amt = sum_dict.get("主力大單賣出金額 (元)", 0.0)
    
    net_buy_amt = sum_dict.get("主力大單淨流入金額 (元)", 0.0)
    big_pct = sum_dict.get("大單佔總成交金額比例(%)", 0.0)
    
    with st.container(border=True):
        st.markdown("### 📊 主力大單資金流向分析")
        
        c1, c2, c3 = st.columns(3)
        net_color = "#ff4b4b" if net_buy_amt > 0 else ("#00cc96" if net_buy_amt < 0 else "#888888")
        net_symbol = "➕" if net_buy_amt > 0 else ("" if net_buy_amt < 0 else "")
        
        c1.metric("主力大單買入總額", f"{big_buy_amt/10000:.1f} 萬元" if isinstance(big_buy_amt, (int, float)) else str(big_buy_amt), f"{big_buy_cnt} 筆")
        c2.metric("主力大單賣出總額", f"{big_sell_amt/10000:.1f} 萬元" if isinstance(big_sell_amt, (int, float)) else str(big_sell_amt), f"{big_sell_cnt} 筆")
        
        with c3:
            net_val_str = f"{net_symbol}{net_buy_amt/10000:.1f} 萬" if isinstance(net_buy_amt, (int, float)) else str(net_buy_amt)
            st.markdown(f"""
            <div style="background-color:#F8FAFC; padding:10px; border-radius:8px; border:1px solid #E2E8F0; text-align:center;">
                <span style="font-size:12px; color:#64748B; font-weight:bold;">主力大單淨流入</span><br/>
                <span style="font-size:22px; font-weight:bold; color:{net_color};">{net_val_str}</span>
            </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        
        col_chart, col_detail = st.columns([1, 1])
        
        with col_chart:
            st.caption("🎯 大單佔總成交金額比例與資金方向")
            normal_amt = max(0.0, total_amount - big_buy_amt - big_sell_amt) if isinstance(total_amount, (int, float)) and isinstance(big_buy_amt, (int, float)) and isinstance(big_sell_amt, (int, float)) else 0.0
            
            labels = ["大單買入", "大單賣出", "一般成交"]
            values = [big_buy_amt, big_sell_amt, normal_amt]
            colors = ["#ff4b4b", "#00cc96", "#E2E8F0"]
            
            fig = go.Figure(data=[go.Pie(
                labels=labels, 
                values=values, 
                hole=.4,
                marker=dict(colors=colors),
                textinfo="percent+label"
            )])
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                height=250,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            
            net_解读_str = "買方力道強勁，主力呈淨買超流入！" if isinstance(net_buy_amt, (int, float)) and net_buy_amt > 0 else "賣方力道沉重，主力呈淨賣出流出！"
            st.markdown(f"""
            <div style="background-color:#EFF6FF; border-left:4px solid #3B82F6; padding:10px; border-radius:4px; font-size:13px; color:#1E3A8A;">
                ℹ️ <b>籌碼解讀：</b>本交易日主力大單佔總成交金額 <b>{big_pct:.1f}%</b>。
                大單淨流入為 <b style="color:{net_color};">{net_val_str}</b>。<br/>
                {net_解读_str}
            </div>
            """, unsafe_allow_html=True)
            
        with col_detail:
            st.caption("📋 最新 50 筆大單明細")
            if not detail.empty and "說明" not in detail.columns:
                df_show = detail.copy()
                df_show["金額"] = df_show["金額"].apply(lambda x: f"{x/10000:.1f} 萬" if isinstance(x, (int, float)) else str(x))
                st.dataframe(df_show, use_container_width=True, hide_index=True)
            elif not detail.empty:
                st.write(detail)
            else:
                st.info("無達到門檻的大單資料。")
