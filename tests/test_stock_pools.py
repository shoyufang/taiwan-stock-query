"""
守門測試（R3）— 確保股票池只有 stock_pools.py 一份定義，
防止未來 AI 接力開發時又複製一份出來（本輪已抓到 3 份互相不一致的清單）。
"""
import re
from pathlib import Path

import pytest

from stock_pools import TW_TOP50, US_TOP50


def test_tw_top50_has_50_unique_codes():
    assert len(TW_TOP50) == 50
    assert len(set(TW_TOP50)) == 50
    assert all(code.isdigit() for code in TW_TOP50)


def test_us_top50_has_50_unique_symbols():
    assert len(US_TOP50) == 50
    assert len(set(US_TOP50)) == 50


def test_no_duplicate_pool_definitions_in_repo():
    """全案 grep 不到第二份 50 檔硬編碼清單（只允許 stock_pools.py 本身）。"""
    project_root = Path(__file__).resolve().parent.parent
    pattern = re.compile(r'^\s*(TW_TOP50|US_TOP50|TW_SCREENER_POOL|TW_BLUE_CHIPS|US_SCREENER_POOL)\s*=\s*\[')

    offenders = []
    for py_file in project_root.rglob("*.py"):
        if "stock_pools.py" in str(py_file):
            continue
        if any(part in str(py_file) for part in (".git", "__pycache__", "site-packages")):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line in text.splitlines():
            if pattern.match(line):
                offenders.append(str(py_file.relative_to(project_root)))

    assert not offenders, (
        f"發現第二份股票池硬編碼清單，應改成 `from stock_pools import ...`: {offenders}"
    )
