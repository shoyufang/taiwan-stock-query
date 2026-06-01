"""
匯出 PDF 報告 — 單一股票完整報告（K線 + 三大法人 + 財報 + AI 摘要）一鍵匯出
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from logging_config import main_logger
import query_wrapper as qw
import io


def render_pdf_export():
    """渲染 PDF 報告匯出功能"""
    st.subheader("📄 匯出 PDF 報告")
    st.caption("生成單一股票完整報告（K線 + 三大法人 + 財報 + AI 摘要）")
    
    # 輸入區域（全寬）
    code = st.text_input("股票代號", placeholder="例：2330", key="pdf_code")
    
    # 按鈕在輸入框下方
    if st.button(" 生成報告", type="primary", use_container_width=True, key="pdf_generate"):
        if code:
            _generate_stock_report(code)


def _generate_stock_report(code: str):
    """生成股票完整報告"""
    with st.spinner(f"正在生成 {code} 完整報告..."):
        try:
            report_data = {}
            
            # 1. 基本資料
            report_data["basic"] = _get_basic_info(code)
            
            # 2. 即時快照
            report_data["snapshot"] = _get_snapshot(code)
            
            # 3. 日K線（最近 3 個月）
            report_data["kbar"] = _get_kbar(code)
            
            # 4. 三大法人（最近 1 個月）
            report_data["institutional"] = _get_institutional(code)
            
            # 5. 財報摘要
            report_data["financials"] = _get_financials(code)
            
            # 顯示報告
            _render_report(code, report_data)
            
        except Exception as e:
            st.error(f"報告生成失敗: {e}")
            main_logger.error(f"PDF 報告生成失敗 ({code}): {e}")


def _get_basic_info(code: str) -> dict:
    """獲取基本資料"""
    try:
        from sinopac_query import query_twse_company
        result = query_twse_company(code)
        if result is not None and not result.empty:
            return result.iloc[0].to_dict()
    except Exception as e:
        main_logger.warning(f"Basic info fetch failed: {e}")
    return {"代號": code, "名稱": "未知"}


def _get_snapshot(code: str) -> pd.DataFrame:
    """獲取即時快照"""
    try:
        result = qw.query_snapshot([code])
        return result if result is not None else pd.DataFrame()
    except Exception as e:
        main_logger.warning(f"Snapshot fetch failed: {e}")
        return pd.DataFrame()


def _get_kbar(code: str, days: int = 90) -> pd.DataFrame:
    """獲取日K線"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        df = qw.query_daily_kbar(code, start_date.date(), end_date.date())
        if df is not None and not df.empty:
            # 標準化欄位名稱
            col_map = {}
            for col in df.columns:
                cl = col.lower()
                if cl in ['date', '日期', 'ts']:
                    col_map[col] = '日期'
                elif cl in ['close', '收盤', '收盤價']:
                    col_map[col] = '收盤'
                elif cl in ['open', '開盤']:
                    col_map[col] = '開盤'
                elif cl in ['high', '最高']:
                    col_map[col] = '最高'
                elif cl in ['low', '最低']:
                    col_map[col] = '最低'
                elif cl in ['volume', '成交量', 'vol']:
                    col_map[col] = '成交量'
            df = df.rename(columns=col_map)
            return df
    except Exception as e:
        main_logger.error(f"Kbar fetch error: {e}")
    return pd.DataFrame()


def _get_institutional(code: str, days: int = 30) -> pd.DataFrame:
    """獲取三大法人"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        result = qw.query_institutional_investors(code, start_date.date(), end_date.date())
        return result if result is not None else pd.DataFrame()
    except Exception as e:
        main_logger.error(f"Institutional fetch error: {e}")
        return pd.DataFrame()


def _get_financials(code: str) -> pd.DataFrame:
    """獲取財報摘要"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        result = qw.query_month_revenue(code, start_date.date(), end_date.date())
        return result if result is not None else pd.DataFrame()
    except Exception as e:
        main_logger.error(f"Financials fetch error: {e}")
        return pd.DataFrame()


def _render_report(code: str, report_data: dict):
    """渲染報告內容"""
    st.divider()
    st.markdown(f"## 📊 {code} 投資報告")
    st.caption(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # 1. 基本資料
    basic = report_data.get("basic", {})
    if basic:
        st.subheader("🏢 公司基本資料")
        try:
            st.json(basic)
        except Exception as e:
            st.error(f"基本資料顯示錯誤: {e}")
    
    # 2. 即時快照
    snapshot = report_data.get("snapshot", pd.DataFrame())
    if snapshot is not None and not snapshot.empty:
        st.subheader("📈 即時行情")
        try:
            st.dataframe(snapshot, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"即時行情顯示錯誤: {e}")
    
    # 3. K線圖
    kbar = report_data.get("kbar", pd.DataFrame())
    if kbar is not None and not kbar.empty:
        st.subheader("📉 日K線圖（最近 3 個月）")
        try:
            if '日期' in kbar.columns and '收盤' in kbar.columns:
                st.line_chart(kbar.set_index('日期')['收盤'])
            elif len(kbar.columns) >= 2:
                st.line_chart(kbar.set_index(kbar.columns[0])[kbar.columns[-1]])
            else:
                st.dataframe(kbar, use_container_width=True)
        except Exception as e:
            st.error(f"K線圖顯示錯誤: {e}")
    
    # 4. 三大法人
    institutional = report_data.get("institutional", pd.DataFrame())
    if institutional is not None and not institutional.empty:
        st.subheader("🏛️ 三大法人買賣超（最近 1 個月）")
        try:
            st.dataframe(institutional, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"三大法人顯示錯誤: {e}")
    
    # 5. 財報
    financials = report_data.get("financials", pd.DataFrame())
    if financials is not None and not financials.empty:
        st.subheader("💰 月營收（最近 1 年）")
        try:
            st.dataframe(financials, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"月營收顯示錯誤: {e}")
    
    # 匯出按鈕
    st.divider()
    if st.button("📥 下載完整報告（CSV 格式）", type="primary", use_container_width=True, key="pdf_download"):
        _export_report_csv(code, report_data)


def _export_report_csv(code: str, report_data: dict):
    """匯出報告為 CSV"""
    try:
        report_lines = [
            f"股票代號,{code}",
            f"生成時間,{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "=== 基本資料 ===",
        ]
        
        basic = report_data.get("basic", {})
        for key, value in basic.items():
            safe_value = str(value).replace(",", "，") if isinstance(value, str) else value
            report_lines.append(f"{key},{safe_value}")
        
        report_lines.append("")
        report_lines.append("=== 即時行情 ===")
        
        snapshot = report_data.get("snapshot", pd.DataFrame())
        if snapshot is not None and not snapshot.empty:
            csv_buffer = io.StringIO()
            snapshot.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            report_lines.append(csv_buffer.getvalue())
        
        csv_content = "\n".join(report_lines)
        st.download_button(
            label="⬇️ 下載 CSV 報告",
            data=csv_content.encode("utf-8-sig"),
            file_name=f"{code}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="pdf_download_csv"
        )
        
        st.success("✅ 報告已準備就緒，請點擊下載")
    except Exception as e:
        st.error(f"匯出失敗: {e}")
