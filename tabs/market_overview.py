"""
市場總覽 — 專業看盤首頁（Phase B）

版面設計（由上而下）：
  ① 指數行情條（Ticker Strip）— 30 秒刷新
  ② 市場寬度（漲跌家數）+ 三大法人買賣超
  ③ 台美 ADR 溢折價
  ④ 今日排行（漲幅｜跌幅｜成交量｜成交額）
  ⑤ 盤前警示（處置股｜注意股｜今日除息）
  ⑥ 大盤新聞
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, date

import query_wrapper as qw
from logging_config import main_logger


# ──────────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────────

def is_market_open() -> bool:
    """週一至五 09:00-13:30 台北時間"""
    from datetime import time as dt_time
    now = datetime.now()
    if now.weekday() >= 5:  # 6=週六, 7=週日
        return False
    return dt_time(9, 0) <= now.time() <= dt_time(13, 30)


def fmt_number(v, decimals=2) -> str:
    """數字格式化（千分位 + 小數）"""
    if pd.isna(v):
        return "-"
    try:
        return f"{float(v):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


def fmt_amount_yi(v) -> str:
    """億格式化"""
    if pd.isna(v):
        return "-"
    try:
        return f"{float(v) / 1e8:,.1f} 億"
    except (ValueError, TypeError):
        return "-"


def _color_up(v) -> str:
    """台股漲紅"""
    try:
        return "color: #d6453d; font-weight: 700" if float(v) > 0 else "color: #1a9c6b; font-weight: 700" if float(v) < 0 else ""
    except (ValueError, TypeError, ZeroDivisionError):
        return ""


def _safe_div(a, b, decimals=2):
    """安全除法"""
    try:
        if b == 0 or pd.isna(b):
            return None
        return round(float(a) / float(b) * 100, decimals)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


# ──────────────────────────────────────────────
# 區塊 ①：指數行情條
# ──────────────────────────────────────────────

@st.fragment(run_every=30 if is_market_open() else None)
def render_index_strip():
    """指數行情條 — 加權指數、櫃買、台指期、匯率、美股期貨"""
    c1, c2, c3, c4, c5 = st.columns(5)

    # 加權指數（即時 yfinance）
    with c1:
        try:
            twii = yf.T("^TWII")
            data = twii.history(period="5d")
            if not data.empty:
                price = data["Close"].iloc[-1]
                prev = data["Close"].iloc[-2] if len(data) > 1 else price
                change = price - prev
                pct = _safe_div(change, prev)
                arrow = "▲" if change >= 0 else "▼"
                color = "#d6453d" if change >= 0 else "#1a9c6b"
                st.metric(
                    label="📈 加權指數",
                    value=f"{price:,.0f}",
                    delta=f"{arrow} {abs(change):,.0f} ({pct:+.2f}%)" if pct is not None else None
                )
                st.markdown(f'<div style="color:{color};font-size:0.8rem;font-weight:600">台積電 {price:,.0f}</div>', unsafe_allow_html=True)
        except Exception:
            st.metric("📈 加權指數", "—", "資料暫不可用")

    # 櫃買指數
    with c2:
        try:
            tpei = yf.T("^TPEx")
            data = tpei.history(period="5d")
            if not data.empty:
                price = data["Close"].iloc[-1]
                prev = data["Close"].iloc[-2] if len(data) > 1 else price
                change = price - prev
                pct = _safe_div(change, prev)
                arrow = "▲" if change >= 0 else "▼"
                st.metric("🏪 櫃買指數", f"{price:,.1f}", f"{arrow} {abs(change):,.1f}" if pct is not None else None)
        except Exception:
            st.metric("🏪 櫃買指數", "—", "—")

    # 台指期 vs 現貨價差
    with c3:
        try:
            tx_df = qw.query_futures_daily("TX", date.today() - timedelta(days=1), date.today())
            if not tx_df.empty:
                tx_close = float(tx_df.iloc[-1]["收盤"])
                twii_df = yf.T("^TWII").history(period="2d")
                if not twii_df.empty:
                    index_close = float(twii_df["Close"].iloc[-1])
                    diff = tx_close - index_close
                    basis_str = f"價差 +{diff:,.0f}" if diff >= 0 else f"價差 {diff:,.0f}"
                    basis_color = "#d6453d" if diff >= 0 else "#1a9c6b"
                    st.metric("📊 台指期", f"{tx_close:,.0f}", basis_str)
                    st.markdown(f'<div style="color:{basis_color};font-size:0.75rem">{diff:.0f} (+{(_safe_div(diff, index_close)):.2f}%)</div>', unsafe_allow_html=True)
        except Exception:
            st.metric("📊 台指期", "—", "—")

    # 匯率 USD/TWD
    with c4:
        try:
            rate_data = qw.adr_query.get_usd_twd_rate() if hasattr(qw, "adr_query") else {"rate": 32.2}
            if not isinstance(rate_data, dict):
                rate_data = {"rate": 32.2}
            rate = rate_data.get("rate", 32.2)
            st.metric("💵 USD/TWD", f"{rate:.4f}", "—")
        except Exception:
            st.metric("💵 USD/TWD", "—", "—")

    # 費半 + 那指
    with c5:
        try:
            sox = yf.T("^SOX")
            data = sox.history(period="5d")
            if not data.empty:
                price = data["Close"].iloc[-1]
                prev = data["Close"].iloc[-2] if len(data) > 1 else price
                change = price - prev
                pct = _safe_div(change, prev)
                arrow = "▲" if change >= 0 else "▼"
                st.metric("🔶 費城半導體", f"{price:,.1f}", f"{arrow} {abs(change):,.1f}" if pct is not None else None)
        except Exception:
            st.metric("🔶 費半", "—", "—")

    st.divider()


# ──────────────────────────────────────────────
# 區塊 ② + ③：市場寬度 + 三大法人
# ──────────────────────────────────────────────

def render_market_breadth_and_institutions():
    """市場寬度（漲跌家數）+ 三大法人"""
    row1, row2 = st.columns([1, 1], gap="medium")

    # ── 市場寬度 ──
    with row1:
        st.markdown('<p style="font-size:0.82rem;font-weight:700;color:var(--claude-text-2);margin-bottom:6px;">📊 市場寬度（當日全市場）</p>', unsafe_allow_html=True)
        try:
            all_df = qw.query_twse_daily_all()
            if not all_df.empty and "漲跌" in all_df.columns:
                up_count = int((all_df["漲跌"] > 0).sum())
                down_count = int((all_df["漲跌"] < 0).sum())
                flat_count = int((all_df["漲跌"] == 0).sum())
                total = len(all_df)
                total_amt = all_df["成交金額"].sum() if "成交金額" in all_df.columns else 0

                # 漲跌停（簡化判斷：漲跌 > 10% 漲停, < -10% 跌停）
                up_limit = int((all_df["漲跌"] >= 10).sum()) if "漲跌" in all_df.columns else 0
                down_limit = int((all_df["漲跌"] <= -10).sum()) if "漲跌" in all_df.columns else 0

                cols = st.columns(4)
                cols[0].metric("↑ 上漲", up_count, delta=None)
                cols[1].metric("↓ 下跌", down_count, delta=None)
                cols[2].metric("📉 跌停", up_limit, delta=None)
                cols[3].metric("📊 成交金額", fmt_amount_yi(total_amt), delta=None)

                # 詳細資訊
                st.caption(f"合計 {total} 檔 | 平盤 {flat_count} 檔")
            else:
                st.caption("資料暫不可用")
        except Exception as e:
            main_logger.warning(f"市場寬度查詢失敗: {e}")
            st.caption("資料暫不可用")

    # ── 三大法人 ──
    with row2:
        st.markdown('<p style="font-size:0.82rem;font-weight:700;color:var(--claude-text-2);margin-bottom:6px;">🏛️ 三大法人今日買賣超</p>', unsafe_allow_html=True)
        try:
            inst_df = qw.query_twse_institutional()
            if not inst_df.empty:
                # 彙總：找今日最後一筆
                latest = inst_df.iloc[-1] if isinstance(inst_df, pd.DataFrame) else None
                if latest is not None and hasattr(latest, '__getitem__'):
                    foreign = float(latest["外資買賣超"]) if "外資買賣超" in inst_df.columns else 0
                    self_inst = float(latest["投信買賣超"]) if "投信買賣超" in inst_df.columns else 0
                    dealer = float(latest["自營商買賣超"]) if "自營商買賣超" in inst_df.columns else 0

                    cols = st.columns(3)
                    cols[0].metric("💼 外資", f"{foreign:+,.0f} 億", delta_color="off")
                    cols[1].metric("🏢 投信", f"{self_inst:+,.0f} 億", delta_color="off")
                    cols[2].metric("📈 自營商", f"{dealer:+,.0f} 億", delta_color="off")

                    # 總和條
                    total_net = foreign + self_inst + dealer
                    bar_color = "#d6453d" if total_net >= 0 else "#1a9c6b"
                    st.markdown(f'<div style="margin-top:4px;color:{bar_color};font-weight:700;font-size:0.82rem">淨流入: {total_net:+,.0f} 億</div>', unsafe_allow_html=True)
                else:
                    st.caption("資料格式異常")
            else:
                st.caption("資料暫不可用")
        except Exception as e:
            main_logger.warning(f"三大法人查詢失敗: {e}")
            st.caption("資料暫不可用")

    st.divider()


# ──────────────────────────────────────────────
# 區塊 ④：台美 ADR 溢折價
# ──────────────────────────────────────────────

def render_adr_section():
    """台美 ADR 溢折價卡片"""
    st.markdown('<p style="font-size:0.82rem;font-weight:700;color:var(--claude-text-2);margin-bottom:6px;">⚖️ 台美 ADR 溢折價</p>', unsafe_allow_html=True)
    try:
        from adr_query import get_adr_snapshots
        adr_data = get_adr_snapshots()
        rate = adr_data["rate"]
        ts_cached = adr_data["timestamp"]
        cols = st.columns(3)
        for idx, item in enumerate(adr_data["data"]):
            premium_pct = item["premium_pct"]
            badge_color = "var(--claude-primary)" if premium_pct >= 0 else "#1976d2"
            badge_bg = "rgba(217, 119, 87, 0.12)" if premium_pct >= 0 else "rgba(25, 118, 210, 0.12)"
            with cols[idx]:
                st.markdown(f"""
                <div style="border-radius:10px;padding:12px;border:1px solid var(--claude-border);background:var(--claude-surface);box-shadow:0 1px 4px var(--claude-shadow);">
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                        <span style="font-weight:700;font-size:0.85rem;">{item['name']} {item['key']}</span>
                        <span style="background:{badge_bg};border-radius:5px;padding:2px 7px;color:{badge_color};font-weight:700;font-size:0.8rem;">{premium_pct:+.2f}%</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                        <span>美股 {item['adr_ticker']} ${item['adr_price']:.2f}</span>
                        <span>台股 {item['tw_code']} {item['tw_price']:.1f}元</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:0.68rem;color:var(--claude-text-2);text-align:right;margin-top:4px;">匯率 {rate:.4f} | 快取 {ts_cached}</div>', unsafe_allow_html=True)
    except Exception as e:
        main_logger.warning(f"ADR 查詢失敗: {e}")
        st.caption("ADR 資料暫不可用")

    st.divider()


