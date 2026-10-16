"""新網站 API 入口（FastAPI）。"""

from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import cache
from app.settings import load_settings


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


@app.get("/api/health")
async def health():
    """服務健康狀態。任一必要元件異常回 503，供 Uptime Kuma 判斷。"""
    settings = app.state.settings
    redis_ok = await cache.ping(app.state.redis)
    body = {
        "status": "ok" if redis_ok else "degraded",
        "version": settings.app_version,
        "time": datetime.now(ZoneInfo(settings.tz)).isoformat(timespec="seconds"),
        "components": {"api": "ok", "redis": "ok" if redis_ok else "down"},
    }
    return JSONResponse(body, status_code=200 if redis_ok else 503)
