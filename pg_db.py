"""
PostgreSQL 寫入模組 — 供 daily_job.py 呼叫
表格：market_daily / screener_daily / disposition
PG 失敗不中斷主流程，全部靜默 fallback。
"""

import os
import json
import pandas as pd

_conn = None

PG_URL = os.environ.get("PG_URL", "")


def _get_conn():
    global _conn
    if _conn is not None:
        try:
            _conn.isolation_level  # ping
            return _conn
        except Exception:
            _conn = None
    if not PG_URL:
        return None
    try:
        import psycopg2
        _conn = psycopg2.connect(PG_URL)
        _conn.autocommit = False
        return _conn
    except Exception as e:
        print(f"  ⚠️  PG 連線失敗: {e}")
        return None


_DDL = """
CREATE TABLE IF NOT EXISTS market_daily (
    date            DATE PRIMARY KEY,
    taiex           NUMERIC(10,2),
    taiex_chg       NUMERIC(8,2),
    taiex_pct       NUMERIC(6,2),
    up_count        INT,
    down_count      INT,
    trade_value_bn  NUMERIC(10,1),
    foreign_net_bn  NUMERIC(10,2),
    trust_net_bn    NUMERIC(10,2),
    dealer_net_bn   NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS screener_daily (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    code            VARCHAR(10) NOT NULL,
    name            VARCHAR(100),
    close_price     NUMERIC(10,2),
    change_pct      NUMERIC(6,2),
    volume_k        INT,
    foreign_net_k   INT,
    trust_net_k     INT,
    pe_ratio        NUMERIC(8,2),
    dividend_yield  NUMERIC(6,2),
    pb_ratio        NUMERIC(6,2),
    conditions      TEXT,
    UNIQUE (date, code)
);

CREATE TABLE IF NOT EXISTS disposition (
    id        SERIAL PRIMARY KEY,
    date      DATE NOT NULL,
    code      VARCHAR(10),
    name      VARCHAR(100),
    raw_data  JSONB,
    UNIQUE (date, code)
);
"""


def ensure_tables() -> bool:
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(_DDL)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  PG 建表失敗: {e}")
        return False


def upsert_market(data: dict, today: str) -> bool:
    conn = _get_conn()
    if conn is None:
        return False
    sql = """
    INSERT INTO market_daily
        (date, taiex, taiex_chg, taiex_pct, up_count, down_count,
         trade_value_bn, foreign_net_bn, trust_net_bn, dealer_net_bn)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (date) DO UPDATE SET
        taiex          = EXCLUDED.taiex,
        taiex_chg      = EXCLUDED.taiex_chg,
        taiex_pct      = EXCLUDED.taiex_pct,
        up_count       = EXCLUDED.up_count,
        down_count     = EXCLUDED.down_count,
        trade_value_bn = EXCLUDED.trade_value_bn,
        foreign_net_bn = EXCLUDED.foreign_net_bn,
        trust_net_bn   = EXCLUDED.trust_net_bn,
        dealer_net_bn  = EXCLUDED.dealer_net_bn;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (
                today,
                data.get("taiex"),
                data.get("taiex_chg"),
                data.get("taiex_pct"),
                data.get("up"),
                data.get("down"),
                data.get("value"),
                data.get("foreign"),
                data.get("trust"),
                data.get("dealer"),
            ))
        conn.commit()
        print("  ✅ PG market_daily 寫入完成")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  PG market_daily 失敗: {e}")
        return False


def upsert_screener(df: pd.DataFrame, today: str) -> int:
    if df.empty:
        return 0
    conn = _get_conn()
    if conn is None:
        return 0
    sql = """
    INSERT INTO screener_daily
        (date, code, name, close_price, change_pct, volume_k,
         foreign_net_k, trust_net_k, pe_ratio, dividend_yield, pb_ratio, conditions)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (date, code) DO UPDATE SET
        close_price    = EXCLUDED.close_price,
        change_pct     = EXCLUDED.change_pct,
        volume_k       = EXCLUDED.volume_k,
        foreign_net_k  = EXCLUDED.foreign_net_k,
        trust_net_k    = EXCLUDED.trust_net_k,
        pe_ratio       = EXCLUDED.pe_ratio,
        dividend_yield = EXCLUDED.dividend_yield,
        pb_ratio       = EXCLUDED.pb_ratio,
        conditions     = EXCLUDED.conditions;
    """

    def _safe(v):
        if v is None:
            return None
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        return v

    count = 0
    try:
        with conn.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute(sql, (
                    today,
                    str(r.get("代號", "")),
                    str(r.get("名稱", "")),
                    _safe(r.get("收盤價")),
                    _safe(r.get("漲跌幅%")),
                    _safe(r.get("成交量(張)")),
                    # 欄位 (股) 是原始股數（2026-07-09 起），DB 欄位 _net_k 語意是「張」
                    # (1000股)，寫入前除 1000，schema 本身不動
                    _safe((lambda v: v / 1000 if v is not None else None)(r.get("外資買賣超(股)"))),
                    _safe((lambda v: v / 1000 if v is not None else None)(r.get("投信買賣超(股)"))),
                    _safe(r.get("本益比")),
                    _safe(r.get("殖利率%")),
                    _safe(r.get("股淨比")),
                    str(r.get("符合條件", "")),
                ))
                count += 1
        conn.commit()
        print(f"  ✅ PG screener_daily 寫入 {count} 筆")
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  PG screener_daily 失敗: {e}")
    return count


def upsert_disposition(df: pd.DataFrame, today: str) -> int:
    if df.empty:
        return 0
    conn = _get_conn()
    if conn is None:
        return 0
    sql = """
    INSERT INTO disposition (date, code, name, raw_data)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (date, code) DO NOTHING;
    """
    # 猜代號欄 / 名稱欄
    code_col = next((c for c in df.columns if "代號" in c or "Code" in c), df.columns[0])
    name_col = next((c for c in df.columns if "名稱" in c or "Name" in c), None)

    count = 0
    try:
        with conn.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute(sql, (
                    today,
                    str(r[code_col]).strip(),
                    str(r[name_col]).strip() if name_col else "",
                    json.dumps(r.to_dict(), ensure_ascii=False, default=str),
                ))
                count += 1
        conn.commit()
        print(f"  ✅ PG disposition 寫入 {count} 筆")
    except Exception as e:
        conn.rollback()
        print(f"  ⚠️  PG disposition 失敗: {e}")
    return count
