"""
投資行事曆 — 台股法說/除息 + 美股財報 + 華爾街共識
Phase A: 暫時用 st.tabs 包既有 render
"""
import streamlit as st


def render_calendar_tab():
    """投資行事曆頁面（Phase D.3 實作）。Phase A: 委派至既有渲染器。"""
    from tabs.us_calendar_tab import render_us_calendar_consensus

    st.markdown("### 📅 投資行事曆")
    st.caption("台股法說/除息 · 美股財報 · 華爾街共識")

    tab_tw, tab_us = st.tabs(["🇹🇼 台股法說/除息", "🇺🇸 美股財報 & 共識"])

    with tab_tw:
        _render_tw_calendar()

    with tab_us:
        render_us_calendar_consensus()


def _render_tw_calendar():
    """台股法說/除息日曆 — 呼叫 tw_calendar 模組。"""
    import tw_calendar as twc
    import streamlit as st
    import pandas as pd

    st.markdown("#### 🇹🇼 台股法說會與除息日曆")
    st.caption("基於 50 檔台股權值巨頭，提供法說會日期、預估 EPS、除息日")

    with st.spinner("正在加載台股日曆數據..."):
        try:
            df_all = twc.get_tw_calendar_consensus_data(force_refresh=False)
        except Exception as e:
            st.error(f"加載數據失敗: {e}")
            return

    if df_all.empty:
        st.error("❌ 無法取得台股日曆數據。請檢查網路或稍後再試。")
        return

    col_l, col_r = st.columns([4, 1])
    with col_r:
        force_refresh = st.button("🔄 強制重新整理", key="tw_cal_refresh",
                                   use_container_width=True,
                                   help="清空 24 小時快取並重新抓取")

    if force_refresh:
        try:
            df_all = twc.get_tw_calendar_consensus_data(force_refresh=True)
        except Exception as e:
            st.error(f"重新整理失敗: {e}")
            return

    # 過濾近期（未來 60 天）— 取「財報公佈日」與「除息日」較近者作為排序依據
    from datetime import datetime, timedelta
    now = datetime.now()
    cutoff = pd.Timestamp(now + timedelta(days=60))

    def _parse(col: str) -> pd.Series:
        return pd.to_datetime(df_all[col], errors="coerce") if col in df_all.columns else pd.Series(pd.NaT, index=df_all.index)

    earnings_dt = _parse("財報公佈日")
    exdiv_dt = _parse("除息日")
    df_all = df_all.copy()
    df_all["_最近日期"] = earnings_dt.combine(exdiv_dt, lambda a, b: min(x for x in (a, b) if pd.notna(x)) if pd.notna(a) or pd.notna(b) else pd.NaT)

    df_recent = df_all[df_all["_最近日期"].isna() | (df_all["_最近日期"] <= cutoff)].copy()

    if df_recent.empty:
        st.info("近期無相關日程")
        return

    df_recent = df_recent.sort_values("_最近日期", ascending=True, na_position="last")

    # 格式化顯示
    display_df = df_recent.drop(columns=["_最近日期"]).copy()
    for col in ["預估下季EPS", "預估營收(B元)"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(
                lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and pd.notna(x) else "-"
            )

    st.dataframe(display_df, use_container_width=True, hide_index=True)
