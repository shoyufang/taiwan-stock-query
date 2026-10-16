"""
通用查詢結果顯示元件（2026-07-07 從 ui_components.py 拆出）
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from utils import ResultType, detect_result_type, format_number, truncate_dataframe
from ui.us import (
    render_us_company_profile, render_us_financials, render_us_holders,
    render_us_analyst_info, render_us_sector_performance_dashboard,
)
from ui.shioaji import render_shioaji_snapshot, render_shioaji_contract, render_shioaji_big_orders


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

        styled = df.style.map(color_change, subset=change_cols)
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
