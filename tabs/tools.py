"""
工具集合模組 — 提供 K 線、對比、資料匯出與書籤管理功能
"""

import streamlit as st
import pandas as pd
from datetime import date
from logging_config import main_logger
from ui_components import date_input_section, code_input_section
from config import add_bookmark, load_bookmarks, remove_bookmark
import query_wrapper as qw


def render_tools():
    """工具"""
    main_logger.info("渲染工具 Tab")
    st.subheader("🛠️ 工具集合")

    with st.expander("📈 K線圖工具"):
        code = code_input_section()
        start_date, end_date = date_input_section(key_prefix="tool_kbar_")
        if st.button("繪製 K線圖", key="tool_kbar_btn"):
            st.info("功能在 Phase 3 實現")

    with st.expander("🔄 對比工具"):
        st.markdown("並排對比多檔股票")

        compare_type = st.selectbox(
            "選擇對比方式",
            ["個股快照對比", "技術面對比", "基本面對比"],
            key="compare_type"
        )

        if compare_type == "個股快照對比":
            st.subheader("📊 個股快照對比")
            codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：2330,2412,3008", key="compare_snapshot_codes")
            use_async = st.checkbox("使用非同步並行查詢（更快）", value=True, key="compare_snapshot_async")

            if st.button("執行對比", key="compare_snapshot_btn"):
                codes = [c.strip() for c in codes_str.split(",") if c.strip()]
                if codes:
                    with st.spinner("查詢中..."):
                        try:
                            if use_async and len(codes) > 1:
                                # 非同步批量查詢
                                queries = [
                                    {"func": qw.query_snapshot, "args": ([code],), "name": code}
                                    for code in codes
                                ]
                                results_list = qw.batch_query_sync(queries)
                                results = [(codes[i], results_list[i]) for i in range(len(codes)) if not results_list[i].empty]
                            else:
                                # 同步查詢
                                results = []
                                for code in codes:
                                    result = qw.query_snapshot([code])
                                    if not result.empty:
                                        results.append((code, result))

                            if results:
                                st.subheader("📈 對比結果")
                                cols = st.columns(len(results))
                                for idx, (code, result) in enumerate(results):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        st.dataframe(result.head(5), use_container_width=True)
                            else:
                                st.warning("無可用結果")
                        except Exception as e:
                            st.error(f"對比失敗: {str(e)}")
                else:
                    st.warning("請輸入至少一個股票代號")

        elif compare_type == "技術面對比":
            st.subheader("📊 技術面對比")
            st.info("比較多檔股票的籌碼面數據（三大法人、融資融券等）")
            codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：2330,2412", key="compare_technical_codes")
            metric = st.selectbox("選擇比較指標", ["三大法人", "融資融券", "外資持股"], key="compare_metric")
            use_async = st.checkbox("使用非同步並行查詢（更快）", value=True, key="compare_technical_async")

            start_date, end_date = date_input_section(default_days=60, key_prefix="cmp_tech_")

            if st.button("執行對比", key="compare_technical_btn"):
                codes = [c.strip() for c in codes_str.split(",") if c.strip()]
                if codes:
                    with st.spinner("查詢中..."):
                        try:
                            st.markdown(f"**對比指標**: {metric}")

                            if use_async and len(codes) > 1:
                                # 非同步批量查詢
                                if metric == "三大法人":
                                    func = qw.query_institutional_investors
                                elif metric == "融資融券":
                                    func = qw.query_margin_short
                                else:
                                    func = qw.query_foreign_shareholding

                                queries = [
                                    {"func": func, "args": (code, start_date, end_date), "name": code}
                                    for code in codes
                                ]
                                results_list = qw.batch_query_sync(queries)

                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        result = results_list[idx]
                                        if not result.empty:
                                            st.dataframe(result.head(10), use_container_width=True)
                                        else:
                                            st.warning("無數據")
                            else:
                                # 同步查詢
                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        try:
                                            if metric == "三大法人":
                                                result = qw.query_institutional_investors(code, start_date, end_date)
                                            elif metric == "融資融券":
                                                result = qw.query_margin_short(code, start_date, end_date)
                                            else:  # 外資持股
                                                result = qw.query_foreign_shareholding(code, start_date, end_date)

                                            if not result.empty:
                                                st.dataframe(result.head(10), use_container_width=True)
                                            else:
                                                st.warning("無數據")
                                        except Exception as e:
                                            st.error(f"查詢失敗: {str(e)}")
                        except Exception as e:
                            st.error(f"對比失敗: {str(e)}")
                else:
                    st.warning("請輸入至少一個股票代號")

        elif compare_type == "基本面對比":
            st.subheader("📊 基本面對比")
            st.info("比較多檔股票的基本面數據（月營收、財報等）")
            codes_str = st.text_input("輸入股票代號（逗號分隔）", placeholder="例：2330,2412", key="compare_fundamental_codes")
            metric = st.selectbox("選擇比較指標", ["月營收", "財務報表"], key="compare_fundamental_metric")
            use_async = st.checkbox("使用非同步並行查詢（更快）", value=True, key="compare_fundamental_async")

            start_date, end_date = date_input_section(default_days=365, key_prefix="cmp_fund_")

            if st.button("執行對比", key="compare_fundamental_btn"):
                codes = [c.strip() for c in codes_str.split(",") if c.strip()]
                if codes:
                    with st.spinner("查詢中..."):
                        try:
                            st.markdown(f"**對比指標**: {metric}")

                            if use_async and len(codes) > 1:
                                # 非同步批量查詢
                                if metric == "月營收":
                                    func = qw.query_month_revenue
                                else:
                                    func = qw.query_financial_statement

                                queries = [
                                    {"func": func, "args": (code, start_date, end_date), "name": code}
                                    for code in codes
                                ]
                                results_list = qw.batch_query_sync(queries)

                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        result = results_list[idx]
                                        if not result.empty:
                                            st.dataframe(result.head(10), use_container_width=True)
                                        else:
                                            st.warning("無數據")
                            else:
                                # 同步查詢
                                cols = st.columns(len(codes))
                                for idx, code in enumerate(codes):
                                    with cols[idx]:
                                        st.markdown(f"### {code}")
                                        try:
                                            if metric == "月營收":
                                                result = qw.query_month_revenue(code, start_date, end_date)
                                            else:  # 財務報表
                                                result = qw.query_financial_statement(code, start_date, end_date)

                                            if not result.empty:
                                                st.dataframe(result.head(10), use_container_width=True)
                                            else:
                                                st.warning("無數據")
                                        except Exception as e:
                                            st.error(f"查詢失敗: {str(e)}")
                        except Exception as e:
                            st.error(f"對比失敗: {str(e)}")
                else:
                    st.warning("請輸入至少一個股票代號")

    with st.expander("📊 資料匯出"):
        st.markdown("將查詢結果匯出或儲存到 Notion")
        df_to_export = st.session_state.get("current_result")
        if df_to_export is not None and not df_to_export.empty:
            from utils import export_csv, export_excel, export_to_notion
            export_title = st.text_input("匯出標題", value="查詢結果", key="export_title")
            col_csv, col_excel, col_notion = st.columns(3)

            with col_csv:
                csv_bytes = export_csv(df_to_export)
                st.download_button("⬇️ 下載 CSV", csv_bytes, file_name=f"{export_title}.csv", mime="text/csv", key="dl_csv")

            with col_excel:
                excel_bytes = export_excel(df_to_export)
                st.download_button("⬇️ 下載 Excel", excel_bytes, file_name=f"{export_title}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_excel")

            with col_notion:
                if st.button("📝 儲存到 Notion", key="save_notion"):
                    cfg = st.session_state.get("config", {})
                    token = cfg.get("notion_token", "")
                    db_id = cfg.get("notion_database_id", "")
                    if not token or not db_id:
                        st.warning("請先在設定中填入 Notion Token 與 Database ID")
                    else:
                        with st.spinner("儲存到 Notion..."):
                            ok, msg = export_to_notion(df_to_export, export_title, token, db_id)
                            if ok:
                                st.success(f"✅ 已儲存到 Notion")
                                if msg:
                                    st.markdown(f"[開啟頁面]({msg})", unsafe_allow_html=False)
                            else:
                                st.error(f"❌ 儲存失敗：{msg}")
        else:
            st.info("請先執行查詢，再進行匯出")

    with st.expander("🔖 書籤管理"):
        st.markdown("管理常用查詢")
        bookmark_name = st.text_input("書籤名稱", key="bookmark_input")
        if st.button("新增書籤", key="add_bookmark_btn"):
            if bookmark_name and st.session_state.current_result is not None:
                success = add_bookmark(
                    bookmark_name,
                    st.session_state.selected_tab,
                    {"type": "custom"}
                )
                if success:
                    st.session_state.bookmarks = load_bookmarks()
                    st.success(f"✅ 書籤 '{bookmark_name}' 已保存")
                    st.rerun()
                else:
                    st.error("❌ 書籤名稱已存在")
            else:
                st.warning("⚠️ 請先執行查詢並輸入書籤名稱")

        bookmarks = st.session_state.get("bookmarks", [])
        if bookmarks:
            st.markdown("**已有書籤：**")
            for bm in bookmarks:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.caption(f"⭐ {bm['name']}")
                with col2:
                    if st.button("🗑️", key=f"delete_{bm['name']}"):
                        remove_bookmark(bm['name'])
                        st.session_state.bookmarks = load_bookmarks()
                        st.rerun()
