"""
配置管理模組 — API KEY、書籤、歷史紀錄
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# 保留模組層級預設常數以相容舊有參考
CONFIG_DIR = Path.home() / ".app_config"
CONFIG_FILE = CONFIG_DIR / "config.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
WATCHLIST_FILE = CONFIG_DIR / "watchlist.json"

# 默認配置（不含任何金鑰）
DEFAULT_CONFIG = {
    "api_key": "",
    "secret_key": "",
    "simulation_mode": True,
    "finmind_token": "",
    "notion_token": "",
    "notion_database_id": "",
    "ai_api_key": "",
    "ai_model": "agnes-2.0-flash",
    "ai_base_url": "https://apihub.agnes-ai.com/v1",
    "export_format": "csv",
}


class ConfigStore:
    """設定儲存器實例，將檔案路徑儲存為屬性以提供完整的單元測試隔離"""

    def __init__(self, config_dir=None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".app_config"
        self.config_file = self.config_dir / "config.json"
        self.bookmarks_file = self.config_dir / "bookmarks.json"
        self.history_file = self.config_dir / "history.json"
        self.watchlist_file = self.config_dir / "watchlist.json"

    def _ensure_config_dir(self):
        """確保配置目錄存在"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_streamlit_secrets(self) -> Dict[str, Any]:
        """從 Streamlit Secrets 讀取金鑰（雲端部署用，本機無效果）"""
        try:
            import streamlit as st
            mapping = {
                "FINMIND_TOKEN": "finmind_token",
                "AGNES_API_KEY": "ai_api_key",
                "DEEPSEEK_API_KEY": "ai_api_key",
                "AGNES_MODEL": "ai_model",
                "DEEPSEEK_MODEL": "ai_model",
                "AGNES_BASE_URL": "ai_base_url",
                "DEEPSEEK_BASE_URL": "ai_base_url",
            }
            return {cfg_key: st.secrets[secret_key]
                    for secret_key, cfg_key in mapping.items()
                    if secret_key in st.secrets}
        except Exception:
            return {}

    def load_config(self) -> Dict[str, Any]:
        """讀取配置。優先順序：Streamlit Secrets > 本地 config.json > 預設值"""
        self._ensure_config_dir()
        config = DEFAULT_CONFIG.copy()

        # 本地設定檔
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
            except Exception:
                pass
        else:
            self.save_config(config)

        # Streamlit Secrets 最高優先（雲端部署時覆蓋本地值）
        config.update(self._load_streamlit_secrets())

        # 一次性遷移：舊鍵 deepseek_* → 新鍵 ai_*（舊鍵保留不刪）
        config = self._migrate_old_keys(config)

        return config

    def _migrate_old_keys(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """若舊鍵有值而新鍵為空，自動搬到新鍵並存檔。"""
        old_key = "deepseek_api_key"
        new_key = "ai_api_key"
        model_key = "ai_model"
        url_key = "ai_base_url"

        needs_save = False
        if config.get(old_key) and not config.get(new_key):
            config[new_key] = config.pop(old_key)
            needs_save = True
        if config.get("deepseek_model") and not config.get(model_key):
            config[model_key] = config.pop("deepseek_model")
            needs_save = True
        if config.get("deepseek_base_url") and not config.get(url_key):
            config[url_key] = config.pop("deepseek_base_url")
            needs_save = True

        if needs_save:
            self.save_config(config)
        return config

    def save_config(self, config: Dict[str, Any]):
        """保存配置"""
        self._ensure_config_dir()
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_bookmarks(self) -> List[Dict[str, Any]]:
        """讀取書籤，支援損壞回退"""
        self._ensure_config_dir()
        if self.bookmarks_file.exists():
            try:
                with open(self.bookmarks_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_bookmarks(self, bookmarks: List[Dict[str, Any]]):
        """保存書籤"""
        self._ensure_config_dir()
        bookmarks = bookmarks[:100]
        with open(self.bookmarks_file, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f, ensure_ascii=False, indent=2)

    def add_bookmark(self, name: str, tab: str, params: Dict[str, Any]) -> bool:
        """添加書籤"""
        bookmarks = self.load_bookmarks()
        # 檢查重複
        if any(b["name"] == name for b in bookmarks):
            return False
        bookmarks.insert(0, {
            "name": name,
            "tab": tab,
            "params": params,
            "created_at": datetime.now().isoformat()
        })
        self.save_bookmarks(bookmarks)
        return True

    def remove_bookmark(self, name: str):
        """刪除書籤"""
        bookmarks = self.load_bookmarks()
        bookmarks = [b for b in bookmarks if b["name"] != name]
        self.save_bookmarks(bookmarks)

    def load_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """讀取查詢歷史（最多 limit 筆），支援損壞回退"""
        self._ensure_config_dir()
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    return history[:limit]
            except Exception:
                return []
        return []

    def save_history(self, history: List[Dict[str, Any]]):
        """保存查詢歷史"""
        self._ensure_config_dir()
        # 只保留最近 100 筆
        if len(history) > 100:
            try:
                # 判斷是新到舊還是舊到新以保留最晚近的紀錄
                first_ts = history[0].get("timestamp", "")
                last_ts = history[-1].get("timestamp", "")
                if first_ts >= last_ts:
                    history = history[:100]
                else:
                    history = history[-100:]
            except Exception:
                history = history[:100]
        else:
            history = history[:100]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def add_history(self, tab: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """添加查詢紀錄到歷史"""
        history = self.load_history()
        history.insert(0, {
            "tab": tab,
            "params": params,
            "timestamp": datetime.now().isoformat()
        })
        self.save_history(history)
        return history

    def clear_history(self):
        """清空查詢歷史"""
        self._ensure_config_dir()
        self.save_history([])

    def load_watchlist(self) -> Dict[str, List[str]]:
        """讀取自選監控名單"""
        self._ensure_config_dir()
        if self.watchlist_file.exists():
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"snapshots": [], "kbars": []}
        return {"snapshots": [], "kbars": []}

    def save_watchlist(self, watchlist: Dict[str, List[str]]):
        """保存自選監控名單"""
        self._ensure_config_dir()
        with open(self.watchlist_file, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)


# 初始化預設與活動儲存器
_default_store = ConfigStore()
_active_store = _default_store


# 模組級別純函數 — 轉發至 _active_store 活動儲存器以實現向後相容
def load_config() -> Dict[str, Any]:
    return _active_store.load_config()


def save_config(config: Dict[str, Any]):
    _active_store.save_config(config)


def load_bookmarks() -> List[Dict[str, Any]]:
    return _active_store.load_bookmarks()


def save_bookmarks(bookmarks: List[Dict[str, Any]]):
    _active_store.save_bookmarks(bookmarks)


def add_bookmark(name: str, tab: str, params: Dict[str, Any]) -> bool:
    return _active_store.add_bookmark(name, tab, params)


def remove_bookmark(name: str):
    _active_store.remove_bookmark(name)


def load_history(limit: int = 100) -> List[Dict[str, Any]]:
    return _active_store.load_history(limit)


def save_history(history: List[Dict[str, Any]]):
    _active_store.save_history(history)


def add_history(tab: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _active_store.add_history(tab, params)


def clear_history():
    _active_store.clear_history()


def load_watchlist() -> Dict[str, List[str]]:
    return _active_store.load_watchlist()


def save_watchlist(watchlist: Dict[str, List[str]]):
    _active_store.save_watchlist(watchlist)


def load_alerts() -> List[Dict[str, Any]]:
    """讀取警示規則（JSON 檔案，容錯模式）"""
    store = _active_store
    alerts_file = store.config_dir / "alerts.json"
    try:
        if alerts_file.exists():
            with open(alerts_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        return []
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []


def save_alerts(alerts: List[Dict[str, Any]]):
    """儲存警示規則"""
    store = _active_store
    alerts_file = store.config_dir / "alerts.json"
    try:
        with open(alerts_file, "w", encoding="utf-8") as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)
    except OSError as e:
        main_logger.warning(f"save_alerts 失敗: {e}")


class ConfigManager(ConfigStore):
    """相容性包裝器，將舊的類別呼叫導向至 ConfigStore，並在指定路徑時將活動儲存器切換至 self"""

    def __init__(self, config_dir=None):
        super().__init__(config_dir)
        if config_dir:
            global _active_store
            _active_store = self

    def ensure_default_config(self):
        """確保預設設定已初始化"""
        self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """相容舊版：載入時若 JSON 格式有誤則拋出異常"""
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                json.load(f)  # 若格式錯誤直接拋出 JSONDecodeError
        return super().load_config()


# 6.2 實作統一金鑰獲取機制
def get_secret(name: str) -> str:
    """
    統一獲取敏感金鑰與設定值的優先順序防線。
    順序：環境變數（大寫） → Streamlit secrets（大寫） → 本地 config.json 設定檔（小寫）。
    """
    env_name = name.upper()

    # 1. 系統環境變數
    val = os.environ.get(env_name, "")
    if val:
        return val

    # 2. Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and env_name in st.secrets:
            return st.secrets[env_name]
    except Exception:
        pass

    # 3. 本地 config.json 欄位
    try:
        cfg = load_config()
        cfg_key = name.lower()
        if cfg_key in cfg:
            return str(cfg.get(cfg_key, ""))
    except Exception:
        pass

    return ""
