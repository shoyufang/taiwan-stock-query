"""
共用 UI 組件與輔助渲染工具
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from ui_components import display_result


def _qbtn_grid(options: list, state_key: str, n_cols: int = 4) -> str:
    """按鈕選單格：顯示 n_cols 欄的選項按鈕，當前選中顯示 primary 樣式，回傳選中項目。"""
    if state_key not in st.session_state or st.session_state[state_key] not in options:
        st.session_state[state_key] = options[0]
    current = st.session_state[state_key]
    cols = st.columns(n_cols)
    for i, opt in enumerate(options):
        with cols[i % n_cols]:
            if st.button(opt, key=f"{state_key}_{i}", use_container_width=True,
                         type="primary" if current == opt else "secondary"):
                st.session_state[state_key] = opt
                current = opt
    st.divider()
    return current


def _render_batch_results(state_key: str, label_fn=None):
    """批次查詢結果統一渲染 helper。

    - 工具列：全部展開／全部收合／清除結果／全部匯出 Excel
    - 第一項預設展開，其餘收合（避免頁面過長）
    - label_fn(item) -> str 可自訂 expander 標題
    """
    stored = st.session_state.get(state_key)
    if not stored:
        return

    # 統一格式：list[(item, result)]
    extra = None
    if isinstance(stored, tuple) and len(stored) == 2 and isinstance(stored[0], list):
        results, extra = stored
    else:
        results = stored
    if not results:
        return

    expand_key = f"_expand_state_{state_key}"

    # ── 工具列 ──────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        if st.button("⬇️ 展開全部", key=f"_btn_expand_{state_key}", use_container_width=True):
            st.session_state[expand_key] = True
            st.rerun()
    with c2:
        if st.button("⬆️ 收合全部", key=f"_btn_collapse_{state_key}", use_container_width=True):
            st.session_state[expand_key] = False
            st.rerun()
    with c3:
        if st.button("🗑️ 清除結果", key=f"_btn_clear_{state_key}", use_container_width=True):
            del st.session_state[state_key]
            st.session_state.pop(expand_key, None)
            st.rerun()
    with c4:
        # 全部導出 Excel（多 sheet）
        valid = []
        for it, r in results:
            if isinstance(r, pd.DataFrame):
                if not r.empty:
                    valid.append((it, r))
            elif isinstance(r, dict):
                # 處理美股特規結果字典與其他可能的分級數據
                rtype = r.get("type")
                rdata = r.get("data")
                if rtype == "us_profile" and isinstance(rdata, dict):
                    df_profile = pd.DataFrame(list(rdata.items()), columns=["欄位名稱", "內容"])
                    valid.append((f"{it}_基本資料", df_profile))
                elif rtype == "us_financials" and isinstance(rdata, dict):
                    name_map = {
                        "income_annual": "年度損益表",
                        "income_quarterly": "季度損益表",
                        "balance_annual": "年度資產負債表",
                        "balance_quarterly": "季度資產負債表",
                        "cashflow_annual": "年度現金流量表",
                        "cashflow_quarterly": "季度現金流量表"
                    }
                    for fk, fdf in rdata.items():
                        if isinstance(fdf, pd.DataFrame) and not fdf.empty:
                            fdf_with_index = fdf.copy()
                            idx_name = fdf_with_index.index.name or "財務項目"
                            fdf_with_index.reset_index(inplace=True)
                            if "index" in fdf_with_index.columns:
                                fdf_with_index.rename(columns={"index": idx_name}, inplace=True)
                            lbl = name_map.get(fk, fk)
                            valid.append((f"財報_{lbl}", fdf_with_index))
                elif rtype == "us_holders" and isinstance(rdata, dict):
                    for hk, hdf in rdata.items():
                        if isinstance(hdf, pd.DataFrame) and not hdf.empty:
                            lbl = "機構持股" if hk == "institutional" else "共同基金持股"
                            valid.append((f"股東_{lbl}", hdf))
                elif rtype == "us_analyst_info" and isinstance(rdata, dict):
                    df_analyst = pd.DataFrame(list(rdata.items()), columns=["評等指標", "數值"])
                    valid.append((f"{it}_分析師評等", df_analyst))
                elif rtype == "us_news" and isinstance(rdata, list):
                    news_list = []
                    for n in rdata:
                        news_list.append({
                            "標題": n.get("title", ""),
                            "媒體": n.get("publisher", ""),
                            "連結": n.get("link", ""),
                            "發布時間戳": n.get("providerPublishTime", 0)
                        })
                    if news_list:
                        df_news = pd.DataFrame(news_list)
                        valid.append((f"{it}_相關新聞", df_news))

        if valid:
            from io import BytesIO
            try:
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    used = set()
                    for name, dfx in valid:
                        sheet = (name[:28] or "Sheet")
                        # 確保 sheet 名唯一
                        base = sheet; i = 1
                        while sheet in used:
                            sheet = f"{base[:25]}_{i}"; i += 1
                        used.add(sheet)
                        
                        # 複製 DataFrame 並清除時區資訊，避免 openpyxl 導出失敗
                        df_clean = dfx.copy()
                        # 確保欄位名稱全部為字串，防止 openpyxl 因 DatetimeIndex 欄位而崩潰
                        df_clean.columns = [str(c) for c in df_clean.columns]
                        
                        for col in df_clean.columns:
                            try:
                                if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                                    if getattr(df_clean[col], "dt", None) is not None and df_clean[col].dt.tz is not None:
                                        df_clean[col] = df_clean[col].dt.tz_localize(None)
                                else:
                                    # 處理可能含有時區的 object 類型日期
                                    df_clean[col] = df_clean[col].apply(
                                        lambda val: val.tz_localize(None) if hasattr(val, "tz_localize") and getattr(val, "tz", None) is not None else val
                                    )
                            except Exception:
                                pass
                        df_clean.to_excel(writer, sheet_name=sheet, index=False)
                
                # 確保 local 範圍內使用正確的 datetime
                from datetime import datetime as dt_local
                ts = dt_local.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    "📥 全部匯出 Excel",
                    data=buf.getvalue(),
                    file_name=f"batch_{state_key}_{ts}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"_export_all_{state_key}",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"匯出失敗：{e}")
        else:
            st.button("📥 全部匯出 Excel", disabled=True, use_container_width=True,
                      key=f"_export_all_{state_key}",
                      help="目前沒有可匯出的表格結果")

    # ── 結果列表 ────────────────────────────────────────
    # extra 若為字串（股票代號），傳入 display_result 供 K線圖使用
    batch_code = extra if isinstance(extra, str) else ""
    expand_state = st.session_state.get(expand_key)
    for idx, (item, result) in enumerate(results):
        if expand_state is True:
            expanded = True
        elif expand_state is False:
            expanded = False
        else:
            expanded = (idx == 0)  # 預設只展開首項
        label = label_fn(item, extra) if label_fn else f"📋 {item}"
        with st.expander(label, expanded=expanded):
            display_result(result, item, enable_export=False, code=batch_code)


def _nav_btn(label: str, icon: str = ""):
    """渲染一個導航按鈕，當前選中顯示 primary 樣式"""
    current = st.session_state.selected_tab
    display = f"{icon} {label}".strip() if icon else label
    btn_type = "primary" if current == label else "secondary"
    if st.button(display, key=f"nav_{label}", use_container_width=True, type=btn_type):
        st.session_state.selected_tab = label
        st.rerun()
