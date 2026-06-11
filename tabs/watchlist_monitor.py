"""
自選股即時監控 — 報價牆 + 個股全景跳轉
Phase D 升級：metric 卡、距 52 週高點 %、量比、→ 個股全景按鈕
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from logging_config import main_logger
import query_wrapper as qw
from stock_lookup import resolve_code
from tabs._shared import goto_stock_page


def _color_up(v) -> str:
    try:
        return "color: #d6453d; font-weight: 700" if float(v) > 0 else "color: #1a9c6b; font-weight: 700" if float(v) < 0 else ""
    except (ValueError, TypeError):
        return ""


def _safe_div(a, b, decimals=2):
    try:
        if b == 0 or pd.isna(b):
            return None
        return round(float(a) / float(b) * 100, decimals)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def render_watchlist_monitor():
    """自選股報價牆 — Phase D 升級版"""
    st.markdown("### 👁️ 自選股")
    st.caption("即時報價牆，一鍵跳轉個股全景（Phase B.3 goto_stock_page）")

    # ── 初始自選股 ──
    if "watchlist_codes" not in st.session_state:
        default_wl = ["2330", "2317", "2454", "2308", "2382"]
        st.session_state.watchlist_codes = default_wl

    # ── 管理列 ──
    col_input, col_add, col_edit, col_clear = st.columns([3, 1, 1, 1])

    with col_input:
        new_code = st.text_input(
            "新增代號（逗號分隔）",
            placeholder="例：2330, 2317, 2454",
            key="wl_input",
            label_visibility="collapsed"
        )
    with col_add:
        if st.button("➕ 新增", use_container_width=True):
            if new_code:
                codes = [c.strip() for c in new_code.split(",") if c.strip()]
                for code in codes:
                    if code not in st.session_state.watchlist_codes:
                        st.session_state.watchlist_codes.append(code)
                st.rerun()
    with col_edit:
        if st.button("✏️ 編輯名單", use_container_width=True):
            st.session_state.show_wl_editor = True
            st.rerun()
    with col_clear:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.watchlist_codes = []
            st.rerun()

    # ── 編輯名單 Popover ──
    if st.session_state.get("show_wl_editor"):
        with st.popover("✏️ 編輯自選股名單", use_container_width=True):
            codes_text = ", ".join(st.session_state.watchlist_codes)
            new_text = st.text_area("代號清單", value=codes_text, height=100, key="wl_editor_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 儲存", use_container_width=True, type="primary"):
                    codes = [c.strip() for c in new_text.split(",") if c.strip()]
                    st.session_state.watchlist_codes = codes
                    del st.session_state.show_wl_editor
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True):
                    del st.session_state.show_wl_editor
                    st.rerun()

    codes = st.session_state.watchlist_codes
    if not codes:
        st.info("💡 輸入代號加入自選股，或預載的 2330/2317/2454/2308/2382")
        return

    # ── 查詢快照 ──
    try:
        snap = qw.query_snapshot(codes)
    except Exception as e:
        main_logger.warning(f"自選股快照查詢失敗: {e}")
        snap = pd.DataFrame()

    if snap.empty:
        # Fallback: yfinance
        snap = _fetch_yfinance_watchlist(codes)

    if snap.empty:
        st.warning("無可用數據")
        return

    # ── 顯示報價牆 ──
    st.markdown("---")

    # 計算 52 週高點 % 和量比
    snap = _compute_extra_metrics(snap, codes)

    # 格式化顯示
    display_cols = ["代號", "名稱", "收盤", "漲跌", "漲跌幅%", "成交量"]
    display_cols = [c for c in display_cols if c in snap.columns]

    # 加個股全景按鈕
    for _, row in snap.iterrows():
        code = str(row.get("代號", ""))
        name = row.get("名稱", "")
        close = row.get("收盤", 0)
        change = row.get("漲跌", 0)
        pct = row.get("漲跌幅%", 0)
        volume = row.get("成交量", 0)
        dist_52w = row.get("距52週高%", None)
        vol_ratio = row.get("量比", None)

        up_color = "#d6453d" if float(change) >= 0 else "#1a9c6b" if str(change).lstrip("-").replace(".", "").isdigit() and float(change) != 0 else ""

        html = f"""
        <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;border:1px solid var(--claude-border-light);margin-bottom:4px;background:var(--claude-surface);">
            <span style="font-weight:700;font-size:0.85rem;min-width:50px;">{code}</span>
            <span style="font-size:0.8rem;color:var(--claude-text-2);min-width:60px;">{name}</span>
            <span style="font-size:0.95rem;font-weight:700;color:{up_color};min-width:65px;text-align:right;">{close:,.0f}</span>
            <span style="font-size:0.82rem;font-weight:600;color:{up_color};min-width:65px;text-align:right;">{change:+,.0f}</span>
            <span style="font-size:0.82rem;font-weight:600;color:{up_color};min-width:60px;text-align:right;">{pct:+.2f}%</span>
            <span style="font-size:0.75rem;color:var(--claude-text-2);min-width:65px;text-align:right;">{volume:,}</span>
            {"<span style='font-size:0.75rem;color:#d6453d;'>(%s)</span>" % str(dist_52w) if dist_52w is not None else ""}
            {"<span style='font-size:0.75rem;color:#1a9c6b;'>(%s)</span>" % str(vol_ratio) if vol_ratio is not None else ""}
            <button style="font-size:0.75rem;padding:2px 8px;border-radius:5px;border:1px solid var(--claude-primary);background:transparent;color:var(--claude-primary);cursor:pointer;"
                    onclick="window.parent.postMessage({{'streamlit:rerun'}}, '*')"
                    data-code="{code}">→ 個股</button>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

    st.caption(f"⏱️ 每 30 秒自動刷新 | → 個股 = 跳轉個股全景頁")


