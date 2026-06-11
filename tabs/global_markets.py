"""
全球市場 — 美股 + 港股 + 期貨/匯率三合一
Phase A: 暫時用 st.tabs 包既有 render
"""
import streamlit as st


def render_global_markets():
    """全球市場頁面（Phase D.2 實作）。Phase A: 委派至既有渲染器。"""
    from tabs.us_stocks import render_us_stocks
    from tabs.hk_stocks import render_hk_us_stocks
    from tabs.futures_forex import render_futures_forex

    st.markdown("### 🌐 全球市場")
    st.caption("美股 · 港股 · 期貨/匯率 — 跨市場一鍵掌握")

    tab_us, tab_hk, tab_fx = st.tabs(["🇺🇸 美股", "🇭🇰 港股", "📊 期貨/匯率"])

    with tab_us:
        render_us_stocks()

    with tab_hk:
        render_hk_us_stocks()

    with tab_fx:
        render_futures_forex()
