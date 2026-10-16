"""
側邊欄導航、書籤/歷史、設定面板、輸入元件（2026-07-07 從 ui_components.py 拆出）
"""

import streamlit as st
from datetime import date, timedelta
from typing import Dict, Any, Optional


def render_sidebar_menu(available_tabs: list) -> str:
    """渲染側邊欄選單 — 分組折疊設計，返回選中的 Tab"""
    with st.sidebar:
        st.markdown("## 📋 導航")

        # 定義分組
        groups = {
            "📊 市場查詢": ["台股市場", "美股專區"],
            "🔍 選股分析": ["台股選股", "美股選股"],
            "📈 技術分析": ["技術分析"],
            "📅 日曆": ["台股日曆", "美股日曆"],
            "🛠️ 工具": ["工具"],
            "🤖 AI": ["AI 對話"],
        }

        selected_tab = None

        for group_name, tabs_in_group in groups.items():
            # 過濾出實際存在的 tabs
            existing_tabs = [t for t in tabs_in_group if t in available_tabs]
            if not existing_tabs:
                continue

            with st.expander(group_name, expanded=True):
                for tab in existing_tabs:
                    if st.button(tab, key=f"sidebar_{tab}", use_container_width=True):
                        selected_tab = tab

        # 如果有其他不在分組中的 tabs
        all_grouped = [t for tabs in groups.values() for t in tabs]
        ungrouped = [t for t in available_tabs if t not in all_grouped]
        if ungrouped:
            with st.expander("其他", expanded=True):
                for tab in ungrouped:
                    if st.button(tab, key=f"sidebar_{tab}", use_container_width=True):
                        selected_tab = tab

        return selected_tab or available_tabs[0] if available_tabs else "台股市場"

def render_search_box() -> str:
    """渲染智能搜尋框"""
    with st.sidebar:
        st.markdown("---")
        search = st.text_input("🔍 智能搜尋", placeholder="例：查2330財報")
        return search

def render_bookmarks_section(bookmarks: list) -> Optional[Dict[str, Any]]:
    """渲染書籤區域"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⭐ 釘選功能")
        if not bookmarks:
            st.caption("暫無書籤")
            return None

        selected_bookmark = st.selectbox(
            "選擇書籤",
            options=bookmarks,
            format_func=lambda x: x.get("name", "未命名"),
            label_visibility="collapsed"
        )
        return selected_bookmark

def render_history_section(history: list) -> Optional[Dict[str, Any]]:
    """渲染查詢歷史區域 — 時間線樣式"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📋 最近查詢")
        if not history:
            st.caption("暫無歷史")
            return None

        # 顯示最近 10 筆歷史
        recent_history = history[:10]

        for idx, item in enumerate(recent_history):
            tab = item.get('tab', '')
            timestamp = item.get('timestamp', '')
            title = item.get('title', '')

            # 格式化時間
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%m/%d %H:%M')
                except:
                    time_str = timestamp[:16]
            else:
                time_str = ''

            # 時間線項目
            with st.container():
                col_time, col_content = st.columns([1, 4])
                with col_time:
                    st.caption(f"🕒 {time_str}")
                with col_content:
                    st.caption(f"**{tab}** — {title[:30]}{'...' if len(title) > 30 else ''}")

        # 選擇歷史
        selected_history = st.selectbox(
            "選擇歷史記錄",
            options=recent_history,
            format_func=lambda x: f"{x.get('tab', '')} - {x.get('title', '')[:20]}",
            key="history_select",
            label_visibility="collapsed"
        )
        return selected_history

