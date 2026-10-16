"""新網站 API 入口（FastAPI）。"""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import cache
from app.settings import load_settings
from app.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.redis = cache.make_client(settings.redis_url)
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(title="台股看盤 API", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(ws_router)


WORKER_STALE_SEC = 30 * 60


def worker_state(status_raw: str | None, now: datetime) -> str:
    """starting：尚未跑過；ok：最近一次成功且 30 分鐘內；error：最近一次失敗；stale：太久沒更新。"""
    if not status_raw:
        return "starting"
    st = json.loads(status_raw)
    if (now - datetime.fromisoformat(st["at"])).total_seconds() > WORKER_STALE_SEC:
        return "stale"
    return "ok" if st.get("ok") else "error"


QUOTE_STALE_SEC = 120


def quote_state(status_raw: str | None, now: datetime) -> str:
    """行情服務狀態。closed／no_credentials 屬正常待命；login_failed、error 或狀態逾 2 分鐘未更新視為異常。"""
    if not status_raw:
        return "starting"
    st = json.loads(status_raw)
    if (now - datetime.fromisoformat(st["at"])).total_seconds() > QUOTE_STALE_SEC:
        return "stale"
    state = st.get("state", "unknown")
    return "error" if state in ("login_failed", "error") else state


@app.get("/api/health")
async def health():
    """服務健康狀態。任一必要元件異常回 503，供 Uptime Kuma 判斷。"""
    settings = app.state.settings
    now = datetime.now(ZoneInfo(settings.tz))
    redis_ok = await cache.ping(app.state.redis)
    worker = worker_state(await app.state.redis.get("overview:status"), now) if redis_ok else "unknown"
    quote = quote_state(await app.state.redis.get("quote:status"), now) if redis_ok else "unknown"
    healthy = redis_ok and worker in ("ok", "starting") and quote not in ("error", "stale")
    body = {
        "status": "ok" if healthy else "degraded",
        "version": settings.app_version,
        "time": now.isoformat(timespec="seconds"),
        "components": {"api": "ok", "redis": "ok" if redis_ok else "down", "worker": worker, "quote": quote},
    }
    return JSONResponse(body, status_code=200 if healthy else 503)


@app.get("/api/market/overview")
async def market_overview():
    """市場總覽（盤後）。由 worker 預先計算存在 Redis，這裡只讀取。"""
    raw = await app.state.redis.get("overview:latest")
    if not raw:
        status = await app.state.redis.get("overview:status")
        return JSONResponse({"status": "preparing", "detail": json.loads(status) if status else None}, status_code=503)
    return JSONResponse(json.loads(raw), headers={"Cache-Control": "no-cache"})
