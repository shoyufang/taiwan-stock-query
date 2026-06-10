"""
美股日曆與華爾街共識 UI 模組
"""

import streamlit as st
import pandas as pd
import us_calendar as usc


def render_us_calendar_consensus():
    """美股財報日曆與華爾街共識 UI"""
    st.markdown("### 📅 美股日曆 & 華爾街共識")
    st.caption("基於 50 檔美股巨頭/藍籌股，提供即將公佈之財報日曆與華爾街目標價空間、評等共識排名")

    # 1. 取得數據 (預設使用快取，24小時永久快取)
    with st.spinner("正在加載美股日曆與華爾街共識數據..."):
        try:
            df_all = usc.get_us_calendar_consensus_data(force_refresh=False)
        except Exception as e:
            st.error(f"加載數據失敗: {e}")
            return

    if df_all.empty:
        st.error("❌ 無法取得美股日曆與共識數據。請檢查網路或稍後再試。")
        return

    # 操作與刷新按鈕
    col_l, col_r = st.columns([4, 1])
    with col_r:
        force_refresh = st.button("🔄 強制重新整理", key="us_cal_refresh", use_container_width=True, help="清空 24 小時快取並重新抓取 50 檔美股最新數據")

    if force_refresh:
        with st.spinner("正在背景抓取 50 檔最新數據（預計耗時 5-8 秒）..."):
            try:
                df_all = usc.get_us_calendar_consensus_data(force_refresh=True)
                st.success("🔄 數據更新成功，已寫入 24 小時 SQLite 快取！")
                st.rerun()
            except Exception as e:
                st.error(f"更新失敗: {e}")
                return

    # 提供兩個分頁
    tab_cal, tab_con = st.tabs(["📅 財報公佈日曆 (Earnings Calendar)", "🎯 華爾街共識與潛在空間 (Wall Street Consensus)"])

    with tab_cal:
        st.markdown("#### 即將公佈之財報日程")
        st.caption("依照財報公佈日由近到遠排序")

        df_cal = df_all.copy()

        # 提取有日期的
        df_has_date = df_cal[df_cal["財報公佈日"] != "N/A"].copy()
        df_no_date = df_cal[df_cal["財報公佈日"] == "N/A"].copy()

        # 對有日期的按日期排序
        df_has_date = df_has_date.sort_values("財報公佈日", ascending=True)
        df_cal_sorted = pd.concat([df_has_date, df_no_date]).reset_index(drop=True)

        # 顯示特定欄位
        display_cols = ["代號", "名稱", "行業板塊", "最新價", "財報公佈日", "預估下季EPS", "預估營收(B)"]
        df_cal_disp = df_cal_sorted[display_cols]

        st.dataframe(df_cal_disp, use_container_width=True, hide_index=True)

        # 匯出按鈕
        try:
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_cal_disp.to_excel(writer, sheet_name="美股財報行事曆", index=False)
            st.download_button("⬇ 下載財報行事曆 Excel", data=buf.getvalue(),
                               file_name="美股財報行事曆.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="us_cal_dl")
        except Exception:
            pass

    with tab_con:
        st.markdown("#### 華爾街目標價潛在漲幅與評等排名")
        st.caption("按照潛在漲幅由高到低排序，協助尋找低估或具備高安全邊際之優質資產")

        df_con = df_all.copy()

        # 排序：潛在漲幅由高到低
        df_con = df_con.sort_values("潛在漲幅%", ascending=False).reset_index(drop=True)

        # 過濾與 Slider 篩選
        col_fil1, col_fil2 = st.columns(2)
        with col_fil1:
            min_upside = st.slider("最低潛在漲幅 (%)", min_value=-50, max_value=100, value=0, step=5, key="us_con_min_upside")
        with col_fil2:
            sectors = sorted(list(df_con["行業板塊"].unique()))
            sector_sel = st.multiselect("板塊篩選", options=["All"] + sectors, default=["All"], key="us_con_sector_sel")

        # 套用過濾
        df_filtered = df_con[df_con["潛在漲幅%"] >= min_upside]
        if sector_sel and "All" not in sector_sel:
            df_filtered = df_filtered[df_filtered["行業板塊"].isin(sector_sel)]

        display_con_cols = ["代號", "名稱", "行業板塊", "最新價", "共識評等", "平均目標價", "潛在漲幅%", "目標最低價", "目標最高價", "分析師人數"]
        df_con_disp = df_filtered[display_con_cols]

        st.dataframe(df_con_disp, use_container_width=True, hide_index=True)

        st.markdown("💡 **操作提示**：複製潛在漲幅居前的美股代號 (如 `NVDA`, `AAPL`) 至 **【技術分析】** 或 **【美股專區】**，可查看即時技術 K 線圖與 AI 智能分析報告！")

        # 匯出按鈕
        try:
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_con_disp.to_excel(writer, sheet_name="華爾街共識排名", index=False)
            st.download_button("⬇ 下載共識排名 Excel", data=buf.getvalue(),
                               file_name="美股華爾街共識排名.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="us_con_dl")
        except Exception:
            pass

        # 保存當前查詢參數供一鍵釘選
        st.session_state.last_query = {
            "tab": "📅 美股日曆 & 共識",
            "params": {
                "type": "us_calendar_consensus"
            },
            "default_name": "美股日曆與共識"
        }