def render_settings_panel(config: Dict[str, Any], in_sidebar: bool = True) -> Dict[str, Any]:
    """渲染設定面板"""
    container = st.sidebar if in_sidebar else st.container()

    with container:
        if in_sidebar:
            st.markdown("---")
            st.markdown("### ⚙️ 設定")

        with st.expander("🔑 API 金鑰", expanded=not in_sidebar):
            st.markdown("**券商提供 Shioaji**")
            api_key = st.text_input("API Key", value=config.get("api_key", ""), type="password", key="api_key_input")
            secret_key = st.text_input("Secret Key", value=config.get("secret_key", ""), type="password", key="secret_key_input")

            st.markdown("**FinMind**")
            finmind_token = st.text_input("FinMind Token", value=config.get("finmind_token", ""), type="password", key="finmind_token_input")

            st.markdown("**Notion**")
            notion_token = st.text_input("Notion Token", value=config.get("notion_token", ""), type="password", key="notion_token_input", placeholder="secret_xxx...")
            notion_db_id = st.text_input("Notion Database ID", value=config.get("notion_database_id", ""), key="notion_db_input", placeholder="32位元ID")

            st.markdown("**Agnes AI**")
            ai_api_key = st.text_input("Agnes AI API Key", value=config.get("ai_api_key", ""), type="password", key="ai_api_key_input", placeholder="sk-...")
            ai_base_url = st.text_input("AI Base URL", value=config.get("ai_base_url", "https://apihub.agnes-ai.com/v1"), key="ai_base_url_input", placeholder="https://apihub.agnes-ai.com/v1")

            # 初始化可用模型列表
            from ai_engine import DeepSeekEngine

            # 使用 session_state 暫存模型列表，避免每次 UI 刷新都重新打 API
            if "available_ai_models" not in st.session_state:
                st.session_state.available_ai_models = []
                # 如果已有 Key，嘗試初始化讀取一次
                if ai_api_key:
                    try:
                        st.session_state.available_ai_models = DeepSeekEngine.list_available_models(ai_api_key)
                    except:
                        pass

            col_fetch, col_info = st.columns([1, 2])
            with col_fetch:
                if st.button("🔍 獲取模型列表", key="fetch_ai_models"):
                    if ai_api_key:
                        with st.spinner("獲取中..."):
                            st.session_state.available_ai_models = DeepSeekEngine.list_available_models(ai_api_key)
                            if st.session_state.available_ai_models:
                                st.success("已更新清單")
                            else:
                                st.error("獲取失敗")
                    else:
                        st.warning("請先輸入 Key")

            # 準備選單內容
            current_model = config.get("ai_model", "")
            models_list = st.session_state.available_ai_models
            if not models_list:
                models_list = ["(點擊上方按鈕獲取)"]
                model_index = 0
            else:
                if current_model in models_list:
                    model_index = models_list.index(current_model)
                else:
                    model_index = 0

            ai_model = st.selectbox("AI 模型選擇", models_list, index=model_index, key="ai_model_select")

            # 已有模型時預設開啟手動輸入（避免下拉清單空白時清掉設定）
            has_existing_model = bool(current_model and current_model != "(點擊上方按鈕獲取)")
            use_custom_model = st.checkbox("手動輸入模型名稱", value=has_existing_model, key="use_custom_ai")
            if use_custom_model:
                custom_model_name = st.text_input("輸入自訂模型代號", value=current_model, placeholder="例：agnes-2.0-flash")
                final_model = custom_model_name
            else:
                final_model = ai_model if ai_model != "(點擊上方按鈕獲取)" else current_model

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 保存", key="save_keys"):
                    config["api_key"] = api_key
                    config["secret_key"] = secret_key
                    config["finmind_token"] = finmind_token
                    config["notion_token"] = notion_token
                    config["notion_database_id"] = notion_db_id
                    config["ai_api_key"] = ai_api_key
                    config["ai_base_url"] = ai_base_url
                    config["ai_model"] = final_model if final_model != "(點擊上方按鈕獲取)" else ""
                    from config import save_config
                    save_config(config)
                    st.success(f"✅ 設定已保存：{config['ai_model']}")
            with col2:
                if st.button("🔄 重置", key="reset_keys"):
                    from config import DEFAULT_CONFIG, save_config
                    config = DEFAULT_CONFIG.copy()
                    save_config(config)
                    st.success("✅ 已重置為預設值")

        with st.expander("⚙️ 偏好設置"):
            export_format = st.selectbox("導出格式", ["csv", "excel"], index=min(["csv", "excel"].index(config.get("export_format", "csv")) if config.get("export_format", "csv") in ["csv", "excel"] else 0, 1), key="export_format_select")
            simulation_mode = st.checkbox("模擬模式", value=config.get("simulation_mode", True), key="simulation_mode_check")

            if st.button("💾 保存偏好", key="save_prefs"):
                config["export_format"] = export_format
                config["simulation_mode"] = simulation_mode
                from config import save_config
                save_config(config)
                st.success("✅ 偏好已保存")

        with st.expander("📋 歷史管理"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 查看歷史", key="view_history"):
                    from config import load_history
                    history = load_history()
                    st.metric("查詢總數", len(history))
            with col2:
                if st.button("🗑️ 清空歷史", key="clear_history"):
                    from config import clear_history
                    clear_history()
                    st.success("✅ 歷史已清空")
                    st.rerun()

        with st.expander("📊 自選監控名單", expanded=not in_sidebar):
            from config import load_watchlist, save_watchlist
            watchlist = load_watchlist()

            snap_codes = st.text_input(
                "即時監控代號 (Snapshots)",
                value=",".join(watchlist.get("snapshots", [])),
                placeholder="例：2330,0050,2454",
                help="儀表板上顯示的即時監控名單，用逗號分隔"
            )

            kbar_codes = st.text_input(
                "預載 K線代號 (K-bars)",
                value=",".join(watchlist.get("kbars", [])),
                placeholder="例：2330,0050",
                help="啟動時會預先加載 30 天數據的代號"
            )

            if st.button("💾 保存監控名單", key="save_watchlist"):
                new_snap = [c.strip() for c in snap_codes.split(",") if c.strip()]
                new_kbar = [c.strip() for c in kbar_codes.split(",") if c.strip()]
                save_watchlist({"snapshots": new_snap, "kbars": new_kbar})
                st.success("✅ 監控名單已更新 (重啟 APP 後生效)")

    return config

def date_input_section(label: str = "選擇日期範圍", default_days: int = 30,
                        key_prefix: str = "") -> tuple:
    """日期輸入區域 — 返回 (start_date, end_date)

    key_prefix: 傳入唯一前綴以隔離不同 Tab 的 session state，
                避免切換 Tab 時日期互相覆蓋（例如 "us_", "fm_", "ts_"）
    """
    kp = key_prefix or ""
    end_key = f"{kp}date_end" if kp else None

    # ── 自動修正過期的結束日期 ──────────────────────────────
    # Streamlit widget 值存在瀏覽器並在重連後送回伺服器，
    # 若使用者先前設定的結束日期超過 30 天以前，自動重設為今日
    if end_key and end_key in st.session_state:
        _stored_end = st.session_state[end_key]
        if isinstance(_stored_end, date) and _stored_end < date.today() - timedelta(days=30):
            del st.session_state[end_key]   # 強制 widget 用 value= 預設值重新初始化

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "開始日期",
            value=date.today() - timedelta(days=default_days),
            key=f"{kp}date_start" if kp else None,
        )
    with col2:
        end_date = st.date_input(
            "結束日期",
            value=date.today(),
            key=end_key,
        )

    # 若結束日期超過 7 天前，顯示警告提示（isinstance 保護：mock/None 不進入比較）
    if isinstance(end_date, date) and end_date < date.today() - timedelta(days=7):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.warning(f"⚠️ 結束日期 {end_date} 超過 7 天前，資料可能不是最新。")
        with c2:
            if st.button("📅 設為今日", key=f"{kp}reset_end", use_container_width=True):
                if end_key:
                    st.session_state[end_key] = date.today()
                st.rerun()

    return start_date, end_date

