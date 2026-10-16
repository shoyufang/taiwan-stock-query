from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import main


class _FakeRedis:
    async def aclose(self):
        pass


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
    r = client_factory(True).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["components"] == {"api": "ok", "redis": "ok"}
    assert body["time"].endswith("+08:00")


def test_health_503_when_redis_down(client_factory):
    r = client_factory(False).get("/api/health")
    assert r.status_code == 503
    assert r.json()["components"]["redis"] == "down"
