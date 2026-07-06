import sys
import os
from unittest.mock import MagicMock, patch

# 確保專案根目錄在 sys.path 最前面
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root in sys.path:
    sys.path.remove(_project_root)
sys.path.insert(0, _project_root)

# 強制載入本地 utils.py 並覆蓋 shioaji 搶註冊的 sys.modules['utils']
import importlib.util
_local_utils_path = os.path.join(_project_root, 'utils.py')
_spec = importlib.util.spec_from_file_location('utils', _local_utils_path)
_local_utils = importlib.util.module_from_spec(_spec)
sys.modules['utils'] = _local_utils
_spec.loader.exec_module(_local_utils)

# 模擬 session_state 為字典格式
class MockSessionState(dict):
    def __getattr__(self, item):
        return self.get(item, MagicMock())
    def __setattr__(self, key, value):
        self[key] = value

mock_st = MagicMock()
mock_st.session_state = MockSessionState()
mock_st.session_state["theme"] = "🌅 Claude 暖橘"
mock_st.columns = lambda spec, *args, **kwargs: [MagicMock() for _ in range(spec)] if isinstance(spec, int) else [MagicMock(), MagicMock()]
mock_st.tabs = lambda spec, *args, **kwargs: [MagicMock() for _ in range(spec)] if isinstance(spec, int) else [MagicMock(), MagicMock()]
mock_st.text_input = lambda label, value="", *args, **kwargs: value
mock_st.number_input = lambda label, value=0, *args, **kwargs: value
mock_st.checkbox = lambda label, value=False, *args, **kwargs: value
mock_st.selectbox = lambda label, options=None, *args, **kwargs: options[0] if options else ""
mock_st.multiselect = lambda label, options=None, default=None, *args, **kwargs: default if default is not None else []
mock_st.date_input = lambda label, value=None, *args, **kwargs: value

import pytest

@pytest.mark.unit
def test_registry_exists_and_covers_known_types():
    # sys.modules['streamlit'] 只在 import app 期間替換成 mock，用完立即還原，
    # 避免污染同一 pytest process 內後續收集的其他測試檔案（2026-07-07 審查發現）
    _real_streamlit = sys.modules.get('streamlit')
    sys.modules['streamlit'] = mock_st
    try:
        from app import QUERY_DISPATCH
    finally:
        if _real_streamlit is not None:
            sys.modules['streamlit'] = _real_streamlit
        else:
            sys.modules.pop('streamlit', None)
    for qt in ["ranking", "snapshot", "kbar", "ticks", "institutional"]:
        assert qt in QUERY_DISPATCH, f"registry 缺少 {qt}"
        assert callable(QUERY_DISPATCH[qt])
