"""
查詢路由分派與執行模組 — 解耦 UI 渲染與核心數據抓取
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Dict, Any, Optional
from logging_config import main_logger
from theme import THEMES
from ui_components import display_result
import query_wrapper as qw


def _handle_ranking(params: dict) -> tuple:
    """處理排行查詢，回傳 (result, title)"""
    ranking_type = params.get("ranking_type", "up")
    limit = params.get("limit", 10)
    result = qw.query_ranking(ranking_type, limit)
    return result, f"台股排行 - {ranking_type}"


def _handle_snapshot(params: dict) -> tuple:
    """處理快照查詢，回傳 (result, title)"""
    codes = params.get("codes", [])
    if not codes:
        return pd.DataFrame(), "個股即時快照"
    result = qw.query_snapshot(codes)
    return result, "個股即時快照"


def _handle_kbar(params: dict) -> tuple:
    """處理日K查詢，回傳 (result, title)"""
    code = params.get("code", "")
    start = params.get("start", "")
    end = params.get("end", "")
    if not (code and start and end):
        return pd.DataFrame(), f"{code} 日K"
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    result = qw.query_daily_kbar(code, start_date, end_date)
    return result, f"{code} 日K"


def _handle_ticks(params: dict) -> tuple:
    """處理逐筆成交查詢，回傳 (result, title)"""
    code = params.get("code", "")
    query_date = params.get("date", "")
    if not (code and query_date):
        return pd.DataFrame(), f"{code} 逐筆成交"
    query_date_obj = datetime.strptime(query_date, "%Y-%m-%d").date()
    result = qw.query_ticks(code, query_date_obj)
    return result, f"{code} 逐筆成交"


def _handle_institutional(params: dict) -> tuple:
    """處理三大法人查詢，回傳 (result, title)"""
    code = params.get("code", "")
    start = params.get("start", "")
    end = params.get("end", "")
    if not (code and start and end):
        return pd.DataFrame(), f"{code} 三大法人明細"
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    result = qw.query_institutional_investors(code, start_date, end_date)
    return result, f"{code} 三大法人明細"


QUERY_DISPATCH = {
    "ranking": _handle_ranking,
    "snapshot": _handle_snapshot,
    "kbar": _handle_kbar,
    "ticks": _handle_ticks,
    "institutional": _handle_institutional,
}


def execute_from_history(history_item: Dict[str, Any]):
    """從歷史記錄執行查詢"""
    main_logger.info(f"從歷史記錄執行: {history_item.get('tab', '')} - {history_item.get('title', '')}")
    params = history_item.get("params", {})
    query_type = params.get("type", "")

    if not query_type:
        main_logger.warning(f"查詢類型不完整: {history_item}")
        st.warning("無法執行：查詢類型不完整")
        return

    with st.spinner("執行中..."):
        try:
            handler = QUERY_DISPATCH.get(query_type)
            if handler:
                result, title = handler(params)
                if not result.empty:
                    st.session_state.current_result = result
                    display_result(
                        result,
                        f"{history_item.get('tab', '')} - {title.split(' - ')[-1] if ' - ' in title else title}"
                    )
            else:
                st.warning(f"⚠️ 暫不支援的查詢類型: {query_type}")

            main_logger.info(f"歷史查詢執行完成: {query_type}")
            st.success("✅ 查詢執行完成")
        except Exception as e:
            main_logger.error(f"歷史查詢執行失敗: {query_type}, 錯誤: {str(e)}")
            st.error(f"❌ 執行失敗: {str(e)}")


def execute_query_by_params(tab: str, params: dict):
    """根據參數執行查詢並直接就地渲染結果，支援跨分頁所有功能 (Pinned widgets)"""
    q_type = params.get("type", "")
    if not q_type:
        st.warning("⚠️ 捷徑參數不完整，無法執行")
        return

    # 延遲導入共用渲染組件，防範循環導入
    from tabs._shared import _render_batch_results

    try:
        # 1. 使用 registry 執行基本查詢類型
        handler = QUERY_DISPATCH.get(q_type)
        if handler:
            res, title = handler(params)
            if not res.empty:
                display_result(res, title)
        # 2. 新增的跨模組捷徑執行
        elif q_type == "technical_analysis":
            code = params.get("code", "")
            start_date = datetime.strptime(params["start"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end"], "%Y-%m-%d").date()
            indicators = params.get("indicators", [])
            import technical_analysis as ta
            with st.spinner("正在繪製互動式技術指標圖表..."):
                kbar_df = qw.query_daily_kbar(code, start_date, end_date)
                if isinstance(kbar_df, pd.DataFrame) and not kbar_df.empty:
                    theme_name = st.session_state.get("theme", "🌅 Claude 暖橘")
                    t_cfg = THEMES.get(theme_name, THEMES["🌅 Claude 暖橘"])
                    
                    tab_tv, tab_plotly = st.tabs(["📊 TradingView 專業 Canvas 終端 (推薦)", "📈 Plotly 綜合指標圖 (含 RSI/MACD/BB)"])
                    with tab_tv:
                        tv_html = ta.render_tradingview_chart(
                            kbar_df,
                            code,
                            theme_cfg=t_cfg,
                            indicators=indicators if indicators else ["MA5", "MA20"],
                            height=520
                        )
                        st.components.v1.html(tv_html, height=540)
                        st.caption("💡 提示：本終端支援極速 Canvas 渲染（含 MA/EMA/布林帶）。若需要查看 RSI、MACD、ATR 等獨立副圖指標，請切換至上方【📈 Plotly 綜合指標圖】。")
                        st.caption("💡 提示：使用滑鼠滾輪進行【縮放】，拖曳圖表進行【平移】，十字游標會顯示精確價格與成交量。")
                        
                    with tab_plotly:
                        fig = ta.plot_kbar_with_indicators(
                            kbar_df,
                            code,
                            indicators=indicators if indicators else ["MA5", "MA20"],
                            theme_cfg=t_cfg,
                            height=750
                        )
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("無法獲取K線數據，繪圖失敗")
                    
        elif q_type == "taistock_batch":
            from tabs.taistock import _taistock_dispatch
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
            query_date = datetime.strptime(params["query_date"], "%Y-%m-%d").date()
            results = []
            for item in params["selected"]:
                kwargs = {}
                if "resolution" in params:
                    kwargs["resolution"] = params["resolution"]
                if "threshold_vol" in params:
                    kwargs["threshold_vol"] = params["threshold_vol"]
                if "threshold_amt" in params:
                    kwargs["threshold_amt"] = params["threshold_amt"]
                res = _taistock_dispatch(
                    item, params["code"], params["codes"], start_date, end_date, query_date, params["count"],
                    **kwargs
                )
                results.append((item, res))
            # 存入臨時狀態以利渲染結果
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
 
        elif q_type == "twse_batch":
            from tabs.twse import _twse_dispatch
            results = []
            for item in params["selected"]:
                res, _ = _twse_dispatch(item, params["code"])
                results.append((item, res))
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
            
        elif q_type == "finmind_batch":
            from tabs.finmind import _finmind_dispatch
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
            results = []
            for item in params["selected"]:
                res = _finmind_dispatch(item, params["code"], start_date, end_date)
                results.append((item, res))
            st.session_state["db_batch_results"] = (results, params["code"])
            _render_batch_results(
                "db_batch_results",
                label_fn=lambda item, extra: f"📋 {extra} — {item}" if extra else f"📋 {item}",
            )
            
        elif q_type == "futures_forex_batch":
            from tabs.futures_forex import _futures_forex_dispatch
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
            results = []
            for item in params["selected"]:
                res = _futures_forex_dispatch(
                    item, params.get("futures_code"), params.get("currency"), start_date, end_date)
                results.append((item, res))
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
            
        elif q_type == "screener_us":
            import us_screener as usc
            from tabs.screener_tab import _us_screener_result_block
            with st.spinner("正在執行美股多因子選股篩選..."):
                df_all = usc.get_us_screener_data(force_refresh=False)
                res_df = usc.filter_us_stocks(df_all, params["filters"])
                _us_screener_result_block(res_df, "美股多因子選股")
                
        elif q_type == "us_stock_batch":
            from tabs.us_stocks import _us_stock_dispatch
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date() if params.get("start_date") else None
            end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date() if params.get("end_date") else None
            results = []
            for item in params["selected"]:
                res = _us_stock_dispatch(item, params["ticker"], start_date, end_date)
                results.append((item, res))
            st.session_state["db_batch_results"] = results
            _render_batch_results("db_batch_results")
            
        elif q_type == "us_calendar_consensus":
            import us_calendar as usc
            with st.spinner("正在加載美股日曆與華爾街共識數據..."):
                df_cal = usc.get_us_calendar_consensus_data(force_refresh=False)
                if not df_cal.empty:
                    # 顯示華爾街評等共識排名
                    display_cols = ["代號", "名稱", "行業板塊", "最新價", "共識評等", "平均目標價", "潛在漲幅%", "分析師人數"]
                    st.dataframe(df_cal[display_cols].sort_values("潛在漲幅%", ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.warning("無數據可顯示")
        else:
            st.warning(f"⚠️ 暫不支援的捷徑類型: {q_type}")
    except Exception as exc:
        st.error(f"❌ 捷徑執行失敗: {exc}")
        main_logger.error(f"捷徑執行出錯 params={params}: {exc}")
