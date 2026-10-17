"""
匯出 PDF 報告 — 單一股票完整報告（K線 + 三大法人 + 財報）一鍵匯出
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from logging_config import main_logger
import query_wrapper as qw
import io

def render_pdf_export():
    st.subheader("📄 匯出 PDF 報告")
    st.caption("生成單一股票完整報告（K線 + 三大法人 + 財報）")
    code = st.text_input("股票代號", placeholder="例：2330", key="pdf_code")
    if st.button("📥 生成報告", type="primary", use_container_width=True, key="pdf_generate"):
        if code:
            _generate_report(code)

def _generate_report(code: str):
    with st.spinner(f"正在生成 {code} 完整報告..."):
        try:
            _render_report(code, {
                "basic": _fetch_basic(code),
                "snapshot": _fetch_snapshot(code),
                "kbar": _fetch_kbar(code),
                "institutional": _fetch_institutional(code),
                "financials": _fetch_financials(code),
            })
        except Exception as e:
            st.error(f"報告生成失敗")
            main_logger.error(f"PDF 報告生成失敗 ({code}): {e}")

def _safe_df(fn, *args, **kwargs) -> pd.DataFrame:
    """安全執行查詢，失敗回傳空 DataFrame"""
    try:
        result = fn(*args, **kwargs)
        return result if result is not None else pd.DataFrame()
    except Exception as e:
        main_logger.warning(f"查詢失敗 {fn.__name__}: {e}")
        return pd.DataFrame()

def _fetch_basic(code: str) -> dict:
    try:
        from sinopac_query import query_twse_company
        df = _safe_df(query_twse_company, code)
        if not df.empty:
            d = df.iloc[0].to_dict()
            # 處理 NaN 值，避免 st.json 失敗
            return {k: str(v) if pd.isna(v) else v for k, v in d.items()}
    except Exception as e:
        main_logger.warning(f"Basic info failed: {e}")
    return {"代號": code, "名稱": "查詢失敗"}

def _fetch_snapshot(code: str) -> pd.DataFrame:
    return _safe_df(qw.query_snapshot, [code])

def _fetch_kbar(code: str, days: int = 90) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=days)
    df = _safe_df(qw.query_daily_kbar, code, start.date(), end.date())
    if df.empty:
        return df
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if cl in ('date', '日期', 'ts'): col_map[col] = '日期'
        elif cl in ('close', '收盤', '收盤價'): col_map[col] = '收盤'
        elif cl in ('open', '開盤'): col_map[col] = '開盤'
        elif cl in ('high', '最高'): col_map[col] = '最高'
        elif cl in ('low', '最低'): col_map[col] = '最低'
        elif cl in ('volume', '成交量', 'vol'): col_map[col] = '成交量'
    return df.rename(columns=col_map)

def _fetch_institutional(code: str, days: int = 30) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=days)
    return _safe_df(qw.query_institutional_investors, code, start.date(), end.date())

def _fetch_financials(code: str) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=365)
    return _safe_df(qw.query_month_revenue, code, start.date(), end.date())

def _safe_dataframe(df: pd.DataFrame, label: str, **kwargs):
    """安全渲染 DataFrame，失敗時顯示提示"""
    if df is None or df.empty:
        st.caption(f"📭 {label}：暫無資料")
        return
    try:
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)
    except Exception as e:
        main_logger.warning(f"渲染失敗 {label}: {e}")
        st.caption(f"📭 {label}：資料渲染失敗")

def _render_report(code: str, data: dict):
    st.divider()
    st.markdown(f"## 📊 {code} 投資報告")
    st.caption(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.container():
        st.subheader("🏢 公司基本資料")
        try:
            st.json(data["basic"])
        except Exception as e:
            st.caption("📭 基本資料：暫無法顯示")

    with st.container():
        st.subheader("📈 即時行情")
        _safe_dataframe(data["snapshot"], "即時行情")

    with st.container():
        st.subheader("📉 日K線圖（最近 3 個月）")
        kbar = data["kbar"]
        if kbar is not None and not kbar.empty:
            try:
                if '日期' in kbar.columns and '收盤' in kbar.columns:
                    st.line_chart(kbar.set_index('日期')['收盤'])
                elif len(kbar.columns) >= 2:
                    st.line_chart(kbar.set_index(kbar.columns[0])[kbar.columns[-1]])
                else:
                    _safe_dataframe(kbar, "日K線")
            except Exception as e:
                st.caption("📭 日K線圖：暫無法顯示")
        else:
            st.caption("📭 日K線圖：暫無資料")

    with st.container():
        st.subheader("🏛️ 三大法人買賣超（最近 1 個月）")
        _safe_dataframe(data["institutional"], "三大法人")

    with st.container():
        st.subheader("💰 月營收（最近 1 年）")
        _safe_dataframe(data["financials"], "月營收")

    st.divider()
    if st.button("📥 下載完整報告（CSV 格式）", type="primary", use_container_width=True, key="pdf_download"):
        _export_csv(code, data)

def _export_csv(code: str, data: dict):
    try:
        lines = [
            f"股票代號,{code}",
            f"生成時間,{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "", "=== 基本資料 ===",
        ]
        for k, v in data.get("basic", {}).items():
            lines.append(f"{k},{str(v).replace(',', '，')}")
        lines += ["", "=== 即時行情 ==="]
        snap = data.get("snapshot")
        if snap is not None and not snap.empty:
            buf = io.StringIO()
            snap.to_csv(buf, index=False, encoding='utf-8-sig')
            lines.append(buf.getvalue())
        text = "\n".join(lines)
        st.download_button("⬇️ 下載 CSV 報告", text.encode("utf-8-sig"),
            file_name=f"{code}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv", key="pdf_download_csv")
        st.success("✅ 報告已準備就緒")
    except Exception as e:
        st.error("匯出失敗")
        main_logger.error(f"CSV 匯出差異: {e}")
