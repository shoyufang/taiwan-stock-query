"""
Phase J: 估值深化 — PE 河流圖與同業比較

PE 河流圖：計算歷史 EPS，疊加 PE 價格帶（10/30/50/70/90 百分位），
一眼看出「現在股價在歷史估值帶的哪一層」。
"""
import numpy as np
import plotly.graph_objects as go

import query_wrapper as qw
from theme import get_updown_colors


def plot_pe_river(code: str, years: int = 5) -> go.Figure:
    """
    PE 河流圖。

    1. 取 PER 歷史數據
    2. 計算歷史 EPS = 收盤價 / PER
    3. 以 PER 的 10/30/50/70/90 百分位畫五條價格帶
    4. 疊上實際股價線
    """
    # 取得 PER 歷史
    import pandas as pd
    from datetime import date, timedelta

    start = (date.today() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    end = date.today().strftime("%Y-%m-%d")

    # 先讀 FinMind PER/PBR
    try:
        from datasources.finmind_client import query_per_pbr
        per_df = query_per_pbr(code, start, end)
    except Exception as e:
        main_logger = __import__('logging_config', fromlist=['main_logger']).main_logger
        main_logger.warning(f"PE river: PER 查詢失敗 ({code}): {e}")
        return _empty_pe_figure(f"PER 資料不可用: {e}")

    if per_df.empty:
        return _empty_pe_figure("無 PER 歷史資料")

    # 取得實際股價（用 Shioaji 快照或 yfinance）
    try:
        import yfinance as yf
        tw_code = f"{code}.TW"
        hist = yf.Ticker(tw_code).history(period=f"{years}y")
        if hist.empty:
            return _empty_pe_figure("股價資料不可用")
        hist = hist.reset_index()
        hist.columns = [c.lower().replace(' ', '_') for c in hist.columns]
        if 'date' not in hist.columns:
            return _empty_pe_figure("日期欄位缺失")
    except Exception as e:
        main_logger = __import__('logging_config', fromlist=['main_logger']).main_logger
        main_logger.warning(f"PE river: 股價查詢失敗 ({code}): {e}")
        return _empty_pe_figure("股價資料不可用")

    # 合併 PER + 股價
    per_df["日期"] = pd.to_datetime(per_df["日期"]).dt.tz_localize(None)
    hist["date"] = pd.to_datetime(hist["date"]).dt.tz_localize(None)

    merged = per_df.merge(
        hist[["date", "close"]],
        left_on="日期", right_on="date", how="inner"
    )

    if merged.empty:
        return _empty_pe_figure("PER 與股價資料無法匹配")

    # 計算歷史 EPS
    per_col = [c for c in merged.columns if "PER" in c or "本益比" in c][0]
    close_col = [c for c in merged.columns if "close" in c][0]

    merged["EPS"] = merged[close_col] / merged[per_col]
    merged = merged.dropna(subset=["EPS"])

    if merged.empty:
        return _empty_pe_figure("EPS 計算失敗（可能有零值或負值 PER）")

    # 計算 PER 百分位對應的價格帶
    per_percentiles = [10, 30, 50, 70, 90]
    per_values = merged[per_col].dropna()

    if per_values.empty or per_values.min() <= 0:
        return _empty_pe_figure("不適用（近期 EPS 為負或 PER 無正數）")

    percentile_levels = per_values.quantile([p / 100 for p in per_percentiles])

    # 用中位數 EPS 計算各百分位對應的價格
    median_eps = merged["EPS"].median()
    price_levels = {}
    for p, qv in percentile_levels.items():
        price_levels[int(p)] = round(qv * median_eps, 2)

    try:
        st = __import__('streamlit', fromlist=['session_state'])
        theme_name = st.session_state.get("theme", "🌅 Claude 暖橘")
        up_color, down_color = get_updown_colors(theme_name)
    except Exception:
        up_color = "#d6453d"
        down_color = "#1a9c6b"
    theme_colors = [
        "rgba(217,119,87,0.15)",  # 10th - 最便宜
        "rgba(217,119,87,0.25)",  # 30th
        "rgba(217,119,87,0.35)",  # 50th
        "rgba(217,119,87,0.50)",  # 70th
        "rgba(217,119,87,0.70)",  # 90th - 最貴
    ]

    fig = go.Figure()

    # 價格帶填充區域
    for i, (p, price) in enumerate(sorted(price_levels.items())):
        label = f"P{p} ({price:,.0f}元)"
        if i == 0:
            fig.add_trace(go.Scatter(
                x=merged["日期"], y=[price] * len(merged),
                fill=None, mode="lines", name=label,
                line=dict(color=theme_colors[i], width=1, dash="dot"),
            ))
        else:
            prev_price = list(price_levels.values())[i - 1]
            fig.add_trace(go.Scatter(
                x=list(merged["日期"]) + list(reversed(merged["日期"])),
                y=[price] * len(merged) + [prev_price] * len(merged),
                fill="tonexty", mode="lines", name=label,
                line=dict(width=0),
                fillcolor=theme_colors[i],
            ))

    # 實際股價線
    fig.add_trace(go.Scatter(
        x=merged["日期"], y=merged[close_col],
        mode="lines", name="實際股價",
        line=dict(color=up_color, width=2),
        hovertemplate="日期: %{x|%Y/%m/%d}<br>股價: %{y:,.0f}元<extra></extra>",
    ))

    # 當前 PER 標記
    latest_per = merged[per_col].iloc[-1]
    latest_price = merged[close_col].iloc[-1]
    latest_eps = merged["EPS"].iloc[-1]

    fig.add_annotation(
        x=merged["日期"].iloc[-1], y=latest_price,
        text=f"PE {latest_per:.1f}<br>{latest_price:,.0f}元",
        showarrow=False,
        xanchor="left", yanchor="bottom",
        bgcolor="rgba(0,0,0,0.7)",
        bordercolor=up_color, borderwidth=1,
    )

    fig.update_layout(
        height=350,
        title=dict(
            text=f"{code} PE 河流圖（近 {years} 年）",
            x=0.5, font=dict(size=13),
        ),
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
        margin=dict(l=55, r=20, t=50, b=40),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_yaxes(title_text="價格（元）", gridcolor="rgba(128,128,128,0.1)")
    fig.update_xaxes(title_text="日期", tickformat="%Y/%m", tickangle=-30)

    return fig


def _empty_pe_figure(reason: str) -> go.Figure:
    """回傳空白的 PE 河流圖"""
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper",
        text=f"⚠️ {reason}",
        showarrow=False, font=dict(size=14),
    )
    fig.update_layout(height=300, template="plotly_white")
    return fig


def plot_peer_comparison(codes: list) -> go.Figure:
    """
    同業比較圖（Bar Chart）。
    顯示各股的 PE/PB/殖利率。
    """
    import pandas as pd
    import query_wrapper as qw

    try:
        val_df = qw.query_twse_valuation()
    except Exception:
        return _empty_peer_figure("估值資料不可用")

    if val_df.empty:
        return _empty_peer_figure("估值資料不可用")

    # 篩選目標股票
    code_col = [c for c in val_df.columns if "代號" in c or "Code" in c or "code" in c][0]
    target = val_df[val_df[code_col].astype(str).isin([str(c) for c in codes])]

    if target.empty:
        return _empty_peer_figure("查無估值資料")

    # 找出 PE/PB/殖利率欄位
    pe_col = [c for c in target.columns if "本益比" in c or "PE" in c][0] if any("本益比" in c or "PE" in c for c in target.columns) else None
    pb_col = [c for c in target.columns if "股淨比" in c or "PB" in c or "PBR" in c][0] if any("股淨比" in c or "PB" in c or "PBR" in c for c in target.columns) else None
    yld_col = [c for c in target.columns if "殖利率" in c][0] if any("殖利率" in c for c in target.columns) else None

    fig = go.Figure()

    # PE bar
    if pe_col:
        fig.add_trace(go.Bar(
            x=target[code_col].astype(str),
            y=pd.to_numeric(target[pe_col], errors="coerce"),
            name="本益比",
            marker_color="rgba(217,119,87,0.7)",
        ))

    # PB bar
    if pb_col:
        fig.add_trace(go.Bar(
            x=target[code_col].astype(str),
            y=pd.to_numeric(target[pb_col], errors="coerce"),
            name="股淨比",
            marker_color="rgba(59,130,246,0.7)",
        ))

    # Yield bar
    if yld_col:
        fig.add_trace(go.Bar(
            x=target[code_col].astype(str),
            y=pd.to_numeric(target[yld_col], errors="coerce"),
            name="殖利率%",
            marker_color="rgba(16,185,129,0.7)",
        ))

    fig.update_layout(
        height=300,
        barmode="group",
        title=dict(text="同業估值比較", x=0.5, font=dict(size=13)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=55, r=20, t=50, b=60),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-30),
    )

    return fig


def _empty_peer_figure(reason: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper",
        text=f"⚠️ {reason}",
        showarrow=False, font=dict(size=14),
    )
    fig.update_layout(height=300, template="plotly_white")
    return fig
