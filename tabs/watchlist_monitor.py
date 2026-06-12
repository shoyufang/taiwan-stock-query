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
from config import load_watchlist, save_watchlist


def _color_up(v) -> str:
    try:
        return "color: var(--up-color); font-weight: 700" if float(v) > 0 else "color: var(--down-color); font-weight: 700" if float(v) < 0 else ""
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

    # ── 初始自選股（統一用 config.py load/save，三軌同步） ──
    if "watchlist_codes" not in st.session_state:
        wl_data = load_watchlist()
        codes = wl_data.get("watchlist", [])
        if not codes:
            codes = ["2330", "2317", "2454", "2308", "2382"]
            save_watchlist({"watchlist": codes})
        st.session_state.watchlist_codes = codes

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
        if st.button("➕ 新增", use_container_width=True, key="wm_add_btn"):
            if new_code:
                codes = [c.strip() for c in new_code.split(",") if c.strip()]
                for code in codes:
                    if code not in st.session_state.watchlist_codes:
                        st.session_state.watchlist_codes.append(code)
                save_watchlist({"watchlist": st.session_state.watchlist_codes})
                st.rerun()
    with col_edit:
        if st.button("✏️ 編輯名單", use_container_width=True, key="wm_edit_btn"):
            st.session_state.show_wl_editor = True
            st.rerun()
    with col_clear:
        if st.button("🗑️ 清空", use_container_width=True, key="wm_clear_btn"):
            st.session_state.watchlist_codes = []
            st.rerun()

    # ── 警示 Popover ──
    with st.popover("🔔 管理警示", use_container_width=True):
        try:
            from config import load_alerts, save_alerts
            import json
            from datetime import datetime as dt2

            current_alerts = load_alerts()
            alert_dict = {}
            for a in current_alerts:
                code = str(a.get("code", ""))
                if code not in alert_dict:
                    alert_dict[code] = []
                alert_dict[code].append(a)

            if codes:
                for code in codes:
                    code = str(code).strip().zfill(4)
                    st.markdown(f"**{code}**")
                    existing = alert_dict.get(code, [])
                    for i, a in enumerate(existing):
                        st.caption(f"• {a['type']} ≥ {a['value']} {'✅' if a.get('enabled') else '❌'}")

                    with st.expander("➕ 新增規則", expanded=False):
                        atype = st.radio("類型", ["price_above", "price_below", "pct_move"],
                                         horizontal=True, key=f"alert_type_{code}", label_visibility="collapsed")
                        atype_label = {"price_above": "價格突破", "price_below": "價格跌破", "pct_move": "單日漲跌"}
                        st.caption(atype_label.get(atype, atype))
                        if atype == "pct_move":
                            avalue = st.number_input("門檻 (%)", value=5.0, min_value=0.1, step=0.5, key=f"alert_val_{code}")
                        else:
                            avalue = st.number_input("價格/門檻", value=1000.0, min_value=0.1, step=10.0, key=f"alert_val_{code}")
                        if st.button("📌 新增警示", key=f"alert_add_{code}", type="primary", use_container_width=True):
                            if not any(a.get("code") == code and a.get("type") == atype for a in current_alerts):
                                current_alerts.append({
                                    "code": code, "type": atype, "value": avalue,
                                    "enabled": True, "name": code,
                                    "created": dt2.now().isoformat(),
                                })
                                save_alerts(current_alerts)
                                st.rerun()
                            else:
                                st.warning("已存在相同規則")
                    st.divider()
            else:
                st.caption("無自選股，無法新增警示")
        except Exception as e:
            main_logger.warning(f"警示管理失敗: {e}")
            st.caption("警示管理暫時不可用")

    # ── 編輯名單 Popover ──
    if st.session_state.get("show_wl_editor"):
        with st.popover("✏️ 編輯自選股名單", use_container_width=True):
            codes_text = ", ".join(st.session_state.watchlist_codes)
            new_text = st.text_area("代號清單", value=codes_text, height=100, key="wl_editor_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 儲存", use_container_width=True, type="primary", key="wm_save_btn"):
                    codes = [c.strip() for c in new_text.split(",") if c.strip()]
                    st.session_state.watchlist_codes = codes
                    save_watchlist({"watchlist": codes})
                    del st.session_state.show_wl_editor
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True, key="wm_cancel_btn"):
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

    # Phase K.3: 盤中視覺警示
    triggered_alerts = {}
    try:
        from alert_engine import check_alerts_intraday
        alert_map = check_alerts_intraday(codes)
        if "_alerts" in alert_map:
            for a in alert_map["_alerts"]:
                code = str(a.get("code", "")).strip().zfill(4)
                if code not in triggered_alerts:
                    triggered_alerts[code] = []
                triggered_alerts[code].append(a)
    except Exception:
        pass

    # 格式化顯示
    display_cols = ["代號", "名稱", "收盤", "漲跌", "漲跌幅%", "成交量"]
    display_cols = [c for c in display_cols if c in snap.columns]

    # 加入警示旗標
    alert_flags = []
    for _, row in snap.iterrows():
        code = str(row.get("代號", "")).strip().zfill(4)
        if code in triggered_alerts:
            alert_flags.append("🔔 觸發")
        else:
            alert_flags.append("")
    snap["警示"] = alert_flags

    # 加入額外指標
    if "距52週高%" in snap.columns:
        display_cols.insert(2, "距52週高%")
    if "量比" in snap.columns:
        display_cols.insert(2, "量比")

    col_cfg = {}
    if "收盤" in display_cols:
        col_cfg["收盤"] = st.column_config.NumberColumn("收盤", format="localized")
    if "成交量" in display_cols:
        col_cfg["成交量"] = st.column_config.NumberColumn("成交量", format="localized")

    event = st.dataframe(
        snap[display_cols],
        use_container_width=True,
        hide_index=True,
        height=min(38 + 35 * min(len(snap), 15), 570),
        on_select="rerun",
        selection_mode="single-row",
        key="watchlist_tbl",
        column_config=col_cfg,
    )
    rows = event.selection.rows if event and hasattr(event, "selection") else []
    if rows:
        code = str(snap.iloc[rows[0]].get("代號", ""))
        handled_key = "watchlist_sel_handled"
        if code.isdigit() and st.session_state.get(handled_key) != (rows[0], code):
            st.session_state[handled_key] = (rows[0], code)
            goto_stock_page(code)
    st.caption(f"⏱️ 每 30 秒自動刷新 | 💡 點選任一列即可跳轉個股全景")


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
