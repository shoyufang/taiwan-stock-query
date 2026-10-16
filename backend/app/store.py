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
            CREATE TABLE IF NOT EXISTS watchlist (code TEXT PRIMARY KEY, position INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, type TEXT NOT NULL, value REAL NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, last_triggered_date TEXT);
            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, rule_id INTEGER, code TEXT NOT NULL, type TEXT NOT NULL,
                message TEXT NOT NULL, at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, shares INTEGER NOT NULL,
                cost REAL NOT NULL, bought_on TEXT, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
            """
        )
        # 這些表只存使用者自己的設定與紀錄；與上面的快取不同，遺失會掉資料（volume 要保留）

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

    # ── 自選股 ──
    def get_watchlist(self) -> list[str] | None:
        """None 表示從未設定過（前端用預設清單）。"""
        with self._lock:
            rows = self.conn.execute("SELECT code FROM watchlist ORDER BY position").fetchall()
            touched = self.conn.execute("SELECT 1 FROM kv WHERE key='watchlist:set'").fetchone()
        return [r[0] for r in rows] if (rows or touched) else None

    def set_watchlist(self, codes: list[str]) -> None:
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM watchlist")
            self.conn.executemany("INSERT INTO watchlist VALUES (?,?)", [(c, i) for i, c in enumerate(codes)])
            self.conn.execute("INSERT OR REPLACE INTO kv VALUES ('watchlist:set', ?, 'true')", (time.time(),))

    # ── 警示 ──
    def list_rules(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, code, type, value, enabled, created_at, last_triggered_date FROM alert_rules ORDER BY id").fetchall()
        keys = ("id", "code", "type", "value", "enabled", "created_at", "last_triggered_date")
        return [{**dict(zip(keys, r)), "enabled": bool(r[4])} for r in rows]

    def add_rule(self, code: str, type_: str, value: float, created_at: str) -> int:
        with self._lock, self.conn:
            cur = self.conn.execute("INSERT INTO alert_rules (code, type, value, enabled, created_at) VALUES (?,?,?,1,?)",
                                    (code, type_, value, created_at))
            return cur.lastrowid

    def update_rule(self, rule_id: int, enabled: bool) -> bool:
        with self._lock, self.conn:
            return self.conn.execute("UPDATE alert_rules SET enabled=? WHERE id=?", (int(enabled), rule_id)).rowcount > 0

    def delete_rule(self, rule_id: int) -> bool:
        with self._lock, self.conn:
            return self.conn.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,)).rowcount > 0

    def mark_triggered(self, rule_id: int, day: str, code: str, type_: str, message: str, at: str) -> bool:
        """同一規則同一天只記一次；回傳這次是否為新觸發。"""
        with self._lock, self.conn:
            cur = self.conn.execute(
                "UPDATE alert_rules SET last_triggered_date=? WHERE id=? AND (last_triggered_date IS NULL OR last_triggered_date<>?)",
                (day, rule_id, day))
            if cur.rowcount == 0:
                return False
            self.conn.execute("INSERT INTO alert_events (rule_id, code, type, message, at) VALUES (?,?,?,?,?)",
                              (rule_id, code, type_, message, at))
            return True

    def add_event(self, code: str, type_: str, message: str, at: str) -> None:
        """不屬於使用者規則的系統通知（例如處置股），rule_id 留空。"""
        with self._lock, self.conn:
            self.conn.execute("INSERT INTO alert_events (rule_id, code, type, message, at) VALUES (NULL,?,?,?,?)",
                              (code, type_, message, at))

    def list_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, rule_id, code, type, message, at FROM alert_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(zip(("id", "rule_id", "code", "type", "message", "at"), r)) for r in rows]

    # ── 投資組合（手動輸入，每筆為一次買進） ──
    _HOLDING_COLS = ("id", "code", "shares", "cost", "bought_on", "note", "created_at")

    def list_holdings(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(f"SELECT {', '.join(self._HOLDING_COLS)} FROM holdings ORDER BY code, id").fetchall()
        return [dict(zip(self._HOLDING_COLS, r)) for r in rows]

    def add_holding(self, code: str, shares: int, cost: float, bought_on: str | None, note: str, created_at: str) -> int:
        with self._lock, self.conn:
            return self.conn.execute(
                "INSERT INTO holdings (code, shares, cost, bought_on, note, created_at) VALUES (?,?,?,?,?,?)",
                (code, shares, cost, bought_on, note, created_at)).lastrowid

    def update_holding(self, holding_id: int, shares: int, cost: float, bought_on: str | None, note: str) -> bool:
        with self._lock, self.conn:
            return self.conn.execute("UPDATE holdings SET shares=?, cost=?, bought_on=?, note=? WHERE id=?",
                                     (shares, cost, bought_on, note, holding_id)).rowcount > 0

    def delete_holding(self, holding_id: int) -> bool:
        with self._lock, self.conn:
            return self.conn.execute("DELETE FROM holdings WHERE id=?", (holding_id,)).rowcount > 0

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
