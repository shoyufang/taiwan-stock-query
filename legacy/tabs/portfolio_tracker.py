"""
投資組合追蹤 — 輸入買入成本/張數，計算未實現損益 + 日報表
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from logging_config import main_logger
import query_wrapper as qw


def render_portfolio_tracker():
    """渲染投資組合追蹤器"""
    st.subheader("💼 投資組合追蹤")
    st.caption("輸入持股資訊，即時計算未實現損益")
    
    # 初始化 session state
    if "portfolio_holdings" not in st.session_state:
        st.session_state.portfolio_holdings = _load_portfolio()
    
    # 輸入區域
    st.markdown("---")
    st.markdown("**➕ 新增持股**")
    
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        code = st.text_input("股票代號", placeholder="例：2330", key="portfolio_code")
    with col2:
        shares = st.number_input("張數", min_value=1, value=1, key="portfolio_shares")
    with col3:
        cost = st.number_input("買入成本（元）", min_value=0.0, value=0.0, step=0.1, key="portfolio_cost")
    with col4:
        st.write("")  # 垂直對齊
        if st.button("➕ 新增", use_container_width=True, key="portfolio_add"):
            if code and cost > 0:
                _add_holding(code, shares, cost)
                st.rerun()
    
    # 顯示投資組合
    if st.session_state.portfolio_holdings:
        st.markdown("---")
        st.markdown("**📊 投資組合概覽**")
        
        # 獲取即時報價
        codes = [h["code"] for h in st.session_state.portfolio_holdings]
        try:
            snapshot = qw.query_snapshot(codes)
            _render_portfolio_table(snapshot)
        except Exception as e:
            st.error(f"無法獲取即時報價: {e}")
            main_logger.error(f"投資組合報價失敗: {e}")


def _load_portfolio() -> list:
    """載入投資組合（從 session state 或檔案）"""
    return []


def _save_portfolio(holdings: list):
    """儲存投資組合"""
    # 未來可擴充為持久化儲存
    pass


def _add_holding(code: str, shares: int, cost: float):
    """新增持股"""
    holding = {
        "code": code,
        "shares": shares,
        "cost": cost,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    st.session_state.portfolio_holdings.append(holding)
    _save_portfolio(st.session_state.portfolio_holdings)
    st.success(f"✅ 已新增 {code} ({shares} 張 @ {cost}元)")


def _render_portfolio_table(snapshot: pd.DataFrame):
    """渲染投資組合表格"""
    if snapshot.empty:
        st.warning("無法獲取持股即時報價")
        return
    
    # 建立投資組合資料
    portfolio_data = []
    total_cost = 0
    total_value = 0
    
    for holding in st.session_state.portfolio_holdings:
        code = holding["code"]
        shares = holding["shares"]  # 張數
        cost = holding["cost"]  # 每股成本
        
        # 查找即時報價
        row = snapshot[snapshot["代號"] == code]
        if row.empty:
            continue
        
        current_price = row.iloc[0]["收盤"]
        change = row.iloc[0]["漲跌"]
        change_pct = row.iloc[0]["漲跌幅%"]
        
        # 計算（1 張 = 1000 股）
        shares_total = shares * 1000
        cost_total = cost * shares_total
        value_total = current_price * shares_total
        pnl = value_total - cost_total
        pnl_pct = (pnl / cost_total) * 100 if cost_total > 0 else 0
        
        total_cost += cost_total
        total_value += value_total
        
        portfolio_data.append({
            "代號": code,
            "張數": shares,
            "買入價": cost,
            "現價": current_price,
            "漲跌": change,
            "漲跌幅%": change_pct,
            "成本": f"{cost_total:,.0f}",
            "現值": f"{value_total:,.0f}",
            "損益": f"{pnl:,.0f}",
            "損益%": f"{pnl_pct:+.2f}%"
        })
    
    if not portfolio_data:
        st.warning("無有效持股資料")
        return
    
    df = pd.DataFrame(portfolio_data)
    
    # 顯示總覽
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 總成本", f"{total_cost:,.0f}元")
    with col2:
        st.metric("📈 總現值", f"{total_value:,.0f}元")
    with col3:
        st.metric("📊 總損益", f"{total_pnl:+,.0f}元 ({total_pnl_pct:+.2f}%)")
    
    st.divider()
    
    # 顯示明細表格
    st.dataframe(df, use_container_width=True, hide_index=True)
