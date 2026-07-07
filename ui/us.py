"""
美股專屬渲染元件（2026-07-07 從 ui_components.py 拆出）
"""

import streamlit as st
import pandas as pd


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
