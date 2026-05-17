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

# 默認配置
DEFAULT_CONFIG = {
    "api_key": "<YOUR_SHIOAJI_API_KEY>",
    "secret_key": "<YOUR_SHIOAJI_SECRET_KEY>",
    "finmind_token": "<YOUR_FINMIND_TOKEN>",
    "notion_token": "",
    "notion_database_id": "",
    "gemini_api_key": "",
    "gemini_model": "",
    "export_format": "csv",
    "simulation_mode": True,
}

def _ensure_config_dir():
    """確保配置目錄存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> Dict[str, Any]:
    """讀取配置，若不存在或損壞則建立默認配置"""
    _ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 確保合併默認值（防止缺少新欄位）
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

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