def _fetch_yfinance_watchlist(codes: list) -> pd.DataFrame:
    """Fallback: 用 yfinance 查詢非台股"""
    rows = []
    for code in codes:
        if code.isdigit() and len(code) <= 4:
            # 台股用 TW 後綴
            ticker = yf.T(f"{code}.TW")
        else:
            ticker = yf.T(code)
        data = ticker.history(period="5d")
        if not data.empty:
            price = data["Close"].iloc[-1]
            prev = data["Close"].iloc[-2] if len(data) > 1 else price
            change = price - prev
            pct = _safe_div(change, prev)
            volume = data["Volume"].iloc[-1]
            name = ticker.info.get("shortName", code)
            rows.append({
                "代號": code,
                "名稱": name,
                "收盤": price,
                "漲跌": change,
                "漲跌幅%": pct if pct is not None else 0,
                "成交量": volume,
            })
    return pd.DataFrame(rows)


def _compute_extra_metrics(df: pd.DataFrame, codes: list) -> pd.DataFrame:
    """計算距 52 週高點 % 和量比"""
    df = df.copy()
    df["距52週高%"] = None
    df["量比"] = None

    for idx, code in enumerate(codes):
        if code.isdigit() and len(code) <= 4:
            try:
                ticker = yf.T(f"{code}.TW")
                data = ticker.history(period="52wk")
                if not data.empty:
                    high_52w = data["High"].max()
                    close = float(df.iloc[idx].get("收盤", 0))
                    dist_pct = _safe_div(close - high_52w, high_52w)
                    df.iloc[idx, df.columns.get_loc("距52週高%")] = f"{dist_pct:.1f}%" if dist_pct is not None else "-"

                # 量比：今日成交量 / 5 日均量
                if not data.empty:
                    vol_today = float(df.iloc[idx].get("成交量", 0))
                    vol_5d = data["Volume"].tail(5).mean()
                    if vol_5d > 0:
                        vol_ratio = vol_today / vol_5d
                        df.iloc[idx, df.columns.get_loc("量比")] = f"{vol_ratio:.2f}x"
            except Exception:
                pass

    return df
