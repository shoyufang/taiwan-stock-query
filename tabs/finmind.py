"""
FinMind 籌碼面/基本面查詢分頁
"""

import streamlit as st
import pandas as pd
from logging_config import main_logger
import query_wrapper as qw
from ui_components import code_input_section, date_input_section
from tabs._shared import _render_batch_results


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
