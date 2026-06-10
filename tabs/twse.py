"""
TWSE OpenAPI 擴充查詢分頁
"""

import streamlit as st
import pandas as pd
from logging_config import main_logger
import query_wrapper as qw
from tabs._shared import _render_batch_results


_TWSE_ESG_MAP = {  # 保留供 dispatch 參照，UI 已不顯示
    1: "溫室氣體排放", 2: "能源管理", 3: "用水管理", 4: "廢棄物管理",
    5: "人力資源發展", 6: "董事會", 7: "投資人溝通", 8: "氣候相關議題管理",
    9: "功能性委員會", 10: "燃料管理", 11: "產品生命週期管理", 12: "食品安全",
    13: "供應鏈管理", 14: "產品品質與安全", 15: "社區關係", 16: "資訊安全",
    17: "普惠金融", 18: "股權與控制", 19: "風險管理政策",
    20: "反競爭行為法律爭議", 21: "職業安全衛生",
}
_TWSE_ESG_REV = {v: k for k, v in _TWSE_ESG_MAP.items()}
_TWSE_IND_MAP = {
    "綜合損益表(一般業)": "ci",  "綜合損益表(金融業)": "basi",
    "綜合損益表(證券期貨)": "bd", "綜合損益表(金控保險)": "fh",
    "綜合損益表(KY外國)": "mim", "綜合損益表(保險業)": "ins",
}
_TWSE_BS_MAP = {"資產負債表(一般業)": "ci", "資產負債表(KY外國)": "mim"}


def _twse_dispatch(qt: str, code: str = "") -> tuple:
    """根據項目名稱執行對應 TWSE 查詢，回傳 (result, needs_code)。"""
    c = code.strip() or None
    if qt == "當日全市場行情":    return qw.query_twse_daily_all(c), False
    if qt == "月均價":            return qw.query_twse_stock_day_avg(c), False
    if qt == "月成交資訊":        return qw.query_twse_monthly(c), False
    if qt == "年成交資訊":        return qw.query_twse_annual(c), False
    if qt == "大盤指數":          return qw.query_twse_mi_index(), False
    if qt == "當日三大法人":      return qw.query_twse_institutional(c), False
    if qt == "融資融券彙總":      return qw.query_twse_margin(c), False
    if qt == "外資持股(產業)":    return qw.query_twse_qfiis_cat(), False
    if qt == "外資持股前20":      return qw.query_twse_qfiis_top20(), False
    if qt == "本益比/殖利率":     return qw.query_twse_valuation(c), False
    if qt == "公司基本資料":
        if not c:
            return {"error": "⚠️ 公司基本資料需輸入股票代號"}, True
        return qw.query_twse_company(c), True
    if qt == "最近上市":          return qw.query_twse_newlisting(), False
    if qt == "下市公司":          return qw.query_twse_suspend_listing(), False
    if qt == "申請上市(國內)":    return qw.query_twse_apply_listing_local(), False
    if qt == "申請上市(外國)":    return qw.query_twse_apply_listing_foreign(), False
    if qt == "處置股清單":        return qw.query_twse_disposition(), False
    if qt == "注意股清單":        return qw.query_twse_notice(), False
    if qt == "官方新聞":          return qw.query_twse_news_list(), False
    if qt == "活動公告":          return qw.query_twse_event_list(), False
    if qt == "月營收彙總":        return qw.query_twse_monthly_revenue(), False
    if qt == "股利分派":          return qw.query_twse_dividend_policy(), False
    if qt == "基金基本資訊":      return qw.query_twse_fund_basic(), False
    if qt in _TWSE_IND_MAP:       return qw.query_twse_income_statement(_TWSE_IND_MAP[qt]), False
    if qt in _TWSE_BS_MAP:        return qw.query_twse_balance_sheet_openapi(_TWSE_BS_MAP[qt]), False
    if qt == "ETF定期定額排行":   return qw.query_twse_etf_rank(), False
    if qt in _TWSE_ESG_REV:       return qw.query_twse_esg(_TWSE_ESG_REV[qt]), False
    return {"error": f"未知項目：{qt}"}, False


