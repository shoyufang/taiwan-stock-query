"""
儀表板分頁 — ADR 監控 + 關注名單
"""
import streamlit as st
import pandas as pd
from logging_config import main_logger
from preload import preload_manager
import query_wrapper as qw
from ui_components import display_result

def render_dashboard_fragment():
    """儀表板自動刷新部分 (Task 7.3/7.4)"""

    # ⚖️ 台美 ADR 溢折價即時監控
    st.subheader("⚖️ 台美 ADR 溢折價即時監控")
    try:
        from adr_query import get_adr_snapshots
        adr_data = get_adr_snapshots()
        rate = adr_data["rate"]
        ts_cached = adr_data["timestamp"]
        
        # 建立 3 欄
        cols = st.columns(3)
        for idx, item in enumerate(adr_data["data"]):
            key = item["key"]
            name = item["name"]
            adr_ticker = item["adr_ticker"]
            adr_price = item["adr_price"]
            tw_code = item["tw_code"]
            tw_price = item["tw_price"]
            adr_twd_equiv = item["adr_twd_equiv"]
            premium_pct = item["premium_pct"]
            
            # 溢價顏色 (正為暖橘，負為藍色)
            badge_color = "var(--claude-primary)" if premium_pct >= 0 else "#1976d2"
            badge_bg = "rgba(217, 119, 87, 0.12)" if premium_pct >= 0 else "rgba(25, 118, 210, 0.12)"
            
            # 使用 HTML 繪製高質感的 Glassmorphic 卡片
            with cols[idx]:
                st.markdown(f"""
                <div style="
                    background: #FFFFFF;
                    border-radius: 12px;
                    padding: 16px;
                    border: 1px solid var(--claude-border);
                    box-shadow: 0 2px 8px var(--claude-shadow);
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-weight: 700; font-size: 0.95rem; color: var(--claude-text);">{name} {key}</span>
                        <div style="
                            background: {badge_bg};
                            border-radius: 6px;
                            padding: 3px 8px;
                            color: {badge_color};
                            font-weight: 700;
                            font-size: 0.85rem;
                        ">
                            {premium_pct:+.2f}%
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <div>
                            <span style="font-size: 0.72rem; color: var(--claude-text-2);">美股 {adr_ticker}</span><br/>
                            <strong style="font-size: 1.05rem; color: var(--claude-text);">${adr_price:.2f}</strong>
                        </div>
                        <div style="text-align: right;">
                            <span style="font-size: 0.72rem; color: var(--claude-text-2);">台股 {tw_code}</span><br/>
                            <strong style="font-size: 1.05rem; color: var(--claude-text);">{tw_price:.1f}元</strong>
                        </div>
                    </div>
                    <div style="
                        border-top: 1px solid var(--claude-border-light);
                        padding-top: 8px;
                        margin-top: 8px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <span style="font-size: 0.72rem; color: var(--claude-text-2);">ADR 折合台幣</span>
                        <strong style="font-size: 1.0rem; color: var(--claude-primary);">{adr_twd_equiv:.2f}元</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown(f"""
        <div style="text-align: right; margin-top: 6px; margin-bottom: 15px;">
            <span style="font-size: 0.72rem; color: var(--claude-text-2); font-weight: 500;">
                💵 美元對台幣匯率: <strong>{rate:.4f}</strong> | ⏱️ ADR 快取更新: <strong>{ts_cached}</strong>
            </span>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.warning(f"無法載入台美 ADR 監控數據: {e}")
        main_logger.error(f"儀表板 ADR 監控渲染出錯: {e}")
        
    st.divider()
    
    # 熱門監控 (基於動態預載名單)
    st.subheader("🔥 關注名單即時監控")
    watchlist = preload_manager.frequent_queries["snapshots"]
    
    try:
        snapshot = qw.query_snapshot(watchlist)
        if not snapshot.empty:
            # 轉置一下方便看
            display_df = snapshot[["代號", "收盤", "漲跌", "漲跌幅%", "成交量"]].copy()
            
            # 加入漲跌視覺化
            def highlight_change(val):
                try:
                    if isinstance(val, (int, float)) and not pd.isna(val):
                        if val > 0:
                            return 'color: #e63946; font-weight: 600'
                        elif val < 0:
                            return 'color: #2a9d8f; font-weight: 600'
                except:
                    pass
                return ''
            
            styled = display_df.style.applymap(highlight_change, subset=["漲跌", "漲跌幅%"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("目前無關注名單數據")
    except Exception as e:
        st.warning(f"無法載入關注名單數據: {e}")
        main_logger.error(f"儀表板關注名單渲染出錯: {e}")

def render_dashboard():
    """完整儀表板"""
    render_dashboard_fragment()
