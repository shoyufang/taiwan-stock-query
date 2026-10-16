"""
技術指標掃描器 — 篩選符合特定技術條件的股票
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from logging_config import main_logger
from stock_pools import TW_TOP50 as TW_BLUE_CHIPS


def render_technical_scanner():
    """渲染技術指標掃描器"""
    st.subheader("🔍 技術指標掃描器")
    st.caption("掃描台股 50 權值股，找出符合技術條件的股票")
    
    # 掃描條件設定
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rsi_oversold = st.checkbox("RSI 超賣 (< 30)", value=True, key="ts_rsi_os")
        rsi_overbought = st.checkbox("RSI 超買 (> 70)", value=False, key="ts_rsi_ob")
    
    with col2:
        ma_golden_cross = st.checkbox("MA 黃金交叉 (5日 > 20日)", value=True, key="ts_ma_gc")
        ma_death_cross = st.checkbox("MA 死亡交叉 (5日 < 20日)", value=False, key="ts_ma_dc")
    
    with col3:
        volume_breakout = st.checkbox("成交量突破 (> 2倍均量)", value=False, key="ts_vol_bo")
        price_breakout = st.checkbox("價格突破 20日高點", value=False, key="ts_price_bo")
    
    if st.button("🚀 開始掃描", type="primary", use_container_width=True, key="ts_scan_btn"):
        _run_scanner(
            rsi_oversold, rsi_overbought,
            ma_golden_cross, ma_death_cross,
            volume_breakout, price_breakout
        )


def _run_scanner(
    rsi_oversold: bool, rsi_overbought: bool,
    ma_golden_cross: bool, ma_death_cross: bool,
    volume_breakout: bool, price_breakout: bool
):
    """執行掃描"""
    with st.spinner("正在掃描 50 檔權值股..."):
        results = []
        
        for code in TW_BLUE_CHIPS:
            try:
                df = _fetch_kbar(code)
                if df.empty:
                    continue
                
                signals = _analyze_signals(df)
                
                # 檢查是否符合任一條件
                match = False
                matched_conditions = []
                
                if rsi_oversold and signals.get("rsi_oversold"):
                    match = True
                    matched_conditions.append("RSI超賣")
                if rsi_overbought and signals.get("rsi_overbought"):
                    match = True
                    matched_conditions.append("RSI超買")
                if ma_golden_cross and signals.get("ma_golden_cross"):
                    match = True
                    matched_conditions.append("MA黃金交叉")
                if ma_death_cross and signals.get("ma_death_cross"):
                    match = True
                    matched_conditions.append("MA死亡交叉")
                if volume_breakout and signals.get("volume_breakout"):
                    match = True
                    matched_conditions.append("成交量突破")
                if price_breakout and signals.get("price_breakout"):
                    match = True
                    matched_conditions.append("價格突破")
                
                if match:
                    results.append({
                        "代號": code,
                        "收盤價": signals.get("close", 0),
                        "漲跌": signals.get("change", 0),
                        "RSI": f"{signals.get('rsi', 0):.1f}",
                        "MA5": f"{signals.get('ma5', 0):.1f}",
                        "MA20": f"{signals.get('ma20', 0):.1f}",
                        "成交量": signals.get("volume", 0),
                        "符合條件": ", ".join(matched_conditions)
                    })
            except Exception as e:
                main_logger.warning(f"掃描 {code} 失敗: {e}")
        
        if results:
            result_df = pd.DataFrame(results)
            st.success(f"✅ 找到 {len(results)} 檔符合條件的股票")
            st.dataframe(result_df, use_container_width=True, hide_index=True)
        else:
            st.info("目前沒有股票符合掃描條件")


def _fetch_kbar(code: str, days: int = 60) -> pd.DataFrame:
    """獲取 K 線數據"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 嘗試從 query_wrapper 獲取（有快取）
        try:
            import query_wrapper as qw
            from datetime import date
            df = qw.query_daily_kbar(code, start_date.date(), end_date.date())
            if not df.empty:
                return df
        except:
            pass
        
        # Fallback 到 yfinance
        ticker = yf.Ticker(f"{code}.TW")
        df = ticker.history(start=start_date, end=end_date)
        if not df.empty:
            df.index = df.index.tz_localize(None)
            df.index.name = "Date"
            return df
        
        return pd.DataFrame()
    except Exception as e:
        main_logger.warning(f"獲取 {code} K線失敗: {e}")
        return pd.DataFrame()


def _analyze_signals(df: pd.DataFrame) -> dict:
    """分析技術訊號"""
    signals = {}
    
    try:
        close = df["收盤"].values if "收盤" in df.columns else df["Close"].values
        volume = df["成交量"].values if "成交量" in df.columns else df["Volume"].values
        
        if len(close) < 20:
            return signals
        
        # 基本數據
        signals["close"] = close[-1]
        signals["change"] = close[-1] - close[-2] if len(close) > 1 else 0
        signals["volume"] = volume[-1] if len(volume) > 0 else 0
        
        # RSI 計算 (14日)
        rsi_period = 14
        if len(close) > rsi_period:
            delta = pd.Series(close).diff()
            gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            signals["rsi"] = rsi.iloc[-1]
            signals["rsi_oversold"] = rsi.iloc[-1] < 30
            signals["rsi_overbought"] = rsi.iloc[-1] > 70
        
        # MA 計算
        ma5 = pd.Series(close).rolling(window=5).mean()
        ma20 = pd.Series(close).rolling(window=20).mean()
        
        signals["ma5"] = ma5.iloc[-1]
        signals["ma20"] = ma20.iloc[-1]
        
        # 黃金交叉 / 死亡交叉
        if len(ma5) > 1:
            signals["ma_golden_cross"] = ma5.iloc[-1] > ma20.iloc[-1] and ma5.iloc[-2] <= ma20.iloc[-2]
            signals["ma_death_cross"] = ma5.iloc[-1] < ma20.iloc[-1] and ma5.iloc[-2] >= ma20.iloc[-2]
        
        # 成交量突破 (2倍 20日均量)
        if len(volume) > 20:
            avg_volume = pd.Series(volume).rolling(window=20).mean().iloc[-1]
            signals["volume_breakout"] = volume[-1] > 2 * avg_volume
        
        # 價格突破 20日高點
        if len(close) > 20:
            high_20 = max(close[-20:-1])
            signals["price_breakout"] = close[-1] > high_20
        
    except Exception as e:
        main_logger.warning(f"分析訊號失敗: {e}")
    
    return signals
