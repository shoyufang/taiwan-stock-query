"""
美股專區分頁 (yfinance)
"""

import streamlit as st
import pandas as pd
from datetime import date
from logging_config import main_logger
import query_wrapper as qw
from ui_components import us_code_input_section, date_input_section
from tabs._shared import _render_batch_results


def _us_stock_dispatch(item: str, ticker: str, start_date, end_date):
    """分派美股市場查詢。"""
    if item == "大盤指數快照":
        indices = {"S&P 500": "^GSPC", "那斯達克": "^IXIC", "道瓊工業": "^DJI"}
        res = []
        for name, symbol in indices.items():
            try:
                hist = qw.query_yfinance_index(symbol, period="2d")
                if len(hist) >= 2:
                    prev_c = hist['Close'].iloc[0]
                    curr_c = hist['Close'].iloc[1]
                    res.append({"指數名稱": name, "最新報價": curr_c, "漲跌": curr_c - prev_c, "漲跌幅(%)": (curr_c - prev_c)/prev_c*100})
                elif len(hist) == 1:
                    res.append({"指數名稱": name, "最新報價": hist['Close'].iloc[0], "漲跌": 0.0, "漲跌幅(%)": 0.0})
            except Exception:
                pass
        return pd.DataFrame(res)

    from us_stock_query import (
        get_us_stock_info, get_us_stock_history, get_us_stock_news,
        get_us_financials, get_us_holders, get_us_analyst_info, get_us_sector_performance
    )
    
    if item == "個股基本資料":
        info = get_us_stock_info(ticker)
        return {"type": "us_profile", "data": info} if info else {"error": "無法獲取基本資料"}

    if item == "個股財務報表":
        fin = get_us_financials(ticker)
        return {"type": "us_financials", "data": fin} if fin else {"error": "無法獲取財務報表"}

    if item == "大股東與機構持股":
        holders = get_us_holders(ticker)
        return {"type": "us_holders", "data": holders} if holders else {"error": "無法獲取股東結構"}

    if item == "分析師評等與目標價":
        analyst = get_us_analyst_info(ticker)
        return {"type": "us_analyst_info", "data": analyst} if analyst else {"error": "無法獲取分析師評等"}

    if item == "美股板塊與大盤表現":
        perf = get_us_sector_performance()
        return perf if not perf.empty else {"error": "無法獲取板塊表現"}
        
    if item == "最新相關新聞":
        news = get_us_stock_news(ticker)
        return {"type": "us_news", "data": news} if news else {"error": "無法獲取相關新聞"}
        
    if item == "個股歷史K線":
        if start_date and end_date:
            try:
                result = qw.query_daily_kbar(ticker, start_date, end_date)
                if isinstance(result, pd.DataFrame) and not result.empty:
                    if result.index.name == 'Date' or isinstance(result.index, pd.DatetimeIndex):
                        result = result.reset_index()
                    if 'Date' in result.columns:
                        result['Date'] = pd.to_datetime(result['Date']).dt.date
                    return result
            except Exception:
                pass

        try:
            import yfinance as yf
            from datetime import timedelta as _td2, date as _date2
            tkr = yf.Ticker(ticker)
            _sd = (_date2.today() - _td2(days=180)).strftime('%Y-%m-%d')
            _ed = (_date2.today() + _td2(days=1)).strftime('%Y-%m-%d')
            df_history = tkr.history(start=_sd, end=_ed)
            if df_history is not None and not df_history.empty:
                if hasattr(df_history.index, "tz") and df_history.index.tz is not None:
                    df_history.index = df_history.index.tz_localize(None)
                df_history.reset_index(inplace=True)
                if 'Date' in df_history.columns:
                    df_history['Date'] = pd.to_datetime(df_history['Date']).dt.date
                return df_history
        except Exception as e:
            return {"error": f"獲取 K 線資料失敗：{e}"}
        return {"error": "無法獲取 K 線資料"}
        
    if item == "美股代號總表 (FinMind)":
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            df = dl.us_stock_info()
            if df is not None and not df.empty:
                return df
            return {"error": "無法獲取 FinMind 美股代號表"}
        except Exception as e:
            return {"error": f"FinMind 查詢失敗: {e}"}

    if item == "個股歷史K線 (FinMind)":
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            sd = start_date.strftime('%Y-%m-%d') if start_date else "2023-01-01"
            df = dl.us_stock_price(stock_id=ticker, start_date=sd)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "date": "Date",
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                })
                df['Date'] = pd.to_datetime(df['Date']).dt.date
                return df
            return {"error": "無 K 線資料 (FinMind)"}
        except Exception as e:
            return {"error": f"FinMind K線查詢失敗: {e}"}
        
    return {"error": f"未知項目：{item}"}


