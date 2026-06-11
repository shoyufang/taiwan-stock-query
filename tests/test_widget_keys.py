"""
防回歸測試：掃描 tabs/*.py 原始碼，所有 Streamlit 元件呼叫必須含 key=。
任何缺少 key= 的元件都會導致測試失敗，確保未來新增的元件不會遺漏。
"""
import ast
import os
import re
from pathlib import Path


# Streamlit 需要 key 參數的元件名稱（st.metric 不需要 key）
REQUIRED_KEY_WIDGETS = [
    "st.button",
    "st.download_button",
    "st.text_input",
    "st.selectbox",
    "st.radio",
    "st.checkbox",
    "st.slider",
    "st.multiselect",
    "st.date_input",
    "st.number_input",
    "st.text_area",
    "st.toggle",
    "st.file_uploader",
    "st.camera_input",
    "st.map",
]


def find_files_without_keys(tabs_dir: str = None) -> list:
    """掃描 tabs/*.py，找出所有 Widget 呼叫不含 key= 的檔案。"""
    if tabs_dir is None:
        tabs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tabs")

    violations = []

    for pyfile in Path(tabs_dir).glob("*.py"):
        if pyfile.name == "__init__.py":
            continue

        with open(pyfile, "r", encoding="utf-8-sig") as f:
            try:
                source = f.read()
            except Exception:
                continue

        # 用 regex 找所有 st.xxx( 的呼叫，往後看 3 行內是否有 key=
        lines = source.split("\n")
        for i, line in enumerate(lines):
            line_num = i + 1
            for widget in REQUIRED_KEY_WIDGETS:
                if f"{widget}(" in line:
                    # 收集這行到後 8 行的內容（多選/複雜呼叫可能 key 在後面幾行）
                    snippet = "\n".join(lines[i:i+8])
                    # 檢查是否有 key=
                    # key= 可能出現在同一行或接下幾行
                    has_key = bool(re.search(r'\bkey\s*=', snippet))
                    # 但也可能是在 f-string 中 key=f"..."
                    has_fstring_key = bool(re.search(r'\bkey\s*=\s*f["\']', snippet))

                    if not (has_key or has_fstring_key):
                        violations.append((str(pyfile), line_num, widget, line.strip()[:80]))

    return violations


def test_all_widgets_have_keys():
    """所有 Streamlit 元件必須有 key= 參數"""
    violations = find_files_without_keys()

    if violations:
        msg_parts = [f"發現 {len(violations)} 個 Widget 缺少 key=：\n"]
        for fpath, line_num, widget, line_snippet in violations[:30]:
            short_path = fpath.replace(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tabs")
            msg_parts.append(f"  {short_path}:{line_num} | {widget} | {line_snippet}")
        msg_parts.append("\n\n請為每個 st.widget() 呼叫加上 key= 參數。")
        assert False, "\n".join(msg_parts)
