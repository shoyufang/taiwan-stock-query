"""
選股中心 — 台股選股 + 美股選股 + 技術掃描三合一
Phase A: 暫時用 st.tabs 包既有 render
"""
import streamlit as st


def render_screener_hub():
    """選股中心頁面（Phase D.1 實作）。Phase A: 委派至既有渲染器。"""
    from tabs.screener_tab import render_screener, render_us_screener
    from tabs.technical_scanner import render_technical_scanner

    st.markdown("### 🎯 選股中心")
    st.caption("台股選股 · 美股選股 · 技術掃描 — 三合一篩選器")

    tab_tw, tab_us, tab_tech = st.tabs(["🇹🇼 台股選股", "🇺🇸 美股選股", "📡 技術掃描"])

    with tab_tw:
        render_screener()

    with tab_us:
        render_us_screener()

    with tab_tech:
        render_technical_scanner()
