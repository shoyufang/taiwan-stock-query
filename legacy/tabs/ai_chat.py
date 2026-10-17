"""
Agnes AI 投資助理 Chat UI 模組
"""

import streamlit as st
from logging_config import main_logger
from ai_engine import get_deepseek_engine
from config import add_history


def render_deepseek_chat():
    """Agnes AI 智能對話 — Chat UI"""
    main_logger.info("渲染 Agnes AI Chat Tab")

    engine = get_deepseek_engine()
    if not engine:
        st.markdown("## 🤖 Agnes AI")
        st.warning("請先在左側欄 **⚙️ 系統設定** 中填入 Agnes AI API Key 與模型名稱，儲存後重新整理頁面。")
        with st.expander("如何取得 API Key？"):
            st.markdown(
                "1. 前往 [Agnes AI Platform](https://apihub.agnes-ai.com)\n"
                "2. 建立 API Key（免費註冊）\n"
                "3. 複製後貼入左側欄 ⚙️ 設定，模型選 `agnes-2.0-flash`\n"
                "4. 按儲存後重新整理"
            )
        return

    history = st.session_state.get("deepseek_chat_history", [])

    # ── 空白狀態：置中歡迎畫面 ─────────────────────────────
    if not history:
        st.markdown(
            """
            <div style="
                display:flex; flex-direction:column; align-items:center;
                justify-content:center; min-height:55vh;
                color:#aaa; gap:12px;
            ">
                <div style="font-size:3rem">🤖</div>
                <div style="font-size:1.4rem; font-weight:600; color:#ddd;">Agnes AI 智能助手</div>
                <div style="font-size:0.95rem; text-align:center; max-width:480px; line-height:1.8;">
                    可自動調用台股、港美股、FinMind、匯率等本地工具<br/>
                    並搜尋網路即時資訊。直接用中文提問。
                </div>
                <div style="
                    margin-top:8px; font-size:0.85rem; color:#666;
                    border:1px solid #333; border-radius:8px;
                    padding:10px 20px; text-align:center; line-height:2;
                ">
                    台積電最新法人買賣超？<br/>
                    今日美股/港股開盤狀況？<br/>
                    USD 匯率近一個月走勢？
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # ── 清除按鈕（右對齊，只在有對話時顯示）─────────────
        st.markdown(
            "<div style='display:flex; justify-content:flex-end; margin-bottom:4px;'>",
            unsafe_allow_html=True,
        )
        if st.button("🗑️ 清除對話", key="clear_deepseek_chat"):
            st.session_state.deepseek_chat_history = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 對話泡泡 ─────────────────────────────────────────
        for msg in history:
            avatar = "🧑" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # ── 輸入框（Streamlit 原生，自動固定底部）────────────────
    user_input = st.chat_input("輸入問題，按 Enter 或點傳送鍵…", key="deepseek_input")

    if user_input:
        if "deepseek_chat_history" not in st.session_state:
            st.session_state.deepseek_chat_history = []
        st.session_state.deepseek_chat_history.append({"role": "user", "content": user_input})

        with st.spinner("🤖 Agnes AI 思考中，正在調用工具與搜尋…"):
            try:
                response = engine.smart_query(user_input)
            except Exception as exc:
                response = {"error": str(exc)}

        # 若有模型自動回退，顯示提示
        if "model_fallback" in response:
            st.info(
                f"⚠️ 原設定模型不可用，已自動切換至 `{response['model_fallback']}`。\n\n"
                "建議在 **⚙️ 系統設定** 中將模型名稱更新為 `agnes-2.0-flash`。",
                icon="🔄",
            )

        ai_text = (
            f"❌ 發生錯誤：{response['error']}"
            if "error" in response
            else (response.get("analysis") or "（AI 無回應，請重試）")
        )

        st.session_state.deepseek_chat_history.append({"role": "assistant", "content": ai_text})
        add_history("Agnes AI", {"type": "deepseek_chat", "query": user_input[:40]})
        st.rerun()
