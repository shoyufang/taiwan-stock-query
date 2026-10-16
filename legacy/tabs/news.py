"""
新聞摘要與 Agnes AI 翻譯模組
"""

import streamlit as st
import pandas as pd
from datetime import date
from logging_config import main_logger
from ai_engine import get_deepseek_engine
import query_wrapper as qw
from tabs._shared import _qbtn_grid


def _render_news_cards(df: pd.DataFrame):
    """把新聞 DataFrame 渲染成卡片列表"""
    if df is None or df.empty:
        st.info("查無新聞資料（可能非交易日或代號有誤）")
        return

    for _, row in df.iterrows():
        title = row.get("標題", "")
        summary = row.get("摘要", "")
        time_ = row.get("時間", "")
        source = row.get("來源", "")
        url = row.get("連結", "")

        with st.container():
            st.markdown(
                f"""<div style="
                    border:1px solid #333; border-radius:10px;
                    padding:14px 18px; margin-bottom:10px;
                    background:#1a1a2e;
                ">
                <div style="font-size:1rem; font-weight:600; margin-bottom:6px; color:#e0e0e0;">
                    {title}
                </div>
                <div style="font-size:0.82rem; color:#888; margin-bottom:6px;">
                    🕐 {time_} &nbsp;|&nbsp; 📰 {source}
                </div>
                {"<div style='font-size:0.88rem; color:#bbb; margin-bottom:8px;'>"+summary+"</div>" if summary else ""}
                {"<a href='"+url+"' target='_blank' style='font-size:0.82rem; color:#5b9bd5;'>🔗 閱讀原文</a>" if url else ""}
                </div>""",
                unsafe_allow_html=True,
            )


def _news_to_text(df: pd.DataFrame) -> str:
    """把新聞 DataFrame 轉成純文字給 AI 摘要"""
    lines = []
    for i, row in df.iterrows():
        lines.append(f"[{i + 1}] {row.get('時間', '')}  {row.get('來源', '')}")
        lines.append(f"    標題：{row.get('標題', '')}")
        if row.get("摘要"):
            lines.append(f"    摘要：{row.get('摘要', '')}")
        lines.append("")
    return "\n".join(lines)


def _news_ai_summary_btn(df: pd.DataFrame, subject: str):
    """在新聞列表下方顯示 AI 摘要按鈕與結果"""
    st.divider()
    col_btn, col_hint = st.columns([2, 5])
    with col_btn:
        do_summary = st.button("🤖 Agnes AI 摘要＆翻譯", key="news_ai_btn", use_container_width=True)
    with col_hint:
        st.caption("一鍵將英文新聞翻譯成繁體中文，並給出投資觀點")

    # 顯示已有的摘要
    if st.session_state.get("_news_summary"):
        with st.expander("📊 Agnes AI 分析結果", expanded=True):
            st.markdown(st.session_state["_news_summary"])

    if do_summary:
        engine = get_deepseek_engine()
        if not engine:
            st.warning("請先在左側欄 ⚙️ 設定中填入 Agnes AI API Key")
            return
        news_text = _news_to_text(df)
        with st.spinner("🤖 Agnes AI 翻譯與分析中…"):
            result = engine.summarize_news(news_text, subject)
        if "error" in result:
            st.error(result["error"])
        else:
            st.session_state["_news_summary"] = result["analysis"]
            st.rerun()


def render_news():
    """新聞（Yahoo Finance + Agnes AI 摘要）"""
    main_logger.info("渲染新聞 Tab")

    query_type = _qbtn_grid(["個股新聞", "大盤新聞"], "news_q", n_cols=2)

    # ── 個股新聞 ─────────────────────────────────────────────
    if query_type == "個股新聞":
        col_code, col_count = st.columns([2, 1])
        with col_code:
            code = st.text_input("股票代號", placeholder="例：2330（台積電）、AAPL、0700.HK", key="news_code")
        with col_count:
            count = st.slider("筆數", 3, 20, 10, key="news_count_stock")

        if st.button("查詢新聞", key="news_stock_btn", type="primary"):
            if not code:
                st.warning("請輸入股票代號")
            else:
                with st.spinner("查詢中…"):
                    df = qw.query_stock_news(code.strip(), count)
                st.session_state["_news_df"] = df
                st.session_state["_news_subject"] = f"{code.strip()}"
                st.session_state["_news_summary"] = None

        df = st.session_state.get("_news_df")
        if df is not None:
            _render_news_cards(df)
            _news_ai_summary_btn(df, st.session_state.get("_news_subject", ""))

    # ── 大盤新聞 ─────────────────────────────────────────────
    elif query_type == "大盤新聞":
        count = st.slider("筆數", 3, 20, 10, key="news_count_market")

        if st.button("查詢大盤新聞", key="news_market_btn", type="primary"):
            with st.spinner("查詢中…"):
                df = qw.query_market_news(count)
            st.session_state["_news_df"] = df
            st.session_state["_news_subject"] = "台股大盤（^TWII）"
            st.session_state["_news_summary"] = None

        df = st.session_state.get("_news_df")
        if df is not None:
            _render_news_cards(df)
            _news_ai_summary_btn(df, st.session_state.get("_news_subject", "台股大盤"))
