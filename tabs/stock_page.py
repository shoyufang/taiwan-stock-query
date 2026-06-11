"""
個股全景頁 — 一個代號看完所有面向（殺手級功能）
Phase A: 代號輸入框 + 導向提示（Phase C 實作完整五分頁）
"""
import streamlit as st
from stock_lookup import resolve_code, get_name_hint


def render_stock_page():
    """個股全景頁面（Phase C 實作）。Phase A: 簡易代號查詢入口。"""
    st.markdown("### 🔍 個股全景")
    st.caption("輸入股票代號或中文名稱，快速查看完整個股資料（技術、籌碼、基本面、五檔大單、新聞/AI）")

    col_code, col_search, col_empty = st.columns([2, 1, 2])
    with col_code:
        raw_code = st.text_input("股票代號 / 中文名稱", placeholder="例：2330、台積電、NVDA", key="stock_page_code_input")
    with col_search:
        do_search = st.button("🔍 查詢", use_container_width=True, type="primary")

    if do_search and raw_code:
        code = resolve_code(raw_code)
        if code:
            hint = get_name_hint(raw_code) if raw_code.isdigit() or len(raw_code) > 2 else f"已解析: **{raw_code}** → **{code}**"
            st.success(hint)
            st.info(f"完整個股全景功能（Phase C）尚未實作。目前可前往以下頁面查詢 **{code}**：")
            cols = st.columns(3)
            with cols[0]:
                if st.button("📈 技術分析", use_container_width=True):
                    st.session_state.selected_tab = "技術分析"
                    st.rerun()
            with cols[1]:
                if st.button("📊 選股中心", use_container_width=True):
                    st.session_state.selected_tab = "選股中心"
                    st.rerun()
            with cols[2]:
                if st.button("🌐 全球市場", use_container_width=True):
                    st.session_state.selected_tab = "全球市場"
                    st.rerun()
        else:
            st.warning(f"找不到 '{raw_code}' 對應的股票代號")
    elif not raw_code:
        st.caption("💡 提示：此頁面將整合技術分析、籌碼面、基本面、五檔大單與新聞/AI 於一頁")
