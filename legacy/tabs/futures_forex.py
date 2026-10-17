"""
期貨/匯率查詢分頁
"""

import streamlit as st
import pandas as pd
from logging_config import main_logger
import query_wrapper as qw
from ui_components import date_input_section
from tabs._shared import _render_batch_results


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
