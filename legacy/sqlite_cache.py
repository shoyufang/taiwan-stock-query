"""
SQLite 永久快取層 — Phase 7 Task 7.1
提供持久化快取功能，優化應用程式冷啟動效能
"""

import sqlite3
import pickle
import time
import os
from pathlib import Path
from typing import Any, Optional
from logging_config import main_logger

# 快取目錄與檔案路徑（可由 APP_CACHE_DIR 環境變數覆寫，供 Docker host-mount 使用）
CACHE_DIR = Path(os.environ.get("APP_CACHE_DIR", str(Path.home() / ".app_config")))
CACHE_DB = CACHE_DIR / "cache.db"

class SQLiteCache:
    """SQLite 快取管理器"""
    
    def __init__(self, db_path: Path = CACHE_DB):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self):
        """確保目錄存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """初始化資料庫表結構"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value BLOB,
                        timestamp REAL,
                        ttl INTEGER
                    )
                """)
                # 建立索引以加速過期清理
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON cache (timestamp)")
        except Exception as e:
            main_logger.error(f"初始化 SQLite 快取失敗: {str(e)}")

    def get(self, key: str) -> Optional[Any]:
        """從快取獲取數據"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value, timestamp, ttl FROM cache WHERE key = ?", 
                    (key,)
                )
                row = cursor.fetchone()
                
                if row:
                    value_blob, timestamp, ttl = row
                    # 檢查是否過期
                    if ttl > 0 and (time.time() - timestamp) > ttl:
                        main_logger.debug(f"[SQLITE CACHE EXPIRED] key: {key}")
                        self.delete(key)
                        return None
                    
                    # 反序列化
                    try:
                        return pickle.loads(value_blob)
                    except Exception as pe:
                        main_logger.error(f"反序列化快取數據失敗 (key: {key}): {str(pe)}")
                        return None
                return None
        except Exception as e:
            main_logger.error(f"讀取 SQLite 快取失敗 (key: {key}): {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """將數據存入快取"""
        try:
            # 序列化
            value_blob = pickle.dumps(value)
            timestamp = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, timestamp, ttl) VALUES (?, ?, ?, ?)",
                    (key, value_blob, timestamp, ttl)
                )
        except Exception as e:
            main_logger.error(f"寫入 SQLite 快取失敗 (key: {key}): {str(e)}")

    def delete(self, key: str):
        """刪除指定快取"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        except Exception as e:
            main_logger.error(f"刪除 SQLite 快取失敗 (key: {key}): {str(e)}")

    def clear_expired(self):
        """清理所有過期快取"""
        try:
            now = time.time()
            with sqlite3.connect(self.db_path) as conn:
                # 刪除 (當前時間 - 存入時間) > ttl 的記錄 (ttl > 0)
                conn.execute("DELETE FROM cache WHERE ttl > 0 AND (? - timestamp) > ttl", (now,))
                main_logger.info("已清理 SQLite 過期快取數據")
        except Exception as e:
            main_logger.error(f"清理 SQLite 過期快取失敗: {str(e)}")

    def clear_all(self):
        """清空所有快取"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache")
                main_logger.info("已清空 SQLite 所有快取數據")
        except Exception as e:
            main_logger.error(f"清空 SQLite 快取失敗: {str(e)}")

# 單例實例
cache_manager = SQLiteCache()

def get_cache(key: str) -> Optional[Any]:
    """快捷函數：獲取快取"""
    return cache_manager.get(key)

def set_cache(key: str, value: Any, ttl: int = 3600):
    """快捷函數：設置快取"""
    cache_manager.set(key, value, ttl)

def clear_expired_cache():
    """快捷函數：清理過期"""
    cache_manager.clear_expired()
