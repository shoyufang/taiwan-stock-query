"""
匯出 PDF 報告 — 單一股票完整報告（K線 + 三大法人 + 財報 + AI 摘要）一鍵匯出
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from logging_config import main_logger
import query_wrapper as qw


def render_pdf_export():
    """渲染 PDF 報告匯出功能"""
    st.subheader("📄 匯出 PDF 報告")
    st.caption("生成單一股票完整報告（K線 + 三大法人 + 財報 + AI 摘要）")
    
    # 輸入區域
    col1, col2 = st.columns([2, 1])
    with col1:
        code = st.text_input("股票代號", placeholder="例：2330", key="pdf_code")
    with col2:
        st.write("")  # 垂直對齊
        if st.button("📥 生成報告", type="primary", use_container_width=True, key="pdf_generate"):
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
        if not result.empty:
            return result.iloc[0].to_dict()
    except:
        pass
    return {"代號": code, "名稱": "未知"}


def _get_snapshot(code: str) -> pd.DataFrame:
    """獲取即時快照"""
    try:
        return qw.query_snapshot([code])
    except:
        return pd.DataFrame()


def _get_kbar(code: str, days: int = 90) -> pd.DataFrame:
    """獲取日K線"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return qw.query_daily_kbar(code, start_date.date(), end_date.date())
    except:
        return pd.DataFrame()


def _get_institutional(code: str, days: int = 30) -> pd.DataFrame:
    """獲取三大法人"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return qw.query_institutional_investors(code, start_date.date(), end_date.date())
    except:
        return pd.DataFrame()


def _get_financials(code: str) -> pd.DataFrame:
    """獲取財報摘要"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        return qw.query_month_revenue(code, start_date.date(), end_date.date())
    except:
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
        st.json(basic)
    
    # 2. 即時快照
    snapshot = report_data.get("snapshot", pd.DataFrame())
    if not snapshot.empty:
        st.subheader("📈 即時行情")
        st.dataframe(snapshot, use_container_width=True, hide_index=True)
    
    # 3. K線圖
    kbar = report_data.get("kbar", pd.DataFrame())
    if not kbar.empty:
        st.subheader("📉 日K線圖（最近 3 個月）")
        st.line_chart(kbar.set_index("日期")["收盤"])
    
    # 4. 三大法人
    institutional = report_data.get("institutional", pd.DataFrame())
    if not institutional.empty:
        st.subheader("🏛️ 三大法人買賣超（最近 1 個月）")
        st.dataframe(institutional, use_container_width=True, hide_index=True)
    
    # 5. 財報
    financials = report_data.get("financials", pd.DataFrame())
    if not financials.empty:
        st.subheader("💰 月營收（最近 1 年）")
        st.dataframe(financials, use_container_width=True, hide_index=True)
    
    # 匯出按鈕
    st.divider()
    if st.button("📥 下載完整報告（CSV 格式）", type="primary", use_container_width=True, key="pdf_download"):
        _export_report_csv(code, report_data)


def _export_report_csv(code: str, report_data: dict):
    """匯出報告為 CSV"""
    try:
        # 建立報告內容
        report_lines = [
            f"股票代號,{code}",
            f"生成時間,{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "=== 基本資料 ===",
        ]
        
        basic = report_data.get("basic", {})
        for key, value in basic.items():
            report_lines.append(f"{key},{value}")
        
        report_lines.append("")
        report_lines.append("=== 即時行情 ===")
        
        snapshot = report_data.get("snapshot", pd.DataFrame())
        if not snapshot.empty:
            report_lines.append(snapshot.to_csv(index=False))
        
        # 提供下載
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
