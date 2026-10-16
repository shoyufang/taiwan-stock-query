from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import main


class _FakeRedis:
    store: dict = {}

    async def aclose(self):
        pass

    async def get(self, key):
        return self.store.get(key)


@pytest.fixture
def client_factory():
    def make(redis_ok: bool):
        patches = [
            patch.object(main.cache, "make_client", return_value=_FakeRedis()),
            patch.object(main.cache, "ping", AsyncMock(return_value=redis_ok)),
        ]
        for p in patches:
            p.start()
        client = TestClient(main.app)
        client.__enter__()
        return client, patches
    created = []

    def factory(redis_ok: bool):
        c, ps = make(redis_ok)
        created.append((c, ps))
        return c

    yield factory
    for c, ps in created:
        c.__exit__(None, None, None)
        for p in ps:
            p.stop()


def test_health_ok_when_redis_up(client_factory):
    _FakeRedis.store = {}
    r = client_factory(True).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["components"] == {"api": "ok", "redis": "ok", "worker": "starting"}
    assert body["time"].endswith("+08:00")


def test_health_503_when_worker_failed(client_factory):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    _FakeRedis.store = {"overview:status": '{"ok": false, "error": "x", "at": "%s"}' % now}
    r = client_factory(True).get("/api/health")
    assert r.status_code == 503 and r.json()["components"]["worker"] == "error"
    _FakeRedis.store = {}


def test_worker_state_rules():
    from datetime import datetime
    now = datetime.fromisoformat("2026-10-17T00:30:00+08:00")
    assert main.worker_state(None, now) == "starting"
    assert main.worker_state('{"ok": true, "at": "2026-10-17T00:20:00+08:00"}', now) == "ok"
    assert main.worker_state('{"ok": true, "at": "2026-10-16T23:50:00+08:00"}', now) == "stale"
    assert main.worker_state('{"ok": false, "at": "2026-10-17T00:25:00+08:00"}', now) == "error"


def test_overview_503_while_preparing(client_factory):
    _FakeRedis.store = {}
    r = client_factory(True).get("/api/market/overview")
    assert r.status_code == 503 and r.json()["status"] == "preparing"


def test_overview_returns_precomputed(client_factory):
    _FakeRedis.store = {"overview:latest": '{"asof": "2026-10-16", "headline": "測試"}'}
    r = client_factory(True).get("/api/market/overview")
    assert r.status_code == 200 and r.json()["asof"] == "2026-10-16"
    _FakeRedis.store = {}


def test_health_503_when_redis_down(client_factory):
    r = client_factory(False).get("/api/health")
    assert r.status_code == 503
    assert r.json()["components"]["redis"] == "down"
