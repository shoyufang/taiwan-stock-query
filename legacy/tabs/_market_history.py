"""
Phase G: 市場歷史資料視覺化

讀取 data/market/*.csv（每日加權指數＋三大法人），
提供大盤走勢圖、法人累計趨勢、市場寬度小圖。
"""
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from query_wrapper import cached_query
from theme import get_updown_colors
from logging_config import main_logger

# 找到 data 目錄（支援 repo 根與 NAS Docker 容器路徑）
_DATA_DIR = None


def _find_data_dir():
    global _DATA_DIR
    if _DATA_DIR:
        return _DATA_DIR
    candidates = [
        Path("data/market"),  # repo 根
        Path("/volume1/docker/sinopac/data/market"),  # NAS
    ]
    # 也嘗試 relative 到本模組
    base = Path(__file__).resolve().parent.parent  # repo 根
    candidates.insert(0, base / "data" / "market")
    for p in candidates:
        if p.is_dir() and list(p.glob("*.csv")):
            _DATA_DIR = p
            main_logger.debug(f"market_history: data_dir={_DATA_DIR}")
            return p
    main_logger.warning("market_history: 找不到 data/market 目錄，將回傳空 DataFrame")
    _DATA_DIR = Path("")
    return _DATA_DIR


@cached_query(ttl=3600, sqlite_ttl=3600, name="market_history")
def load_market_history(days: int = 250) -> pd.DataFrame:
    """
    讀取 data/market/*.csv 合併為單一 DataFrame。

    欄位（各日檔可能部分缺失）：
      date, taiex, taiex_chg, taiex_pct, trust, dealer

    回傳：
      sorted DataFrame (date, taiex, taiex_chg, taiex_pct, trust, dealer, foreign)
      其中 foreign = trust（外資買賣超合計）
    """
    data_dir = _find_data_dir()
    if not data_dir or not data_dir.is_dir():
        return pd.DataFrame(columns=["date", "taiex", "taiex_chg", "taiex_pct", "trust", "dealer", "foreign"])

    csv_files = sorted(data_dir.glob("*.csv"), reverse=True)
    frames = []

    required_cols = {"date"}
    for csv_file in csv_files[:days + 30]:  # 多讀一些以防假日缺檔
        try:
            df = pd.read_csv(csv_file, encoding="utf-8-sig")
            if df.empty:
                continue
            # 標準化欄位名：小寫 + 去掉可能的亂碼
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            # 保留共有的欄位
            frames.append(df)
            required_cols |= set(df.columns)
        except Exception as e:
            main_logger.debug(f"market_history: 跳過 {csv_file.name}: {e}")
            continue

    if not frames:
        return pd.DataFrame(columns=["date", "taiex", "taiex_chg", "taiex_pct", "trust", "dealer", "foreign"])

    combined = pd.concat(frames, ignore_index=True)

    # 確保 date 存在
    if "date" not in combined.columns:
        main_logger.warning("market_history: CSV 中無 date 欄位")
        return pd.DataFrame()

    # 标准化日期
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date"])
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date", ascending=False).reset_index(drop=True)

    # 取最近 N 日
    combined = combined.head(days).reset_index(drop=True)

    # 計算外資（trust 就是外資）
    if "trust" in combined.columns:
        combined["foreign"] = combined["trust"]
    else:
        combined["foreign"] = 0.0

    # 確保 numeric
    for col in ["taiex", "taiex_chg", "taiex_pct", "trust", "dealer", "foreign"]:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")
        else:
            combined[col] = 0.0

    return combined


def get_plotly_colors(theme_name: str = None):
    """取得當前主題的 Plotly 漲跌色"""
    if theme_name is None:
        import streamlit as st
        theme_name = st.session_state.get("theme", "🌅 Claude 暖橘")
    colors = get_updown_colors(theme_name)
    return colors["up"], colors["down"]


