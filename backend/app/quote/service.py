"""即時行情服務（獨立容器：python -m app.quote.service）。

全站唯一的 Shioaji 連線。只在交易時段登入；訂閱推播寫進 Redis 供 API 的 WebSocket 轉送。
遵守永豐金使用規範：盤中不輪詢 snapshots／ticks／kbars；排行每分鐘最多查一次。

Redis 鍵：
  q:{code}              pub/sub 頻道，推送 normalize 後的 JSON
  q:last:{code}         最新一筆（新連上的瀏覽器先拿這個）
  q:scanner             最新盤中排行（JSON）
  quote:interest        有序集合：瀏覽器關注的代號 → 最後關注時間
  quote:status          服務狀態（給 /api/health）
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import redis

from app.quote import normalize as nz
from app.quote.subscriptions import plan

log = logging.getLogger("quote")
TZ = ZoneInfo("Asia/Taipei")

INDEX_CODE = "IX0001"  # 加權指數
DEFAULT_PINNED = [INDEX_CODE, "2330", "2317", "2454", "2308", "2382"]
LOOP_SEC = 5
SCANNER_SEC = 60
LAST_TTL = 2 * 86400


class QuoteService:
    def __init__(self, rds: redis.Redis, api_factory, *, pinned: list[str] | None = None,
                 force_session: bool = False, clock=lambda: datetime.now(TZ), sj_module=None):
        self._sj = sj_module
        self.rds = rds
        self.api_factory = api_factory
        self.pinned = pinned or DEFAULT_PINNED
        self.force_session = force_session
        self.clock = clock
        self.api = None
        self.subscribed: set[str] = set()
        self.last_tick_at: str | None = None
        self.error: str | None = None
        self.backoff = 5
        self.next_login_at = 0.0
        self.last_scanner_at = 0.0
        self._lock = threading.Lock()

    # ── 推播回呼（在 Shioaji 自己的執行緒；只做轉換與寫入，不做運算）──
    def publish(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        code = payload["code"]
        pipe = self.rds.pipeline()
        pipe.set(f"q:last:{code}", data, ex=LAST_TTL)
        pipe.publish(f"q:{code}", data)
        pipe.execute()
        self.last_tick_at = self.clock().isoformat(timespec="seconds")

    def on_quote_stk(self, exchange, quote) -> None:
        try:
            self.publish(nz.from_quote_stk(quote))
        except Exception:
            log.exception("處理個股推播失敗")

    def on_quote_idx(self, exchange, quote) -> None:
        try:
            self.publish(nz.from_quote_idx(quote))
        except Exception:
            log.exception("處理指數推播失敗")

    # ── 連線管理 ──
    def login(self) -> None:
        api = self.api_factory()
        api.set_on_quote_stk_v1_callback(self.on_quote_stk)
        api.set_on_quote_idx_v1_callback(self.on_quote_idx)
        self.api = api
        self.subscribed = set()
        self.backoff = 5
        log.info("永豐金已登入")

    def logout(self) -> None:
        if self.api is not None:
            try:
                self.api.logout()
            except Exception:
                log.warning("登出時發生錯誤", exc_info=True)
        self.api = None
        self.subscribed = set()

    @property
    def sj(self):
        if self._sj is None:
            import shioaji  # 只在真正連線時需要
            self._sj = shioaji
        return self._sj

    def _contract(self, code: str):
        c = self.api.contracts.get(code)
        if c is None:
            raise KeyError(f"找不到商品合約 {code}")
        return c

    def reconcile(self, now_ts: float) -> None:
        sj = self.sj
        interest = {m: s for m, s in self.rds.zrange("quote:interest", 0, -1, withscores=True)}
        to_add, to_remove = plan(self.subscribed, self.pinned, interest, now_ts)
        for code in to_remove:
            try:
                self.api.unsubscribe(self._contract(code), quote_type=sj.QuoteType.Quote)
            except Exception:
                log.warning("退訂 %s 失敗", code, exc_info=True)
            self.subscribed.discard(code)
        for code in to_add:
            try:
                self.api.subscribe(self._contract(code), quote_type=sj.QuoteType.Quote)
                self.subscribed.add(code)
            except Exception:
                log.warning("訂閱 %s 失敗", code, exc_info=True)
        self.rds.zremrangebyscore("quote:interest", 0, now_ts - 3600)

    def refresh_scanner(self) -> None:
        sj = self.sj
        ranks = {}
        for key, stype, asc in [("amount", sj.ScannerType.AmountRank, True),
                                ("gainers", sj.ScannerType.ChangePercentRank, True),
                                ("losers", sj.ScannerType.ChangePercentRank, False)]:
            ranks[key] = nz.from_scanner(self.api.scanners(scanner_type=stype, ascending=asc, count=10))
        payload = {"kind": "scanner", "code": "SCANNER", "time": self.clock().isoformat(timespec="seconds"), **ranks}
        data = json.dumps(payload, ensure_ascii=False)
        self.rds.set("q:scanner", data, ex=LAST_TTL)
        self.rds.publish("q:SCANNER", data)

    # ── 主迴圈的一步（方便測試）──
    def step(self) -> str:
        now = self.clock()
        now_ts = now.timestamp()
        if not (self.force_session or nz.in_session(now)):
            if self.api is not None:
                self.logout()
                log.info("收盤，登出")
            return "closed"
        if self.api is None:
            if now_ts < self.next_login_at:
                return "waiting_retry"
            try:
                self.login()
                self.error = None
            except Exception as e:
                self.error = f"登入失敗：{e}"[:300]
                self.next_login_at = now_ts + self.backoff
                self.backoff = min(self.backoff * 2, 60)
                log.exception("永豐金登入失敗，%s 秒後重試", self.backoff)
                return "login_failed"
        try:
            self.reconcile(now_ts)
            if now_ts - self.last_scanner_at >= SCANNER_SEC:
                self.last_scanner_at = now_ts
                self.refresh_scanner()
        except Exception as e:
            self.error = f"執行錯誤：{e}"[:300]
            log.exception("行情服務執行錯誤，重新登入")
            self.logout()
            return "error"
        return "streaming"

    def write_status(self, state: str) -> None:
        status = {"state": state, "at": self.clock().isoformat(timespec="seconds"),
                  "last_tick_at": self.last_tick_at, "subscribed": len(self.subscribed), "error": self.error}
        self.rds.set("quote:status", json.dumps(status, ensure_ascii=False))


def shioaji_factory():
    import shioaji as sj
    key, secret = os.environ.get("SHIOAJI_API_KEY", ""), os.environ.get("SHIOAJI_SECRET_KEY", "")
    if not key or not secret:
        raise RuntimeError("未設定 SHIOAJI_API_KEY／SHIOAJI_SECRET_KEY（home server 的 deploy/.env）")
    simulation = os.environ.get("SHIOAJI_SIMULATION", "true").lower() != "false"
    api = sj.Shioaji(simulation=simulation)
    api.login(api_key=key, secret_key=secret, fetch_contract=True)
    return api


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    rds = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    svc = QuoteService(rds, shioaji_factory, force_session=os.environ.get("QUOTE_FORCE_SESSION") == "1")
    if not os.environ.get("SHIOAJI_API_KEY"):
        log.warning("沒有永豐金金鑰，行情服務待命")
    while True:
        state = svc.step() if os.environ.get("SHIOAJI_API_KEY") else "no_credentials"
        svc.write_status(state)
        time.sleep(LOOP_SEC if state == "streaming" else 30 if state in ("closed", "no_credentials") else LOOP_SEC)


if __name__ == "__main__":
    main()
