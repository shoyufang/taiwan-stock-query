"""
台股市場分頁
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from logging_config import main_logger
import query_wrapper as qw
from ui_components import code_input_section, date_input_section
from tabs._shared import _render_batch_results


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
