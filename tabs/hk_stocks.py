"""
港美股專區分頁 (Futu OpenAPI)
"""

import streamlit as st
import pandas as pd
from datetime import date
from logging_config import main_logger
import query_wrapper as qw
from ui_components import date_input_section
from tabs._shared import _render_batch_results


def _hkus_dispatch(qt, market, codes, plate_code, start_date, end_date):
    """分派港美股查詢。"""
    first_code = codes[0] if codes else ""
    if qt == "市場開收盤狀態":   return qw.query_futu_market_state()
    if qt == "港/美股日K":
        if not first_code:
            return {"error": "⚠️ 港/美股日K 需輸入股票代號"}
        return qw.query_futu_kbar(first_code, start_date, end_date)
    if qt == "股票基本資訊":
        if not codes:
            return {"error": "⚠️ 股票基本資訊需輸入股票代號"}
        return qw.query_futu_basicinfo(market, codes)
    if qt == "資金分布":
        if not first_code:
            return {"error": "⚠️ 資金分布需輸入股票代號"}
        return qw.query_futu_capital_distribution(first_code)
    if qt == "資金流向":
        if not first_code:
            return {"error": "⚠️ 資金流向需輸入股票代號"}
        return qw.query_futu_capital_flow(first_code)
    if qt == "板塊列表":         return qw.query_futu_plate_list(market)
    if qt == "板塊成分股":
        if not plate_code:
            return {"error": "⚠️ 板塊成分股需輸入板塊代號"}
        return qw.query_futu_plate_stocks(plate_code)
    if qt == "股票所屬板塊":
        if not codes:
            return {"error": "⚠️ 股票所屬板塊需輸入股票代號"}
        return qw.query_futu_owner_plate(codes)
    return {"error": f"未知項目：{qt}"}


def render_hk_us_stocks():
    """港美股查詢 (Futu OpenAPI) —— 複選批次模式"""
    main_logger.info("渲染港美股 Tab")
    st.info("港美股查詢需要本機運行 FutuOpenD (https://openapi.futunn.com)")

    MARKET_ITEMS = ["市場開收盤狀態", "板塊列表", "板塊成分股"]
    STOCK_ITEMS  = ["港/美股日K", "股票基本資訊", "資金分布", "資金流向", "股票所屬板塊"]

    # ── 上半：複選區（左=市場/板塊，右=個股查詢） ─────────────
    with st.container(border=True):
        col_l, col_r = st.columns(2)
        with col_l:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("🌍 市場 / 板塊")
            with hc2:
                if st.button("全選", key="hk_all_m", use_container_width=True):
                    for i in range(len(MARKET_ITEMS)):
                        st.session_state[f"hk_cb_m_{i}"] = True
            for i, opt in enumerate(MARKET_ITEMS):
                st.checkbox(opt, key=f"hk_cb_m_{i}")
        with col_r:
            hc1, hc2 = st.columns([4, 1])
            with hc1:
                st.caption("📈 個股查詢")
            with hc2:
                if st.button("全選", key="hk_all_s", use_container_width=True):
                    for i in range(len(STOCK_ITEMS)):
                        st.session_state[f"hk_cb_s_{i}"] = True
            for i, opt in enumerate(STOCK_ITEMS):
                st.checkbox(opt, key=f"hk_cb_s_{i}")

    selected_m = [opt for i, opt in enumerate(MARKET_ITEMS) if st.session_state.get(f"hk_cb_m_{i}", False)]
    selected_s = [opt for i, opt in enumerate(STOCK_ITEMS)  if st.session_state.get(f"hk_cb_s_{i}", False)]
    selected   = selected_m + selected_s

    # ── 條件參數區 ────────────────────────────────────────
    needs_market = any(x in selected for x in ["股票基本資訊", "板塊列表"])
    needs_codes  = any(x in selected for x in ["港/美股日K", "股票基本資訊", "資金分布", "資金流向", "股票所屬板塊"])
    needs_plate  = "板塊成分股" in selected
    needs_date   = "港/美股日K" in selected

    market = "HK"
    if needs_market:
        market = st.selectbox("市場", ["HK", "US"], key="hk_market")

    codes = []
    if needs_codes:
        codes_str = st.text_input(
            "股票代號（逗號分隔可多碼）",
            placeholder="例：HK.00700, US.AAPL",
            key="hk_codes",
        )
        codes = [c.strip() for c in codes_str.split(",") if c.strip()]

    plate_code = ""
    if needs_plate:
        plate_code = st.text_input(
            "板塊代號", placeholder="例：HK.BK1000（藍籌股）", key="hk_plate_code"
        )

    start_date = end_date = date.today()
    if needs_date:
        start_date, end_date = date_input_section(default_days=365, key_prefix="hk_")

    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")

    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True,
                          key="hk_run_batch")

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
                    result = _hkus_dispatch(item, market, codes, plate_code,
                                            start_date, end_date)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["hk_batch_results"] = (results, codes[0] if codes else "")

    _render_batch_results("hk_batch_results")