def code_input_section(label: str = "輸入股票代號", single: bool = True) -> str | list:
    """股票代號輸入區域（支援中文名稱輸入，如：台積電、蘋果、NVIDIA）"""
    try:
        from stock_lookup import resolve_code, resolve_codes, get_name_hint
        _lookup_ok = True
    except ImportError:
        _lookup_ok = False

    if single:
        raw = st.text_input(label, placeholder="例：2330、台積電、蘋果、AAPL").strip()
        if raw and _lookup_ok:
            resolved = resolve_code(raw)
            hint = get_name_hint(raw)
            if hint:
                st.caption(f"✅ 已解析：{hint}")
            return resolved
        return raw
    else:
        codes_str = st.text_input(label, placeholder="例：2330,台積電,蘋果，用逗號分隔")
        if not codes_str:
            return []
        if _lookup_ok:
            parts = [p.strip() for p in codes_str.split(",") if p.strip()]
            resolved_list = [resolve_code(p) for p in parts]
            hints = []
            for raw_p, res_p in zip(parts, resolved_list):
                if res_p.upper() != raw_p.upper() and res_p != raw_p:
                    hints.append(f"{raw_p}→{res_p}")
            if hints:
                st.caption("✅ 已解析：" + "，".join(hints))
            return resolved_list
        return [c.strip() for c in codes_str.split(",") if c.strip()]

def us_code_input_section(label: str = "輸入美股代號或名稱", single: bool = True) -> str | list:
    """美股代號輸入區域（支援中文名稱輸入，如：蘋果、微軟）"""
    try:
        from stock_lookup import resolve_us_stock, get_us_name_hint
        _lookup_ok = True
    except ImportError:
        _lookup_ok = False

    if single:
        raw = st.text_input(label, placeholder="例：AAPL、蘋果、微軟、NVDA").strip()
        if raw and _lookup_ok:
            resolved = resolve_us_stock(raw)
            hint = get_us_name_hint(raw)
            if hint:
                st.caption(f"🤖 AI 解析：{hint}")
            return resolved
        return raw
    else:
        codes_str = st.text_input(label, placeholder="例：AAPL,微軟,TSLA，用逗號分隔")
        if not codes_str:
            return []
        if _lookup_ok:
            parts = [p.strip() for p in codes_str.split(",") if p.strip()]
            resolved_list = [resolve_us_stock(p) for p in parts]
            hints = []
            for raw_p, res_p in zip(parts, resolved_list):
                if res_p.upper() != raw_p.upper() and res_p != raw_p:
                    hints.append(f"{raw_p}→{res_p}")
            if hints:
                st.caption("🤖 AI 解析：" + "，".join(hints))
            return resolved_list
        return [c.strip() for c in codes_str.split(",") if c.strip()]
