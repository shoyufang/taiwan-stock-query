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

def display_result(df, query_type: str = "", enable_export: bool = True):
    """智能呈現結果 — 根據類型自動選擇表格 / 圖表。

    df 通常是 pd.DataFrame；若 dispatch 失敗，會收到 dict {"error": "..."}，
    本函式優先處理錯誤 dict 與 None，再做型別判斷。
    """
    # 錯誤 dict（dispatch helper 失敗時回傳）
    if isinstance(df, dict):
        if "error" in df:
            st.error(df["error"])
            return
        st.json(df)
        return

    if df is None:
        st.warning("沒有查詢結果")
        return

    if not isinstance(df, pd.DataFrame):
        st.write(df)
        return

    if df.empty:
        st.warning("沒有查詢結果")
        return

    result_type = detect_result_type(df, query_type)
    df_display = truncate_dataframe(df)

    # 根據類型呈現
    if result_type == ResultType.KBAR:
        display_kbar(df_display)
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
    """顯示表格"""
    st.subheader("📊 查詢結果")
    st.dataframe(df, use_container_width=True, height=400)

def display_kbar(df: pd.DataFrame):
    """顯示 K線圖 + OHLC 表"""
    st.subheader("📈 K線圖")

    # 確定日期和 OHLC 欄位名稱
    date_col = None
    open_col, high_col, low_col, close_col = None, None, None, None

    col_lower = {c.lower(): c for c in df.columns}

    for col in df.columns:
        col_lower_val = col.lower()
        if col_lower_val in ['date', '日期']:
            date_col = col
        if col_lower_val in ['open', '開盤']:
            open_col = col
        if col_lower_val in ['high', '最高']:
            high_col = col
        if col_lower_val in ['low', '最低']:
            low_col = col
        if col_lower_val in ['close', '收盤']:
            close_col = col

    if not all([open_col, high_col, low_col, close_col]):
        st.warning("K線資料不完整")
        display_table(df)
        return

    # 使用 Plotly 繪製 K線圖
    if date_col:
        try:
            df['Date'] = pd.to_datetime(df[date_col], utc=True).dt.tz_localize(None)
        except Exception:
            try:
                df['Date'] = pd.to_datetime(df[date_col])
            except Exception:
                df['Date'] = range(len(df))
    else:
        df['Date'] = range(len(df))

    fig = go.Figure(data=[go.Candlestick(
        x=df['Date'],
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col]
    )])

    fig.update_layout(
        title="K線圖",
        yaxis_title="價格",
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

    # 下方顯示表格
    st.subheader("OHLC 詳細資料")
    display_table(df[[date_col or '日期', open_col, high_col, low_col, close_col]] if date_col else df)

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
    """渲染側邊欄選單 — 返回選中的 Tab"""
    with st.sidebar:
        st.markdown("## 📋 導航")
        selected_tab = st.radio("選擇查詢類型", available_tabs, label_visibility="collapsed")
        return selected_tab

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
    """渲染查詢歷史區域"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📋 最近查詢")
        if not history:
            st.caption("暫無歷史")
            return None

        selected_history = st.selectbox(
            "最近查詢",
            options=history,
            format_func=lambda x: f"{x.get('tab', '')} - {x.get('timestamp', '')[:10]}",
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

            st.markdown("**Google Gemini**")
            gemini_api_key = st.text_input("Gemini API Key", value=config.get("gemini_api_key", ""), type="password", key="gemini_api_key_input", placeholder="AIzaSy...")
            
            # 初始化可用模型列表
            from gemini_engine import GeminiEngine
            
            # 使用 session_state 暫存模型列表，避免每次 UI 刷新都重新打 API
            if "available_gemini_models" not in st.session_state:
                st.session_state.available_gemini_models = []
                # 如果已有 Key，嘗試初始化讀取一次
                if gemini_api_key:
                    try:
                        st.session_state.available_gemini_models = GeminiEngine.list_available_models(gemini_api_key)
                    except:
                        pass

            col_fetch, col_info = st.columns([1, 2])
            with col_fetch:
                if st.button("🔍 獲取模型列表", key="fetch_gemini_models"):
                    if gemini_api_key:
                        with st.spinner("獲取中..."):
                            st.session_state.available_gemini_models = GeminiEngine.list_available_models(gemini_api_key)
                            if st.session_state.available_gemini_models:
                                st.success("已更新清單")
                            else:
                                st.error("獲取失敗")
                    else:
                        st.warning("請先輸入 Key")

            # 準備選單內容
            current_model = config.get("gemini_model", "")
            models_list = st.session_state.available_gemini_models
            if not models_list:
                models_list = ["(點擊上方按鈕獲取)"]
                model_index = 0
            else:
                if current_model in models_list:
                    model_index = models_list.index(current_model)
                else:
                    model_index = 0

            gemini_model = st.selectbox("Gemini 模型選擇", models_list, index=model_index, key="gemini_model_select")

            # 已有模型時預設開啟手動輸入（避免下拉清單空白時清掉設定）
            has_existing_model = bool(current_model and current_model != "(點擊上方按鈕獲取)")
            use_custom_model = st.checkbox("手動輸入模型名稱", value=has_existing_model, key="use_custom_gemini")
            if use_custom_model:
                custom_model_name = st.text_input("輸入自訂模型代號", value=current_model, placeholder="例：gemini-2.5-flash-preview-05-20")
                final_model = custom_model_name
            else:
                final_model = gemini_model if gemini_model != "(點擊上方按鈕獲取)" else current_model

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 保存", key="save_keys"):
                    config["api_key"] = api_key
                    config["secret_key"] = secret_key
                    config["finmind_token"] = finmind_token
                    config["notion_token"] = notion_token
                    config["notion_database_id"] = notion_db_id
                    config["gemini_api_key"] = gemini_api_key
                    config["gemini_model"] = final_model if final_model != "(點擊上方按鈕獲取)" else ""
                    from config import save_config
                    save_config(config)
                    st.success(f"✅ 設定已保存：{config['gemini_model']}")
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

def date_input_section(label: str = "選擇日期範圍", default_days: int = 30) -> tuple:
    """日期輸入區域 — 返回 (start_date, end_date)"""
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "開始日期",
            value=date.today() - timedelta(days=default_days)
        )
    with col2:
        end_date = st.date_input(
            "結束日期",
            value=date.today()
        )
    return start_date, end_date

def code_input_section(label: str = "輸入股票代號", single: bool = True) -> str | list:
    """股票代號輸入區域"""
    if single:
        return st.text_input(label, placeholder="例：2330").strip()
    else:
        codes_str = st.text_input(label, placeholder="例：2330,2412,3008，用逗號分隔")
        return [c.strip() for c in codes_str.split(",") if c.strip()] if codes_str else []
