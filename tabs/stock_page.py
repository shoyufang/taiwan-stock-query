"""
個股全景頁 — 一個代號看完所有面向（殺手級功能，Phase C）

版面：
  ┌─────────────────────────────────────────────────────────────┐
  │ [搜尋框] [🔍] [⭐加自選]                                      │
  ├─────────────────────────────────────────────────────────────┤
  │ 個股表頭（即時報價）                                          │
  ├─────────────────────────────────────────────────────────────┤
  │ st.tabs：📈 技術 ｜ 📊 籌碼 ｜ 💰 基本面 ｜ 🏛️ 五檔大單 ｜ 📰 新聞AI │
  └─────────────────────────────────────────────────────────────┘
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, date

from stock_lookup import resolve_code, get_name_hint
import query_wrapper as qw
from logging_config import main_logger


# ──────────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────────

def is_tw_stock(code: str) -> bool:
    """台股：純數字（含 5-6 碼 ETF）"""
    return code.isdigit()


def _color_up(v) -> str:
    """台股漲紅跌綠（改用 CSS 變數）"""
    try:
        return "color: var(--up-color); font-weight: 700" if float(v) > 0 else "color: var(--down-color); font-weight: 700" if float(v) < 0 else ""
    except (ValueError, TypeError):
        return ""


# ──────────────────────────────────────────────
# 區塊 0：搜尋 + 表頭
# ──────────────────────────────────────────────

def render_stock_header():
    """搜尋框 + 個股表頭（含即時報價）"""
    st.markdown("### 🔍 個股全景")
    st.caption("輸入代號或中文名稱，一頁掌握報價、技術、籌碼、基本面、新聞/AI")

    col_code, col_btn1, col_btn2 = st.columns([3, 1, 1])
    with col_code:
        raw_input = st.text_input(
            "股票代號 / 中文名稱",
            placeholder="例：2330、台積電、NVDA",
            key="sp_code_input",
            label_visibility="collapsed"
        )
    with col_btn1:
        do_search = st.button("🔍 查詢", use_container_width=True, type="primary", key="sp_search_btn")
    with col_btn2:
        do_watchlist = st.button("⭐ 加自選", use_container_width=True, key="sp_watchlist_btn")

    code = ""
    name = ""
    is_tw = False

    if do_search and raw_input:
        code = resolve_code(raw_input)
        if code:
            name = raw_input if raw_input.isdigit() or len(raw_input) > 2 else code
            is_tw = is_tw_stock(code)
            st.session_state["sp_code"] = code
            st.session_state["sp_name"] = name
            st.session_state["sp_is_tw"] = is_tw
            st.rerun()
        else:
            st.warning(f"找不到 '{raw_input}' 對應的股票代號")

    if do_watchlist and raw_input:
        from config import load_watchlist, save_watchlist
        code = resolve_code(raw_input)
        if code:
            wl_data = load_watchlist()
            wl = wl_data.get("watchlist", [])
            if code not in wl:
                wl.append(code)
                save_watchlist({"watchlist": wl})
                st.success(f"已將 {code} 加入自選股")
            else:
                st.info(f"{code} 已在自選股中")
            st.rerun()

    # 若已查詢，顯示表頭
    code = st.session_state.get("sp_code", "")
    name = st.session_state.get("sp_name", "")
    is_tw = st.session_state.get("sp_is_tw", True)

    if not code:
        st.caption("💡 提示：此頁面整合技術分析、籌碼面、基本面、五檔大單與新聞/AI 於一頁")
        return code, name, is_tw

    # ── 即時報價表頭 ──
    try:
        if is_tw:
            # 台股：Shioaji 快照
            snap = qw.query_snapshot([code])
            if not snap.empty:
                row = snap.iloc[0]
                close = float(row.get("收盤", 0))
                change = float(row.get("漲跌", 0))
                pct = float(row.get("漲跌幅%", 0)) if "漲跌幅%" in row else 0
                volume = row.get("成交量", 0)
                open_price = row.get("開盤", 0)
                high = row.get("最高", 0)
                low = row.get("最低", 0)
                prev_close = row.get("昨收", close - change)
                amplitude = _safe_div(high - low, prev_close, 2) if prev_close > 0 else 0

                up_color = "var(--up-color)" if change >= 0 else "var(--down-color)"
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:20px;padding:12px 16px;border-radius:10px;border:1px solid var(--claude-border);background:var(--claude-surface);margin-bottom:8px;">
                    <div>
                        <span style="font-size:1.1rem;font-weight:700;">{name}</span>
                        <span style="color:var(--claude-text-2);margin-left:8px;">{code}.TW</span>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:{up_color}">{close:,.0f}</div>
                        <div style="font-size:0.82rem;font-weight:600;color:{up_color}">{change:+,.0f} ({pct:+.2f}%)</div>
                    </div>
                    <div style="font-size:0.8rem;color:var(--claude-text-2);">
                        開 {open_price:,.0f} ｜ 高 {high:,.0f} ｜ 低 {low:,.0f}
                    </div>
                    <div style="font-size:0.8rem;color:var(--claude-text-2);">
                        昨收 {prev_close:,.0f} ｜ 振幅 {amplitude:.2f}%
                    </div>
                    <div style="font-size:0.8rem;color:var(--claude-text-2);">
                        成交量 {volume:,} 張
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            # Bug 4 修復: yf.T() → yf.Ticker(), NVDA 不要加 .US
            ticker = yf.Ticker(code if "." in code else code)
            data = ticker.history(period="5d")
            if not data.empty:
                close = float(data["Close"].iloc[-1])
                prev = float(data["Close"].iloc[-2]) if len(data) > 1 else close
                change = close - prev
                pct = _safe_div(change, prev)
                up_color = "var(--up-color)" if change >= 0 else "var(--down-color)"  # 台股紅漲 / 美股由主題決定

                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:20px;padding:12px 16px;border-radius:10px;border:1px solid var(--claude-border);background:var(--claude-surface);margin-bottom:8px;">
                    <div>
                        <span style="font-size:1.1rem;font-weight:700;">{name or code}</span>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.4rem;font-weight:800;color:{up_color}">${close:.2f}</div>
                        <div style="font-size:0.82rem;font-weight:600;color:{up_color}">${change:+.2f} ({pct:+.2f}%)</div>
                    </div>
                    <div style="font-size:0.8rem;color:var(--claude-text-2);">
                        美股資料（功能受限）
                    </div>
                </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        main_logger.warning(f"個股表頭查詢失敗 ({code}): {e}")
        st.warning(f"即時報價查詢失敗: {e}")

    return code, name, is_tw


def _safe_div(a, b, decimals=2):
    try:
        if b == 0 or pd.isna(b):
            return None
        return round(float(a) / float(b) * 100, decimals)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


# ──────────────────────────────────────────────
# 分頁 1：📈 技術
# ──────────────────────────────────────────────

def render_technical_tab(code: str, is_tw: bool):
    """技術分析分頁"""
    if not is_tw:
        st.info("個股全景的技術分析功能目前僅支援台股（純數字代號）。美股請至【技術分析】分頁查詢。")
        return

    # 日期範圍
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    col_start, col_end, col_fetch = st.columns([2, 2, 1])
    with col_start:
        start = st.date_input("開始日期", start_date, key="sp_tech_start")
    with col_end:
        end = st.date_input("結束日期", end_date, key="sp_tech_end")
    with col_fetch:
        fetch_btn = st.button("📈 載入 K 線", use_container_width=True, type="primary", key="sp_kbar_btn")

    if not fetch_btn:
        st.caption("📌 點擊載入 K 線圖與技術指標")
        return

    with st.spinner("正在載入 K 線數據..."):
        try:
            df = qw.query_kbars(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        except Exception as e:
            main_logger.warning(f"個股 K 線查詢失敗 ({code}): {e}")
            st.error(f"K 線數據查詢失敗: {e}")
            return

    if df.empty:
        st.warning("無 K 線數據")
        return

    # 導入技術分析模組
    try:
        from technical_analysis import plot_kbar_with_indicators, quick_chart
    except ImportError:
        st.error("技術分析模組載入失敗")
        return

    st.plotly_chart(quick_chart(code, df), use_container_width=True, key=f"sp_chart_{code}")

    # 區間統計
    if "收盤" in df.columns:
        period_return = _safe_div(df.iloc[-1]["收盤"] - df.iloc[0]["收盤"], df.iloc[0]["收盤"])
        high = df["收盤"].max() if "收盤" in df.columns else 0
        low = df["收盤"].min() if "收盤" in df.columns else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("區間漲跌幅", f"{period_return:+.2f}%" if period_return is not None else "-")
        c2.metric("區間高點", f"{high:,.0f}" if high else "-")
        c3.metric("區間低點", f"{low:,.0f}" if low else "-")


# ──────────────────────────────────────────────
# 分頁 2：📊 籌碼
# ──────────────────────────────────────────────

def render_chips_tab(code: str):
    """籌碼面分頁：三大法人 + 融資券 + 外資持股 + 當沖"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    # Phase I.2: 籌碼摘要磚（連買天數 + 累計）
    import chip_analysis as chip_mod
    summary = chip_mod.get_individual_chip_summary(code)
    if "error" not in summary or summary.get("error") == "error":
        st.markdown("#### 📋 籌碼摘要")
        if "error" in summary and summary["error"] != "error":
            st.info(summary["error"])
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("外資連買", f'{summary.get("外資連買", 0)} 天', delta_color="off")
            c2.metric("外資累計", f'{summary.get("外資累計", 0):,.0f} 張', delta_color="off")
            c3.metric("投信連買", f'{summary.get("投信連買", 0)} 天', delta_color="off")
            c4.metric("投信累計", f'{summary.get("投信累計", 0):,.0f} 張', delta_color="off")
        st.divider()

    col_start, col_end = st.columns(2)
    with col_start:
        start = st.date_input("開始日期", start_date, key="sp_chips_start")
    with col_end:
        end = st.date_input("結束日期", end_date, key="sp_chips_end")

    # ── 區塊 1：三大法人 ──
    st.markdown("#### 🏛️ 三大法人買賣超")
    try:
        inst_df = qw.query_institutional_summary(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not inst_df.empty:
            st.dataframe(inst_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"法人查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")

    # ── 區塊 2：融資融券 ──
    st.markdown("#### 📊 融資融券餘額")
    try:
        margin_df = qw.query_margin_short(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not margin_df.empty:
            st.dataframe(margin_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"融資券查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")

    # ── 區塊 3：外資持股 ──
    st.markdown("#### 🌏 外資持股比例")
    try:
        share_df = qw.query_day_trading_volume(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")) if False else pd.DataFrame()
        # 正確函式是 query_foreign_shareholding
        share_df = qw.query_foreign_shareholding(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not share_df.empty:
            st.dataframe(share_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"外資持股查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")

    # ── 區塊 4：當沖 ──
    st.markdown("#### 🔄 當沖交易量")
    try:
        dt_df = qw.query_day_trading_volume(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not dt_df.empty:
            st.dataframe(dt_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"當沖查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")


# ──────────────────────────────────────────────
# 分頁 3：💰 基本面
# ──────────────────────────────────────────────

def render_fundamentals_tab(code: str):
    """基本面分頁：月營收 + 財報 + 股利 + 公司資料"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    col_start, col_end = st.columns(2)
    with col_start:
        start = st.date_input("開始日期", start_date, key="sp_fund_start")
    with col_end:
        end = st.date_input("結束日期", end_date, key="sp_fund_end")

    # ── 月營收 ──
    st.markdown("#### 📊 月營收")
    try:
        rev_df = qw.query_month_revenue(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not rev_df.empty:
            st.dataframe(rev_df, use_container_width=True, hide_index=True, height=250)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"月營收查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")

    # ── 財報 ──
    st.markdown("#### 📋 綜合損益表")
    try:
        fs_df = qw.query_financial_statement(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not fs_df.empty:
            st.dataframe(fs_df, use_container_width=True, hide_index=True, height=250)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"財報查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")

    # ── 股利 ──
    st.markdown("#### 💰 股利政策")
    try:
        div_df = qw.query_dividend(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not div_df.empty:
            st.dataframe(div_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"股利查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")

    # ── PE 河流圖 ──
    st.markdown("#### 📈 PE 河流圖（歷史估值帶）")
    try:
        from valuation_chart import plot_pe_river
        pe_fig = plot_pe_river(code, years=3)
        st.plotly_chart(pe_fig, use_container_width=True, key=f"sp_pe_river_{code}")
    except Exception as e:
        main_logger.warning(f"PE 河流圖失敗 ({code}): {e}")
        st.caption("PE 河流圖資料不可用")

    # ── 同業比較 ──
    st.markdown("#### 🏢 同業估值比較")
    try:
        from valuation_chart import plot_peer_comparison
        # 找同產業（用 sector_map 簡易版：硬編碼半導體同業）
        peer_codes = []
        try:
            from sector_map import get_sector_map
            sector_df = get_sector_map()
            if not sector_df.empty:
                my_sector = sector_df[sector_df["公司代號"] == code]["產業別代碼"].values
                if len(my_sector) > 0:
                    peers = sector_df[sector_df["產業別代碼"] == my_sector[0]]["公司代號"].head(5).tolist()
                    if peers:
                        peer_codes = [c for c in peers if c != code][:4]
                        peer_codes.insert(0, code)
        except Exception:
            # Fallback: 硬編碼半導體同業
            if code in ("2330",):
                peer_codes = ["2330", "2454", "2303", "3037", "6507"]
            elif code in ("2454",):
                peer_codes = ["2454", "2330", "2303", "3037", "6507"]
            else:
                peer_codes = [code]

        if len(peer_codes) > 1:
            peer_fig = plot_peer_comparison(peer_codes)
            st.plotly_chart(peer_fig, use_container_width=True, key=f"sp_peer_{code}")
        else:
            st.caption("同業比較資料不足")
    except Exception as e:
        main_logger.warning(f"同業比較失敗 ({code}): {e}")
        st.caption("同業比較資料不可用")

    # ── 公司資料 ──
    st.markdown("#### 🏢 公司基本資料")
    try:
        comp_df = qw.query_twse_company(code)
        if not comp_df.empty:
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
        else:
            st.caption("無數據")
    except Exception as e:
        main_logger.warning(f"公司資料查詢失敗 ({code}): {e}")
        st.caption("查詢失敗")


# ──────────────────────────────────────────────
# 分頁 4：🏛️ 五檔大單
# ──────────────────────────────────────────────

def render_five_level_tab(code: str, is_tw: bool):
    """五檔報價盤 + 大單分析"""
    if not is_tw:
        st.info("五檔大單功能僅支援台股（Shioaji 券商 API）。")
        return

    today = datetime.now().strftime("%Y%m%d")
    col_code, col_date, col_go = st.columns([2, 2, 1])
    with col_code:
        code_input = st.text_input("代號", code, key="sp_5level_code")
    with col_date:
        date_input = st.date_input("日期", datetime.now(), key="sp_5level_date")
    with col_go:
        go_btn = st.button("🔍 查詢", use_container_width=True, type="primary", key="sp_five_btn")

    if not go_btn:
        st.caption("💡 選擇日期與代號查詢五檔與大單")
        return

    date_str = date_input.strftime("%Y%m%d")

    # 五檔
    st.markdown("#### 🏛️ 五檔報價")
    try:
        from ui_components import render_shioaji_snapshot
        snap = qw.query_shioaji_snapshot([code_input or code])
        if not snap.empty:
            render_shioaji_snapshot(snap)
        else:
            st.caption("無即時報價（可能非交易日或無 Shioaji 金鑰）")
    except Exception as e:
        main_logger.warning(f"五檔查詢失敗: {e}")
        st.caption("五檔資料暫不可用（需 Shioaji API 金鑰）")

    # 大單
    st.markdown("#### 🔍 大單分析")
    with st.expander("進階設定", expanded=False):
        vol_thresh = st.number_input("大單成交量門檻", value=1000, key="sp_big_vol", help="張數")
        amt_thresh = st.number_input("大單金額門檻", value=100000, key="sp_big_amt", help="元")

    try:
        from ui_components import render_shioaji_big_orders
        big_orders = qw.analyze_shioaji_big_orders(
            code_input or code, date_str, vol_thresh, amt_thresh
        )
        if big_orders and "summary" in big_orders:
            render_shioaji_big_orders(big_orders)
        else:
            st.caption("無大單數據")
    except Exception as e:
        main_logger.warning(f"大單分析失敗: {e}")
        st.caption("大單分析暫不可用（需 Shioaji 金鑰）")


# ──────────────────────────────────────────────
# 分頁 5：📰 新聞 AI
# ──────────────────────────────────────────────

def render_news_ai_tab(code: str, is_tw: bool):
    """個股新聞 + AI 解讀"""
    col_code, col_btn = st.columns([3, 1])
    with col_code:
        code_input = st.text_input("代號/名稱", code, key="sp_news_code")
    with col_btn:
        do_fetch = st.button("📰 查詢新聞", use_container_width=True, type="primary", key="sp_news_btn")

    if do_fetch:
        # 新聞
        st.markdown("#### 📰 相關新聞")
        try:
            news_df = qw.query_stock_news(code_input or code)
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
            st.caption("新聞查詢失敗")

        # AI 解讀
        st.markdown("#### 🤖 AI 個股解讀")
        ai_key = f"stock_ai_{code_input or code}"
        if "ai_btn_clicked" not in st.session_state:
            st.session_state.ai_btn_clicked = False

        if st.button("🤖 AI 個股健檢", key=f"sp_ai_btn_{code_input or code}", use_container_width=True, type="primary"):
            st.session_state.ai_btn_clicked = True
            st.rerun()

        if st.session_state.get(ai_key) is None and st.session_state.get("ai_btn_clicked"):
            with st.spinner("AI 正在分析中..."):
                try:
                    if is_tw:
                        # 台股走 deepseek_engine chat
                        from deepseek_engine import generate_tw_stock_report
                        report = generate_tw_stock_report(code_input or code)
                    else:
                        # 美股走 generate_us_stock_report
                        from deepseek_engine import generate_us_stock_report
                        report = generate_us_stock_report(code_input or code)
                    st.session_state[ai_key] = report
                except Exception as e:
                    main_logger.warning(f"AI 分析失敗: {e}")
                    st.error(f"AI 分析失敗: {e}")

        if st.session_state.get(ai_key):
            report = st.session_state[ai_key]
            st.markdown(report)
            st.download_button(
                "📥 下載 Markdown",
                data=report,
                file_name=f"stock_ai_{code_input or code}_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True,
                key="sp_news_dl"
            )
            # Phase L.1: 加上當日盤勢對照（個股 vs 大盤相對強弱）
            st.markdown("---")
            try:
                from deepseek_engine import generate_market_briefing
                brief_key = f"ai_brief_{date.today().isoformat()}"
                if brief_key not in st.session_state:
                    # 快速組裝 context
                    all_df = qw.query_twse_daily_all()
                    context = {
                        "index": {"name": "加權指數", "value": 0, "change": 0, "pct": 0},
                        "breadth": {"up": 0, "down": 0, "volume": 0},
                        "institutions": {"foreign": 0, "trust": 0, "dealer": 0},
                        "top_sectors": [], "top_up": [], "disposition_count": 0,
                    }
                    if not all_df.empty and "漲跌幅%" in all_df.columns:
                        up_c = int((all_df["漲跌幅%"] > 0).sum()) if pd.api.types.is_numeric_dtype(all_df["漲跌幅%"]) else 0
                        down_c = int((all_df["漲跌幅%"] < 0).sum()) if pd.api.types.is_numeric_dtype(all_df["漲跌幅%"]) else 0
                        context["breadth"] = {"up": up_c, "down": down_c, "volume": float(all_df["成交金額"].sum()) if "成交金額" in all_df.columns else 0}
                    st.session_state[brief_key] = generate_market_briefing(context)
                brief = st.session_state[brief_key]
                if brief and not brief.startswith("⚠️") and not brief.startswith("❌"):
                    st.info(f"**今日大盤參考：** {brief[:200]}...")
            except Exception:
                pass


# ──────────────────────────────────────────────
# 主渲染
# ──────────────────────────────────────────────

def render_stock_page():
    """個股全景主入口"""
    code, name, is_tw = render_stock_header()
    if not code:
        return

    tab_tech, tab_chips, tab_fund, tab_five, tab_news = st.tabs([
        "📈 技術", "📊 籌碼", "💰 基本面", "🏛️ 五檔大單", "📰 新聞/AI"
    ])

    with tab_tech:
        render_technical_tab(code, is_tw)

    with tab_chips:
        render_chips_tab(code)

    with tab_fund:
        render_fundamentals_tab(code)

    with tab_five:
        render_five_level_tab(code, is_tw)

    with tab_news:
        render_news_ai_tab(code, is_tw)
