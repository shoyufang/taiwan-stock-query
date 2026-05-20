"""
配置管理模組 — API KEY、書籤、歷史紀錄
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

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
    "gemini_api_key": "",
    "gemini_model": "gemini-3.5-flash",
    "export_format": "csv",
}

def _ensure_config_dir():
    """確保配置目錄存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def _load_streamlit_secrets() -> Dict[str, Any]:
    """從 Streamlit Secrets 讀取金鑰（雲端部署用，本機無效果）"""
    try:
        import streamlit as st
        mapping = {
            "FINMIND_TOKEN": "finmind_token",
            "GEMINI_API_KEY": "gemini_api_key",
            "GEMINI_MODEL":   "gemini_model",
        }
        return {cfg_key: st.secrets[secret_key]
                for secret_key, cfg_key in mapping.items()
                if secret_key in st.secrets}
    except Exception:
        return {}

def load_config() -> Dict[str, Any]:
    """讀取配置。優先順序：Streamlit Secrets > 本地 config.json > 預設值"""
    _ensure_config_dir()
    config = DEFAULT_CONFIG.copy()

    # 本地設定檔
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except Exception:
            pass
    else:
        save_config(config)

    # Streamlit Secrets 最高優先（雲端部署時覆蓋本地值）
    config.update(_load_streamlit_secrets())
    return config

def save_config(config: Dict[str, Any]):
    """保存配置"""
    _ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_bookmarks() -> List[Dict[str, Any]]:
    """讀取書籤，支援損壞回退"""
    _ensure_config_dir()
    if BOOKMARKS_FILE.exists():
        try:
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_bookmarks(bookmarks: List[Dict[str, Any]]):
    """保存書籤"""
    _ensure_config_dir()
    bookmarks = bookmarks[:100]
    with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=2)

def add_bookmark(name: str, tab: str, params: Dict[str, Any]) -> bool:
    """添加書籤"""
    bookmarks = load_bookmarks()
    # 檢查重複
    if any(b["name"] == name for b in bookmarks):
        return False
    bookmarks.insert(0, {
        "name": name,
        "tab": tab,
        "params": params,
        "created_at": datetime.now().isoformat()
    })
    save_bookmarks(bookmarks)
    return True

def remove_bookmark(name: str):
    """刪除書籤"""
    bookmarks = load_bookmarks()
    bookmarks = [b for b in bookmarks if b["name"] != name]
    save_bookmarks(bookmarks)

def load_history(limit: int = 100) -> List[Dict[str, Any]]:
    """讀取查詢歷史（最多 limit 筆），支援損壞回退"""
    _ensure_config_dir()
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                return history[:limit]
        except Exception:
            return []
    return []

def save_history(history: List[Dict[str, Any]]):
    """保存查詢歷史"""
    _ensure_config_dir()
    # 只保留最近 100 筆
    if len(history) > 100:
        try:
            # 判斷是新到舊（首筆較新）還是舊到新（尾筆較新），以保留最晚近的紀錄且維持原有順序
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
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def add_history(tab: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """添加查詢紀錄到歷史"""
    history = load_history()
    history.insert(0, {
        "tab": tab,
        "params": params,
        "timestamp": datetime.now().isoformat()
    })
    save_history(history)
    return history

def clear_history():
    """清空查詢歷史"""
    _ensure_config_dir()
    save_history([])

def load_watchlist() -> Dict[str, List[str]]:
    """讀取自選監控名單"""
    _ensure_config_dir()
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"snapshots": [], "kbars": []}
    return {"snapshots": [], "kbars": []}

def save_watchlist(watchlist: Dict[str, List[str]]):
    """保存自選監控名單"""
    _ensure_config_dir()
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


class ConfigManager:
    """相容性包裝器，將舊的類別呼叫導向到新的純函數"""
    def __init__(self, config_dir=None):
        if config_dir:
            global CONFIG_DIR, CONFIG_FILE, BOOKMARKS_FILE, HISTORY_FILE, WATCHLIST_FILE
            CONFIG_DIR = Path(config_dir)
            CONFIG_FILE = CONFIG_DIR / "config.json"
            BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
            HISTORY_FILE = CONFIG_DIR / "history.json"
            WATCHLIST_FILE = CONFIG_DIR / "watchlist.json"

    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                json.load(f)
        return load_config()

    def save_config(self, config):
        save_config(config)

    def load_bookmarks(self):
        return load_bookmarks()

    def save_bookmarks(self, bookmarks):
        save_bookmarks(bookmarks)

    def load_history(self, limit=100):
        return load_history(limit)

    def save_history(self, history):
        save_history(history)

    def clear_history(self):
        clear_history()

    def ensure_default_config(self):
        load_config()