# ──────────────────────────────────────────────
# 區塊 ⑤：今日排行
# ──────────────────────────────────────────────

def render_rankings():
    """今日排行（漲幅｜跌幅｜成交量｜成交額）"""
    st.markdown('<p style="font-size:0.82rem;font-weight:700;color:var(--claude-text-2);margin-bottom:6px;">📊 今日排行</p>', unsafe_allow_html=True)

    tabs = st.tabs(["🔺 漲幅", "🔻 跌幅", "📦 成交量", "💰 成交額"])
    ranking_map = {"🔺 漲幅": "ChangePercentRank", "🔻 跌幅": "ChangePercentRank", "📦 成交量": "VolumeRank", "💰 成交額": "AmountRank"}
    reverse_map = {"🔺 涨幅": True, "🔻 跌幅": False, "📦 成交量": False, "💰 成交額": False}

    for tab_label, ranking_type in ranking_map.items():
        with tabs[list(ranking_map.keys()).index(tab_label)]:
            try:
                df = qw.query_ranking(ranking_type, limit=15)
                if not df.empty:
                    cols_to_show = ["代號", "名稱"]
                    if "收盤" in df.columns:
                        cols_to_show.append("收盤")
                    if "漲跌" in df.columns:
                        cols_to_show.append("漲跌")
                    if "漲跌幅%" in df.columns:
                        cols_to_show.append("漲跌幅%")
                    if "成交量" in df.columns:
                        cols_to_show.append("成交量")
                    if "成交金額" in df.columns:
                        cols_to_show.append("成交金額")

                    show_cols = [c for c in cols_to_show if c in df.columns]
                    display_df = df[show_cols].head(15)

                    # 漲跌欄上色
                    for col in ["漲跌", "漲跌幅%"]:
                        if col in display_df.columns:
                            display_df[col] = display_df[col].apply(lambda v: f"{v:+,.2f}" if pd.notna(v) else "-")

                    st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
                else:
                    st.caption("無數據")
            except Exception as e:
                main_logger.warning(f"排行查詢失敗 ({ranking_type}): {e}")
                st.caption("資料暫不可用")