def render_twse_section():
    """TWSE 證交所查詢（OpenAPI 全端點）—— 複選批次模式"""
    main_logger.info("渲染 TWSE Tab")

    # ── 今日快取狀態欄 ─────────────────────────────────────
    try:
        cache_info = qw.twse_cache_status()
        ready = [c for c, v in cache_info.items() if v["exists"]]
        total = len(cache_info)
        if len(ready) == total:
            st.success(f"✅ 今日 TWSE 資料已快取（{total}/{total} 項）— 查詢速度更快", icon="⚡")
        elif ready:
            st.info(
                f"📦 今日快取：{len(ready)}/{total} 項已就緒  "
                f"（{', '.join(ready)}）\n\n"
                "未快取項目將即時呼叫 API。快取每天 20:05 自動更新。",
                icon="📡",
            )
        else:
            st.warning(
                "📡 今日尚無本地快取，所有查詢將即時呼叫 TWSE API。\n\n"
                "快取將於今日 20:05 自動下載（或週末/假日無資料）。",
                icon="⏳",
            )
    except Exception:
        pass  # 狀態顯示失敗不影響主功能

    GROUPS = [
        ("📊 行情資訊",   ["當日全市場行情", "月均價", "月成交資訊", "年成交資訊", "大盤指數"]),
        ("🏦 法人/籌碼",  ["當日三大法人", "融資融券彙總", "外資持股(產業)", "外資持股前20"]),
        ("📈 估值",       ["本益比/殖利率"]),
        ("🏢 公司資訊",   ["公司基本資料", "最近上市", "下市公司", "申請上市(國內)", "申請上市(外國)"]),
        ("⚠️ 注意/處置", ["處置股清單", "注意股清單"]),
        ("📰 新聞公告",   ["官方新聞", "活動公告"]),
        ("💰 財報/股利",  ["月營收彙總", "股利分派", "基金基本資訊",
                           "綜合損益表(一般業)", "綜合損益表(金融業)", "綜合損益表(證券期貨)",
                           "綜合損益表(金控保險)", "綜合損益表(KY外國)", "綜合損益表(保險業)",
                           "資產負債表(一般業)", "資產負債表(KY外國)"]),
        ("📊 ETF",        ["ETF定期定額排行"]),
    ]

    # ── 上半：複選 Checkbox（左右 2 欄） ─────────────────────
    with st.container(border=True):
        col_left, col_right = st.columns(2)
        half = (len(GROUPS) + 1) // 2
        for gi, (caption, options) in enumerate(GROUPS):
            with col_left if gi < half else col_right:
                hc1, hc2 = st.columns([4, 1])
                with hc1:
                    st.caption(caption)
                with hc2:
                    if st.button("全選", key=f"twse_selall_{gi}",
                                 use_container_width=True):
                        for oi in range(len(options)):
                            st.session_state[f"twse_cb_{gi}_{oi}"] = True
                for oi, opt in enumerate(options):
                    st.checkbox(opt, key=f"twse_cb_{gi}_{oi}")

    # ── 篩選代號輸入 + 確認按鈕 ─────────────────────────────
    param_col, btn_col = st.columns([3, 1])
    with param_col:
        code_filter = st.text_input(
            "篩選代號", placeholder="例：2330（留空查全市場）",
            key="twse_batch_code", label_visibility="collapsed",
        )
    with btn_col:
        run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True)

    # 勾選摘要
    selected = [
        opt
        for gi, (_, options) in enumerate(GROUPS)
        for oi, opt in enumerate(options)
        if st.session_state.get(f"twse_cb_{gi}_{oi}", False)
    ]
    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected[:8])}{'…' if len(selected) > 8 else ''}")

    st.divider()

    # ── 下半：批次執行 + 結果統一顯示 ──────────────────────
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result, _ = _twse_dispatch(item, code_filter)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["twse_batch_results"] = results

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "TWSE",
                "params": {
                    "type": "twse_batch",
                    "selected": selected,
                    "code": code_filter
                },
                "default_name": f"TWSE批次 ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

    _render_batch_results("twse_batch_results")
