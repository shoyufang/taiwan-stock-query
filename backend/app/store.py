"""本地快取（SQLite，存在 Docker volume /data）。內容都可從 FinMind 重建，遺失無妨。

- bars：個股日 K（原始成交價），增量更新
- kv：其他資料集的 JSON 快取，帶抓取時間
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bars (
                code TEXT NOT NULL, date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume INTEGER, value REAL,
                PRIMARY KEY (code, date));
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, fetched_at REAL NOT NULL, body TEXT NOT NULL);
            """
        )

    # ── 日 K ──
    def upsert_bars(self, code: str, bars: list[dict]) -> None:
        with self._lock, self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?)",
                [(code, b["date"], b["open"], b["high"], b["low"], b["close"], b["volume"], b["value"]) for b in bars],
            )

    def get_bars(self, code: str, since: str | None = None) -> list[dict]:
        sql = "SELECT date, open, high, low, close, volume, value FROM bars WHERE code=?"
        args: list = [code]
        if since:
            sql += " AND date>=?"
            args.append(since)
        with self._lock:
            rows = self.conn.execute(sql + " ORDER BY date", args).fetchall()
        return [dict(zip(("date", "open", "high", "low", "close", "volume", "value"), r)) for r in rows]

    def last_bar_date(self, code: str) -> str | None:
        with self._lock:
            row = self.conn.execute("SELECT MAX(date) FROM bars WHERE code=?", (code,)).fetchone()
        return row[0] if row else None

    # ── 一般快取 ──
    def kv_get(self, key: str, max_age: float) -> object | None:
        with self._lock:
            row = self.conn.execute("SELECT fetched_at, body FROM kv WHERE key=?", (key,)).fetchone()
        if not row or time.time() - row[0] > max_age:
            return None
        return json.loads(row[1])

    def kv_put(self, key: str, value: object) -> None:
        with self._lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?,?)",
                              (key, time.time(), json.dumps(value, ensure_ascii=False)))