# ──────────────────────────────────────────────
# 區塊 ⑥：盤前警示
# ──────────────────────────────────────────────

def render_alerts():
    """盤前警示：處置股、注意股、今日除息"""
    row1, row2 = st.columns(2)

    with row1:
        st.markdown('<p style="font-size:0.82rem;font-weight:700;color:var(--claude-text-2);margin-bottom:6px;">⚠️ 盤前警示</p>', unsafe_allow_html=True)

        # 處置股
        try:
            disp_df = qw.query_twse_disposition()
            if not disp_df.empty and "證券代號" in disp_df.columns:
                count = len(disp_df)
                codes = ", ".join(str(c) for c in disp_df["證券代號"].head(10))
                st.metric("🔴 處置股", f"{count} 檔")
                with st.expander(f"處置股代號（前10檔）", expanded=False):
                    st.code(codes)
                    if count > 10:
                        st.caption(f"...等共 {count} 檔")
            else:
                st.metric("🔴 處置股", "0 檔")
        except Exception as e:
            main_logger.warning(f"處置股查詢失敗: {e}")
            st.metric("🔴 處置股", "—", "查詢失敗")

        # 注意股
        with st.expander("🟡 注意有價證券", expanded=False):
            try:
                notice_df = qw.query_twse_notice()
                if not notice_df.empty and "證券代號" in notice_df.columns:
                    count = len(notice_df)
                    codes = ", ".join(str(c) for c in notice_df["證券代號"].head(10))
                    st.write(f"共 **{count}** 檔")
                    st.code(codes)
                else:
                    st.caption("無注意股")
            except Exception as e:
                main_logger.warning(f"注意股查詢失敗: {e}")
                st.caption("查詢失敗")

        # 今日除息
        with st.expander("💰 今日除息", expanded=False):
            try:
                cal_df = qw.tw_calendar.get_tw_calendar_consensus_data() if hasattr(qw.tw_calendar, "get_tw_calendar_consensus_data") else pd.DataFrame()
                if cal_df.empty:
                    import tw_calendar
                    cal_df = tw_calendar.get_tw_calendar_consensus_data()
                if not cal_df.empty and "除息日" in cal_df.columns:
                    today_str = date.today().strftime("%Y-%m-%d")
                    today_div = cal_df[cal_df["除息日"].astype(str).str.startswith(today_str[:10])]
                    if not today_div.empty:
                        st.success(f"**{len(today_div)}** 檔今日除息")
                        for _, row in today_div.iterrows():
                            code = row.get("代號", "?")
                            name = row.get("名稱", "")
                            eps = row.get("預估下季EPS", "-")
                            st.write(f"• **{code}** {name} — 預估 EPS {eps}")
                    else:
                        st.caption(f"今日 ({today_str}) 無除息股")
                else:
                    st.caption("無數據")
            except Exception as e:
                main_logger.warning(f"除息查詢失敗: {e}")
                st.caption("查詢失敗")

    with row2:
        st.markdown('<p style="font-size:0.82rem;font-weight:700;color:var(--claude-text-2);margin-bottom:6px;">📰 大盤新聞（最新 5 則）</p>', unsafe_allow_html=True)
        try:
            news_df = qw.query_market_news(limit=5)
            if not news_df.empty and "標題" in news_df.columns:
                for _, row in news_df.iterrows():
                    title = row["標題"]
                    source = row.get("來源", "")
                    time_str = row.get("時間", "")
                    st.markdown(f"""
                    <div style="padding:8px 10px;border-radius:8px;border:1px solid var(--claude-border-light);margin-bottom:6px;background:var(--claude-surface);">
                        <div style="font-weight:600;font-size:0.82rem;">{title}</div>
                        <div style="font-size:0.7rem;color:var(--claude-text-2);margin-top:2px;">{source} · {time_str}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("無新聞")
        except Exception as e:
            main_logger.warning(f"新聞查詢失敗: {e}")
            st.caption("新聞暫不可用")


# ──────────────────────────────────────────────
# 主渲染
# ──────────────────────────────────────────────

def render_market_overview():
    """專業看盤首頁 — 市場總覽"""
    st.markdown("### 🏠 市場總覽")
    st.caption("一屏掌握大盤，10 秒判斷今天是什麼盤")

    # 區塊 ①：指數行情條（自動刷新）
    render_index_strip()

    # 區塊 ②③：市場寬度 + 三大法人
    render_market_breadth_and_institutions()

    # 區塊 ④：ADR
    render_adr_section()

    # 區塊 ⑤：排行
    render_rankings()

    # 區塊 ⑥：盤前警示 + 新聞
    render_alerts()
