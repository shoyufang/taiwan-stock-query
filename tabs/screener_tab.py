"""
多因子選股篩選器 UI 模組 (台股選股 + 美股選股)
"""

import streamlit as st
import pandas as pd
from logging_config import main_logger
import us_screener as usc
import screener as sc


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
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="美股選股結果", index=False)
        st.download_button("⬇ 下載美股選股 Excel", data=buf.getvalue(),
                           file_name=f"美股選股_{label}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        main_logger.error(f"美股選股結果匯出 Excel 失敗: {str(e)}")


def render_us_screener():
    """美股多因子選股頁面"""
    st.caption("基於 50 檔美股巨頭/藍籌股，提供中長期基本面與安全邊際多因子量化篩選")

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


def _screener_result_block(df: pd.DataFrame, label: str):
    """顯示選股結果並提供 Excel 下載"""
    if df is None or df.empty:
        st.info("無符合條件的股票")
        return
    st.success(f"找到 **{len(df)}** 檔符合「{label}」")
    st.dataframe(df, use_container_width=True, hide_index=True)
    try:
        import io
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
        excl_etf = c1.checkbox("排除 ETF", value=True, key=f"{prefix}_etf")
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
        pe_on = col1.checkbox("本益比 ≤", value=False, key="fb_pe_on")
        pb_on = col2.checkbox("股淨比 ≤", value=False, key="fb_pb_on")
        yld_on = col3.checkbox("殖利率 ≥", value=False, key="fb_yld_on")
        pe_v = col1.number_input("本益比上限", value=20.0, min_value=0.1, key="fb_pe_v",
                                  disabled=not pe_on)
        pb_v = col2.number_input("股淨比上限", value=2.0, min_value=0.1, key="fb_pb_v",
                                  disabled=not pb_on)
        yld_v = col3.number_input("殖利率下限 (%)", value=3.0, min_value=0.0, key="fb_yld_v",
                                   disabled=not yld_on)

        st.markdown("**FinMind 月營收**")
        col4, col5 = st.columns(2)
        ryoy_on = col4.checkbox("月營收 YOY ≥ (%)", value=False, key="fb_ryoy_on")
        rcons_on = col5.checkbox("月營收連續正成長", value=False, key="fb_rcons_on")
        ryoy_v = col4.number_input("YOY 成長率下限 (%)", value=10.0, key="fb_ryoy_v",
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
            pe2_on = st.checkbox("本益比 ≤", key="mf_pe_on")
            pe2_v = st.number_input("本益比上限", value=20.0, key="mf_pe_v", disabled=not pe2_on)
            pb2_on = st.checkbox("股淨比 ≤", key="mf_pb_on")
            pb2_v = st.number_input("股淨比上限", value=2.0, key="mf_pb_v", disabled=not pb2_on)
            yld2_on = st.checkbox("殖利率 ≥ (%)", key="mf_yld_on")
            yld2_v = st.number_input("殖利率下限", value=3.0, key="mf_yld_v", disabled=not yld2_on)
            ryoy2_on = st.checkbox("月營收 YOY ≥ (%)", key="mf_ryoy_on")
            ryoy2_v = st.number_input("YOY 下限", value=10.0, key="mf_ryoy_v", disabled=not ryoy2_on)

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
