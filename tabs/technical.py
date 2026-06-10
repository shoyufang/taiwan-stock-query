"""
雙引擎技術分析圖表 UI 模組
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from logging_config import main_logger
import technical_analysis as ta
from theme import THEMES
from config import add_history
import query_wrapper as qw


def render_technical_analysis():
    """技術分析 — K線圖 + 技術指標（Plotly互動式）"""
    main_logger.info("渲染技術分析 Tab")

    st.markdown("""
    ### 📈 K 線圖分析
    使用 **Plotly** 互動式圖表，支援各項技術指標。
    """)

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
