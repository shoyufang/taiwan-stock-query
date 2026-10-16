"""
測試 Phase A 相容性：TAB_COMPAT_MAP 所有舊鍵映射到 TAB_RENDERERS
"""
import sys
import os

# 確保專案根目錄在 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tab_compat_values_in_renderers():
    """TAB_COMPAT_MAP 所有映射值必須 ∈ TAB_RENDERERS 的鍵"""
    from app import TAB_COMPAT_MAP, TAB_RENDERERS

    compat_keys = set(TAB_COMPAT_MAP.keys())
    renderer_keys = set(TAB_RENDERERS.keys())
    mapped_values = set(TAB_COMPAT_MAP.values())

    # 所有舊鍵 → 新鍵 映射後的值必須在 TAB_RENDERERS 中
    missing = mapped_values - renderer_keys
    assert not missing, f"以下映射值不在 TAB_RENDERERS: {missing}"


def test_all_compat_keys_covered():
    """TAB_COMPAT_MAP 不該有空值或 None"""
    from app import TAB_COMPAT_MAP

    for old_key, new_key in TAB_COMPAT_MAP.items():
        assert new_key is not None and new_key != "", f"TAB_COMPAT_MAP['{old_key}'] 為空值"


def test_primary_tabs_in_renderers():
    """PRIMARY_TABS 全部要在 TAB_RENDERERS 中"""
    from app import PRIMARY_TABS, TAB_RENDERERS

    missing = [t for t in PRIMARY_TABS if t not in TAB_RENDERERS]
    assert not missing, f"PRIMARY_TABS 以下鍵不在 TAB_RENDERERS: {missing}"


def test_advanced_tabs_in_renderers():
    """ADVANCED_TABS 全部要在 TAB_RENDERERS 中"""
    from app import ADVANCED_TABS, TAB_RENDERERS

    missing = [t for t in ADVANCED_TABS if t not in TAB_RENDERERS]
    assert not missing, f"ADVANCED_TABS 以下鍵不在 TAB_RENDERERS: {missing}"


def test_utility_tabs_in_renderers():
    """UTILITY_TABS 全部要在 TAB_RENDERERS 中"""
    from app import UTILITY_TABS, TAB_RENDERERS

    missing = [t for t in UTILITY_TABS if t not in TAB_RENDERERS]
    assert not missing, f"UTILITY_TABS 以下鍵不在 TAB_RENDERERS: {missing}"