def render_us_stocks():
    """美股專區 — 整合 yfinance 與 FinMind (批次查詢模式)"""
    main_logger.info("渲染美股專區 Tab")
    st.markdown("## 🇺🇸 美股專區")
    
    NO_DATE_ITEMS = [
        "大盤指數快照", 
        "個股基本資料", 
        "最新相關新聞", 
        "個股財務報表", 
        "大股東與機構持股", 
        "分析師評等與目標價", 
        "美股板塊與大盤表現",
        "美股代號總表 (FinMind)"
    ]
    DATE_ITEMS    = ["個股歷史K線", "個股歷史K線 (FinMind)"]
    
    # ── 上半：複選區 ─────────────
    with st.container(border=True):
        col_left, col_right = st.columns(2)
        with col_left:
            st.caption("📊 綜合資訊 (不需選擇日期)")
            for i, opt in enumerate(NO_DATE_ITEMS):
                st.checkbox(opt, key=f"us_cb_nd_{i}")
        with col_right:
            st.caption("📅 歷史行情 (需選擇日期範圍)")
            for i, opt in enumerate(DATE_ITEMS):
                st.checkbox(opt, key=f"us_cb_d_{i}")

    selected_nd = [opt for i, opt in enumerate(NO_DATE_ITEMS) if st.session_state.get(f"us_cb_nd_{i}", False)]
    selected_d  = [opt for i, opt in enumerate(DATE_ITEMS)    if st.session_state.get(f"us_cb_d_{i}",  False)]
    selected    = selected_nd + selected_d

    has_snapshot = "大盤指數快照" in selected
    has_profile  = "個股基本資料" in selected
    has_news     = "最新相關新聞" in selected
    has_kbar     = "個股歷史K線" in selected
    has_list     = "美股代號總表 (FinMind)" in selected
    has_fm_kbar  = "個股歷史K線 (FinMind)" in selected
    has_fin      = "個股財務報表" in selected
    has_holders  = "大股東與機構持股" in selected
    has_analyst  = "分析師評等與目標價" in selected
    
    needs_code   = has_profile or has_news or has_kbar or has_fm_kbar or has_fin or has_holders or has_analyst
    
    ticker = ""
    if needs_code:
        ticker = us_code_input_section("搜尋美股 (支援中文名稱、代號)", single=True)
        
    start_date, end_date = None, None
    if has_kbar or has_fm_kbar:
        start_date, end_date = date_input_section(default_days=180, key_prefix="us_")

    if selected:
        st.caption(f"已勾選 {len(selected)} 項：{' · '.join(selected)}")
        
    run_batch = st.button("🔍 確認查詢", type="primary", use_container_width=True, key="us_run_batch")
    
    st.divider()
    
    if run_batch:
        if not selected:
            st.warning("請至少勾選一個項目")
        elif needs_code and not ticker:
            st.warning("請輸入代號才能查詢個股資料")
        else:
            results = []
            bar = st.progress(0, text="查詢中...")
            for idx, item in enumerate(selected):
                bar.progress((idx + 1) / len(selected), text=f"查詢：{item}")
                try:
                    result = _us_stock_dispatch(item, ticker, start_date, end_date)
                except Exception as e:
                    result = {"error": str(e)}
                results.append((item, result))
            bar.empty()
            st.session_state["us_batch_results"] = (results, ticker)

            # 保存當前查詢參數供一鍵釘選
            st.session_state.last_query = {
                "tab": "🇺🇸 美股專區",
                "params": {
                    "type": "us_stock_batch",
                    "selected": selected,
                    "ticker": ticker,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "default_name": f"美股批次 - {ticker} ({'、'.join(selected[:2])}{'等' if len(selected)>2 else ''})"
            }

    _render_batch_results("us_batch_results")

    # ── AI 投資研究報告 ──────────────────────────────────
    if ticker:
        st.divider()
        st.markdown(f"### 🤖 AI 一鍵美股健檢與投資報告")
        
        report_key = f"us_ai_report_{ticker}"
        
        col1, col2 = st.columns([1, 4])
        with col1:
            generate_btn = st.button("✨ 生成 AI 健檢報告", type="primary", use_container_width=True, key=f"btn_ai_rep_{ticker}")
        
        if generate_btn:
            with st.spinner(f"正在為您抓取數據並由 AI 生成 {ticker} 深度投資研究報告..."):
                from ai_engine import generate_us_stock_report
                report_content = generate_us_stock_report(ticker)
                st.session_state[report_key] = report_content
                
        if report_key in st.session_state:
            report_content = st.session_state[report_key]
            
            with st.container(border=True):
                st.markdown(report_content)
                
                st.download_button(
                    "📥 下載 Markdown 投資報告",
                    data=report_content,
                    file_name=f"{ticker}_AI_Investment_Report.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key=f"dl_ai_rep_{ticker}"
                )
