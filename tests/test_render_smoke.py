"""
渲染煙霧測試 — 用 Streamlit AppTest 逐一切換 8 個一級導航頁，
任何 AttributeError / DuplicateElementId / yf.T 崩潰都會在部署前抓到。

標記為 slow：會真的執行查詢（網路慢時跑得久），CI 可跳過。
"""
import pytest
from streamlit.testing.v1 import AppTest


def test_app_boots():
    """基本啟動測試：app.py 能正常渲染不拋例外"""
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    assert not at.exception


@pytest.mark.slow
@pytest.mark.parametrize("tab", [
    "市場總覽",
    "個股全景",
    "自選股",
    "選股中心",
    "全球市場",
    "投資行事曆",
    "AI 助理",
    "投資組合",
])
def test_each_tab_renders(tab):
    """逐一切換一級導航頁，確認渲染不崩潰"""
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["selected_tab"] = tab
    at.run()
    assert not at.exception, f"{tab} 渲染拋出例外: {at.exception}"
