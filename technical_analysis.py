"""
技術分析模組 - Plotly 互動式K線圖 + 技術指標

使用方式（在 Streamlit app 中）：
    import technical_analysis as ta
    kbar_df = query_daily_kbar("2330", date(2025, 1, 1), date(2026, 5, 20))
    fig = ta.plot_kbar_with_indicators(kbar_df, "2330", indicators=["MA5", "MA20", "RSI", "MACD"])
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


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
              col: str = "close") -> tuple:
    """MACD (Moving Average Convergence Divergence)
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0,
                         col: str = "close") -> tuple:
    """布林帶 (Bollinger Bands)
    Returns: (middle_band, upper_band, lower_band)
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
    return df['TR'].rolling(window=window).mean()


# ═══════════════════════════════════════════════════════════
# 欄位標準化
# ═══════════════════════════════════════════════════════════

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    統一欄位名為小寫英文 (open/high/low/close/volume)。
    支援中文欄位、yfinance 大寫欄位等多種來源。
    """
    df = df.copy()

    # 明確映射（中文 + 大寫英文）
    col_map = {
        "開盤": "open", "最高": "high", "最低": "low", "收盤": "close",
        "成交量": "volume", "成交量(股)": "volume",
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # 剩餘欄位全部轉小寫（處理其他大寫情況）
    df = df.rename(columns={c: c.lower() for c in df.columns if c == c.upper() and c.isascii()})

    return df


# ═══════════════════════════════════════════════════════════
# K 線圖繪製（主函數）
# ═══════════════════════════════════════════════════════════

def plot_kbar_with_indicators(
    df: pd.DataFrame,
    code: str,
    indicators: list = None,
    title: str = None,
    height: int = 700,
) -> go.Figure:
    """
    繪製 K 線圖 + 技術指標（多行子圖）

    子圖佈局（由上到下）：
        Row 1：K 線 + MA/EMA + 布林帶
        Row 2：成交量柱狀圖（獨立 Y 軸，不壓縮 K 線）
        Row 3：RSI（如有）
        Row 4：MACD（如有）

    Parameters:
        df: DataFrame，需含 open/high/low/close/volume（或中文版）
        code: 股票代號（用於標題）
        indicators: 指標列表，支援 MA5/MA20/EMA12/RSI/MACD/BB/ATR 等
        title: 自訂標題（預設自動生成）
        height: 圖表總高度（px）

    Returns:
        plotly.graph_objects.Figure
    """
    if indicators is None:
        indicators = ["MA5", "MA20"]

    # ── 決定配色（美股/港股用綠漲紅跌；台股用紅漲藍跌） ───────────────────
    is_us = not code.isdigit()
    if is_us:
        up_color = "#2e7d32"  # 漲：綠
        down_color = "#d32f2f"  # 跌：紅
    else:
        up_color = "#d32f2f"  # 漲：紅
        down_color = "#1976d2"  # 跌：藍（台股習慣）

    # ── 欄位標準化 ─────────────────────────────────────────
    df = _normalize_columns(df)

    # ── 日期索引 ───────────────────────────────────────────
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors='coerce')
    except Exception:
        df.index = pd.RangeIndex(len(df))

    # 確保必要欄位存在
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame 缺少欄位：{missing}。現有欄位：{df.columns.tolist()}")

    has_volume = "volume" in df.columns

    # ── 計算指標（先比對完整名稱，再用 startswith 避免 MACD 被誤判為 MA）────
    indicator_data = {}
    for ind in indicators:
        if ind == "MACD":
            macd_line, signal_line, histogram = calc_macd(df)
            indicator_data["MACD"] = macd_line
            indicator_data["Signal"] = signal_line
            indicator_data["Histogram"] = histogram
        elif ind == "RSI":
            indicator_data["RSI"] = calc_rsi(df)
        elif ind == "BB":
            middle, upper, lower = calc_bollinger_bands(df)
            indicator_data["BB_Middle"] = middle
            indicator_data["BB_Upper"] = upper
            indicator_data["BB_Lower"] = lower
        elif ind == "ATR":
            indicator_data["ATR"] = calc_atr(df)
        elif ind.startswith("EMA"):
            w_str = ind[3:]
            window = int(w_str) if w_str.isdigit() else 12
            indicator_data[f"EMA{window}"] = calc_ema(df, window)
        elif ind.startswith("MA"):
            w_str = ind[2:]
            window = int(w_str) if w_str.isdigit() else 20
            indicator_data[f"MA{window}"] = calc_ma(df, window)

    # ── 計算子圖數量 ───────────────────────────────────────
    # Row 1: K 線（固定）
    # Row 2: 成交量（固定，小行）
    # Row 3: RSI（選用）
    # Row 4: MACD（選用）
    has_rsi = "RSI" in indicator_data
    has_macd = "MACD" in indicator_data
    has_atr = "ATR" in indicator_data

    rows = 2  # K 線 + 成交量
    row_rsi = row_macd = row_atr = None
    if has_rsi:
        rows += 1
        row_rsi = rows
    if has_macd:
        rows += 1
        row_macd = rows
    if has_atr:
        rows += 1
        row_atr = rows

    # 高度比例：K 線佔大部分，其他子圖較小
    kline_ratio = 0.55
    vol_ratio = 0.10
    other_ratio = (1.0 - kline_ratio - vol_ratio) / max(rows - 2, 1) if rows > 2 else 0
    row_heights = [kline_ratio, vol_ratio] + [other_ratio] * (rows - 2)

    # ── 建立子圖框架 ───────────────────────────────────────
    subplot_titles = [""] * rows
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.03,
        subplot_titles=subplot_titles,
    )

    # ═══════════════════════════════════════════════════════
    # Row 1：K 線 + MA / EMA / 布林帶
    # ═══════════════════════════════════════════════════════
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K線",
            increasing_line_color=up_color,
            increasing_fillcolor=up_color,
            decreasing_line_color=down_color,
            decreasing_fillcolor=down_color,
            line=dict(width=1),
        ),
        row=1, col=1,
    )

    # 布林帶（加填充區域，放在 MA 之前讓 MA 線顯示在上層）
    if "BB_Upper" in indicator_data:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["BB_Upper"],
                name="BB 上軌",
                line=dict(color="rgba(255, 152, 0, 0.6)", width=1, dash="dot"),
                hovertemplate="BB上軌: %{y:.2f}<extra></extra>",
                showlegend=True,
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["BB_Lower"],
                name="BB 下軌",
                line=dict(color="rgba(255, 152, 0, 0.6)", width=1, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(255, 152, 0, 0.05)",
                hovertemplate="BB下軌: %{y:.2f}<extra></extra>",
                showlegend=True,
            ),
            row=1, col=1,
        )
        # 中軌
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["BB_Middle"],
                name="BB 中軌",
                line=dict(color="rgba(255, 152, 0, 0.8)", width=1),
                hovertemplate="BB中軌: %{y:.2f}<extra></extra>",
            ),
            row=1, col=1,
        )

    # MA / EMA 線
    _MA_COLORS = {
        "MA5": "#ff9800", "MA10": "#00bcd4", "MA20": "#1565c0",
        "MA60": "#7b1fa2", "MA120": "#546e7a",
    }
    _EMA_COLORS = {
        "EMA5": "#ffeb3b", "EMA10": "#26c6da", "EMA12": "#ef5350",
        "EMA26": "#ab47bc",
    }
    for ind_name, ind_series in indicator_data.items():
        if ind_name.startswith("MA") and ind_name not in ("MACD",):
            color = _MA_COLORS.get(ind_name, "#90a4ae")
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=ind_series,
                    name=ind_name,
                    line=dict(color=color, width=1.5),
                    hovertemplate=f"{ind_name}: %{{y:.2f}}<extra></extra>",
                ),
                row=1, col=1,
            )
        elif ind_name.startswith("EMA"):
            color = _EMA_COLORS.get(ind_name, "#80cbc4")
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=ind_series,
                    name=ind_name,
                    line=dict(color=color, width=1.5, dash="dash"),
                    hovertemplate=f"{ind_name}: %{{y:.2f}}<extra></extra>",
                ),
                row=1, col=1,
            )

    # ═══════════════════════════════════════════════════════
    # Row 2：成交量（獨立 Y 軸，不影響 K 線比例）
    # ═══════════════════════════════════════════════════════
    if has_volume:
        vol_colors = [
            up_color if c >= o else down_color
            for c, o in zip(df["close"], df["open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["volume"],
                name="成交量",
                marker=dict(color=vol_colors, opacity=0.7),
                hovertemplate="成交量: %{y:,.0f}<extra></extra>",
            ),
            row=2, col=1,
        )

    # ═══════════════════════════════════════════════════════
    # RSI 子圖
    # ═══════════════════════════════════════════════════════
    if has_rsi:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["RSI"],
                name="RSI(14)",
                line=dict(color="#7e57c2", width=2),
                hovertemplate="RSI: %{y:.2f}<extra></extra>",
            ),
            row=row_rsi, col=1,
        )
        # 超買/超賣基準線
        fig.add_hrect(y0=70, y1=100, row=row_rsi, col=1,
                      fillcolor="rgba(211, 47, 47, 0.05)", line_width=0)
        fig.add_hrect(y0=0, y1=30, row=row_rsi, col=1,
                      fillcolor="rgba(25, 118, 210, 0.05)", line_width=0)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(211,47,47,0.6)",
                      line_width=1, row=row_rsi, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(25,118,210,0.6)",
                      line_width=1, row=row_rsi, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="rgba(128,128,128,0.4)",
                      line_width=1, row=row_rsi, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=row_rsi, col=1,
                         tickvals=[0, 30, 50, 70, 100])

    # ═══════════════════════════════════════════════════════
    # MACD 子圖
    # ═══════════════════════════════════════════════════════
    if has_macd:
        # Histogram 柱狀
        hist_values = indicator_data["Histogram"].fillna(0)
        hist_colors = [up_color if h >= 0 else down_color for h in hist_values]
        fig.add_trace(
            go.Bar(
                x=df.index, y=hist_values,
                name="MACD Hist",
                marker=dict(color=hist_colors, opacity=0.6),
                hovertemplate="Hist: %{y:.4f}<extra></extra>",
            ),
            row=row_macd, col=1,
        )
        # MACD 線
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["MACD"],
                name="MACD",
                line=dict(color="#1565c0", width=1.5),
                hovertemplate="MACD: %{y:.4f}<extra></extra>",
            ),
            row=row_macd, col=1,
        )
        # Signal 線
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["Signal"],
                name="Signal",
                line=dict(color="#e53935", width=1.5),
                hovertemplate="Signal: %{y:.4f}<extra></extra>",
            ),
            row=row_macd, col=1,
        )
        fig.add_hline(y=0, line_dash="dot", line_color="rgba(128,128,128,0.5)",
                      line_width=1, row=row_macd, col=1)
        fig.update_yaxes(title_text="MACD", row=row_macd, col=1)

    # ═══════════════════════════════════════════════════════
    # ATR 子圖
    # ═══════════════════════════════════════════════════════
    if has_atr:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indicator_data["ATR"],
                name="ATR(14)",
                line=dict(color="#ff7043", width=1.5),
                fill="tozeroy",
                fillcolor="rgba(255,112,67,0.08)",
                hovertemplate="ATR: %{y:.2f}<extra></extra>",
            ),
            row=row_atr, col=1,
        )
        fig.update_yaxes(title_text="ATR", row=row_atr, col=1)

    # ═══════════════════════════════════════════════════════
    # 全局佈局設定
    # ═══════════════════════════════════════════════════════
    if title is None:
        try:
            start_str = pd.Timestamp(df.index[0]).strftime("%Y-%m-%d")
            end_str = pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")
            title = f"{code} 技術分析  {start_str} ~ {end_str}"
        except Exception:
            title = f"{code} 技術分析"

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center", font=dict(size=14)),
        height=height,
        template="plotly_dark",          # 深色背景，K 線顏色更鮮明
        hovermode="x unified",
        margin=dict(l=60, r=20, t=50, b=20),
        font=dict(family="Arial, sans-serif", size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="right", x=1,
            font=dict(size=10),
        ),
        # 關閉 K 線的 rangeslider
        xaxis_rangeslider_visible=False,
    )

    # Y 軸標籤
    fig.update_yaxes(title_text="價格", row=1, col=1, tickformat=".2f" if is_us else ".0f")
    fig.update_yaxes(title_text="成交量", row=2, col=1, tickformat=".2s")

    # X 軸：統一關閉 rangeslider，最後一個子圖顯示日期
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_xaxes(showticklabels=True, row=rows, col=1)

    return fig


# ═══════════════════════════════════════════════════════════
# 快速視覺化函數
# ═══════════════════════════════════════════════════════════

def quick_chart(code: str, df: pd.DataFrame, indicators: list = None) -> go.Figure:
    """便利函數：快速畫 K 線圖（預設 MA5 + MA20 + RSI）"""
    if indicators is None:
        indicators = ["MA5", "MA20", "RSI"]
    return plot_kbar_with_indicators(df, code, indicators)