def render_market_chart(days: int = 250, theme_name: str = None):
    """
    繪製大盤主圖（Plotly 雙軸）：
      - 上軸：加權指數收盤線（近 N 日）
      - 下軸：三大法人累計買賣超面積圖（cumsum）
    """
    df = load_market_history(days)
    if df.empty:
        import streamlit as st
        st.warning("⚠️ 尚無歷史市場資料（data/market/ 目錄空或不存在）。每日排程將自動累積。")
        return

    up_color, down_color = get_plotly_colors(theme_name)

    # 排序（由早到晚）
    df = df.sort_values("date").reset_index(drop=True)

    n = len(df)
    dates = df["date"]

    # 計算累計法人買賣超
    foreign_cum = df["foreign"].cumsum()
    trust_cum = df["trust"].cumsum()
    dealer_cum = df["dealer"].cumsum()

    # 創建子圖（2 行：指數 + 法人）
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.65, 0.35],
        subplot_titles=["加權指數", "三大法人累計買賣超（張）"],
    )

    # 上層：加權指數線
    fig.add_trace(
        go.Scatter(
            x=dates, y=df["taiex"],
            mode="lines",
            name="加權指數",
            line=dict(color=up_color, width=2),
            hovertemplate="日期: %{x|%Y/%m/%d}<br>收盤: %{y:,.0f}<br>漲跌: %{customdata}<extra></extra>",
            customdata=df.apply(lambda r: f"{r['taiex_chg']:+,.0f} ({r['taiex_pct']:+.2f}%)", axis=1),
        ),
        row=1, col=1,
    )

    # 法人累計面積圖（堆疊）
    # 外資（上為正、下為負）
    fig.add_trace(
        go.Scatter(
            x=dates, y=foreign_cum,
            fill="tozeroy",
            name="外資累計",
            fillcolor=f"rgba(255, 100, 100, 0.3)",
            line=dict(color=up_color, width=1.5),
            hovertemplate="日期: %{x|%Y/%m/%d}<br>外資累計: %{y:,.0f} 張<extra></extra>",
        ),
        row=2, col=1,
    )

    # 投信
    fig.add_trace(
        go.Scatter(
            x=dates, y=trust_cum,
            fill="tozeroy",
            name="投信累計",
            fillcolor=f"rgba(100, 150, 255, 0.3)",
            line=dict(color="#3B82F6", width=1.5),
            hovertemplate="日期: %{x|%Y/%m/%d}<br>投信累計: %{y:,.0f} 張<extra></extra>",
        ),
        row=2, col=1,
    )

    # 自營商
    fig.add_trace(
        go.Scatter(
            x=dates, y=dealer_cum,
            fill="tozeroy",
            name="自營商累計",
            fillcolor=f"rgba(100, 255, 150, 0.3)",
            line=dict(color="#10B981", width=1.5),
            hovertemplate="日期: %{x|%Y/%m/%d}<br>自營商累計: %{y:,.0f} 張<extra></extra>",
        ),
        row=2, col=1,
    )

    # 零線
    fig.add_hline(
        y=0, line=dict(color="rgba(128,128,128,0.4)", dash="dot"),
        row=2, col=1,
    )

    fig.update_layout(
        height=320,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
        margin=dict(l=55, r=20, t=30, b=40),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_yaxes(title_text="指數點", row=1, col=1, gridcolor="rgba(128,128,128,0.1)")
    fig.update_yaxes(title_text="張", row=2, col=1, gridcolor="rgba(128,128,128,0.1)")
    fig.update_xaxes(title_text="日期", tickformat="%Y/%m", tickangle=-30)

    import streamlit as st
    st.plotly_chart(fig, use_container_width=True, key="mo_market_chart")


def breadth_sparkline(days: int = 60, theme_name: str = None):
    """
    繪製市場寬度小圖：近 N 日三大法人合計買賣超柱狀圖（高 ~120px）。
    正數紅、負數綠。
    """
    df = load_market_history(days)
    if df.empty:
        import streamlit as st
        st.caption("📊 法人累計趨勢資料不足")
        return

    df = df.sort_values("date").reset_index(drop=True)

    up_color, down_color = get_plotly_colors(theme_name)

    # 法人合計
    total_inst = df["foreign"] + df["trust"] + df["dealer"]

    # 顏色：正紅、負綠
    colors = [up_color if v >= 0 else down_color for v in total_inst]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"],
        y=total_inst,
        marker_color=colors,
        opacity=0.7,
        hovertemplate="日期: %{x|%Y/%m/%d}<br>法人合計: %{y:,.0f} 張<extra></extra>",
    ))

    fig.add_hline(y=0, line=dict(color="rgba(128,128,128,0.3)", dash="dot"))

    fig.update_layout(
        height=120,
        margin=dict(l=45, r=10, t=5, b=30),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(tickformat="%Y/%m", tickangle=-30, tickfont=dict(size=8)),
        yaxis=dict(tickfont=dict(size=8), gridcolor="rgba(128,128,128,0.1)"),
    )

    import streamlit as st
    st.plotly_chart(fig, use_container_width=True, key="mo_breadth_sparkline")


def data_asof(label: str, ts):
    """
    資料時效標示：在區塊右上角顯示小字「📅 資料時間：…」
    """
    import streamlit as st
    if pd.isna(ts):
        ts_str = "資料不足"
    else:
        if hasattr(ts, "strftime"):
            ts_str = ts.strftime("%Y/%m/%d")
        else:
            ts_str = str(ts)
    st.caption(f"📅 {label}：{ts_str}")
