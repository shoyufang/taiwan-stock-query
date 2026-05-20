"""
技術分析模組 - Plotly 互動式K線圖 + 技術指標

使用方式（在 Streamlit app 中）：
    import technical_analysis as ta
    kbar_df = query_daily_kbar_finmind("2330", "2025-01-01", "2026-05-20")
    fig = ta.plot_kbar_with_indicators(kbar_df, "2330", indicators=["MA", "RSI", "MACD"])
    st.plotly_chart(fig, use_container_width=True)
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ═══════════════════════════════════════════════════════════
# 技術指標計算
# ═══════════════════════════════════════════════════════════

def calc_ma(df: pd.DataFrame, window: int = 20, col: str = "close") -> pd.Series:
    """移動平均線 (MA)"""
    return df[col].rolling(window=window).mean()


def calc_ema(df: pd.DataFrame, window: int = 12, col: str = "close") -> pd.Series:
    """指數移動平均線 (EMA)"""
    return df[col].ewm(span=window, adjust=False).mean()


def calc_rsi(df: pd.DataFrame, window: int = 14, col: str = "close") -> pd.Series:
    """相對強度指標 (RSI)"""
    delta = df[col].diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, col: str = "close") -> tuple:
    """MACD (Moving Average Convergence Divergence)

    Returns:
        (macd_line, signal_line, histogram)
    """
    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0, col: str = "close") -> tuple:
    """布林帶 (Bollinger Bands)

    Returns:
        (middle_band, upper_band, lower_band)
    """
    middle = df[col].rolling(window=window).mean()
    std = df[col].rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return middle, upper, lower


def calc_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """真實波幅 (Average True Range)"""
    df = df.copy()
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift())
    df['L-PC'] = abs(df['low'] - df['close'].shift())
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    atr = df['TR'].rolling(window=window).mean()
    return atr


# ═══════════════════════════════════════════════════════════
# K 線圖繪製
# ═══════════════════════════════════════════════════════════

def plot_kbar_with_indicators(
    df: pd.DataFrame,
    code: str,
    indicators: list = None,
    title: str = None,
    height: int = 700,
) -> go.Figure:
    """
    繪製 K 線圖 + 技術指標

    Parameters:
        df: DataFrame，必須有 close, open, high, low, volume 欄位
        code: 股票代號（用於標題）
        indicators: 指標列表，如 ["MA5", "MA20", "RSI", "MACD", "BB"]
        title: 自訂標題
        height: 圖表高度（px）

    Returns:
        plotly.graph_objects.Figure
    """
    if indicators is None:
        indicators = ["MA5", "MA20"]

    # 標準化欄位名
    df = df.copy()
    col_map = {
        "開盤": "open", "最高": "high", "最低": "low", "收盤": "close",
        "成交量": "volume", "成交量(股)": "volume",
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    df = df.rename(columns=str.lower)
    df.index = pd.to_datetime(df.index) if not isinstance(df.index, pd.DatetimeIndex) else df.index

    # 計算指標
    indicator_data = {}
    for ind in indicators:
        if ind.startswith("MA"):
            window = int(ind[2:]) if len(ind) > 2 else 20
            indicator_data[f"MA{window}"] = calc_ma(df, window)
        elif ind.startswith("EMA"):
            window = int(ind[3:]) if len(ind) > 3 else 12
            indicator_data[f"EMA{window}"] = calc_ema(df, window)
        elif ind == "RSI":
            indicator_data["RSI"] = calc_rsi(df)
        elif ind == "MACD":
            macd, signal, hist = calc_macd(df)
            indicator_data["MACD"] = macd
            indicator_data["Signal"] = signal
            indicator_data["Histogram"] = hist
        elif ind == "BB":
            middle, upper, lower = calc_bollinger_bands(df)
            indicator_data["BB_Middle"] = middle
            indicator_data["BB_Upper"] = upper
            indicator_data["BB_Lower"] = lower
        elif ind == "ATR":
            indicator_data["ATR"] = calc_atr(df)

    # 判斷需要幾個子圖
    num_subplots = 1
    if "RSI" in indicator_data:
        num_subplots += 1
    if "MACD" in indicator_data:
        num_subplots += 1

    # 建立子圖
    row_heights = [0.7] + [0.15] * (num_subplots - 1)
    fig = make_subplots(
        rows=num_subplots, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.08,
    )

    # ──── 第 1 行：K 線圖 ────
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K線",
            increasing_line_color="red",
            decreasing_line_color="green",
        ),
        row=1, col=1,
    )

    # 新增成交量柱狀圖
    colors = ["red" if close >= open_ else "green"
              for close, open_ in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["volume"],
            name="成交量",
            marker=dict(color=colors),
            opacity=0.3,
        ),
        row=1, col=1,
    )

    # 新增移動平均線
    colors_ma = {"MA5": "orange", "MA10": "cyan", "MA20": "blue", "MA60": "purple", "MA120": "gray"}
    for ind_name, ind_series in indicator_data.items():
        if ind_name.startswith("MA") or ind_name.startswith("EMA"):
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=ind_series,
                    name=ind_name,
                    line=dict(color=colors_ma.get(ind_name, "gray"), width=1.5),
                    hovertemplate=f"{ind_name}: %{{y:.2f}}<extra></extra>",
                ),
                row=1, col=1,
            )

    # 新增布林帶
    if "BB_Upper" in indicator_data:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=indicator_data["BB_Upper"],
                name="BB 上軌",
                line=dict(color="rgba(255, 0, 0, 0.3)", width=1),
                hovertemplate="BB Upper: %{y:.2f}<extra></extra>",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=indicator_data["BB_Lower"],
                name="BB 下軌",
                line=dict(color="rgba(0, 255, 0, 0.3)", width=1),
                fill="tonexty",
                hovertemplate="BB Lower: %{y:.2f}<extra></extra>",
            ),
            row=1, col=1,
        )

    # ──── 第 2 行：RSI ────
    if "RSI" in indicator_data:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=indicator_data["RSI"],
                name="RSI(14)",
                line=dict(color="purple", width=2),
                hovertemplate="RSI: %{y:.2f}<extra></extra>",
            ),
            row=2, col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # ──── 第 3 行：MACD ────
    if "MACD" in indicator_data:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=indicator_data["MACD"],
                name="MACD",
                line=dict(color="blue", width=2),
                hovertemplate="MACD: %{y:.4f}<extra></extra>",
            ),
            row=3, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=indicator_data["Signal"],
                name="Signal",
                line=dict(color="red", width=2),
                hovertemplate="Signal: %{y:.4f}<extra></extra>",
            ),
            row=3, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=indicator_data["Histogram"],
                name="Histogram",
                marker=dict(color=["red" if h > 0 else "green" for h in indicator_data["Histogram"]]),
                opacity=0.3,
            ),
            row=3, col=1,
        )

    # ──── 佈局設定 ────
    if title is None:
        title = f"{code} 技術分析 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})"

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        height=height,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=0, r=0, t=40, b=0),
        font=dict(family="Arial", size=11),
    )

    # 更新 Y 軸標籤
    fig.update_yaxes(title_text="價格", row=1, col=1)
    if "RSI" in indicator_data:
        fig.update_yaxes(title_text="RSI", row=2, col=1)
    if "MACD" in indicator_data:
        fig.update_yaxes(title_text="MACD", row=3, col=1)

    # 更新 X 軸
    fig.update_xaxes(rangeslider_visible=False)

    return fig


# ═══════════════════════════════════════════════════════════
# 快速視覺化函數
# ═══════════════════════════════════════════════════════════

def quick_chart(code: str, df: pd.DataFrame, indicators: list = None) -> go.Figure:
    """便利函數：快速畫 K 線圖"""
    if indicators is None:
        indicators = ["MA5", "MA20", "RSI"]
    return plot_kbar_with_indicators(df, code, indicators)
