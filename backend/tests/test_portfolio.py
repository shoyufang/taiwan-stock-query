from unittest.mock import AsyncMock, patch

import fakeredis
from fastapi.testclient import TestClient

from app import main

INFO = [{"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"}]


def test_portfolio_crud_and_validation():
    rds = fakeredis.FakeAsyncRedis(decode_responses=True)
    row = {"code": "2330", "name": "台積電", "date": "2026-10-16", "close": 2420, "change": -20, "change_pct": -0.82}
    with patch.object(main.cache, "make_client", return_value=rds), \
         patch("app.services.stock_loader.stock_info", AsyncMock(return_value=INFO)), \
         patch("app.api_portfolio._row", AsyncMock(return_value=row)), \
         TestClient(main.app) as c:
        for h in c.get("/api/portfolio").json()["holdings"]:
            c.delete(f"/api/portfolio/{h['id']}")
        assert c.post("/api/portfolio", json={"code": "9999", "shares": 1000, "cost": 10}).status_code == 400
        assert c.post("/api/portfolio", json={"code": "2330", "shares": 0, "cost": 10}).status_code == 422
        assert c.post("/api/portfolio", json={"code": "2330", "shares": 10, "cost": 900, "bought_on": "2999-01-01"}).status_code == 422
        hid = c.post("/api/portfolio", json={"code": "2330", "shares": 1000, "cost": 1000.5, "bought_on": "2026-01-05"}).json()["id"]
        c.post("/api/portfolio", json={"code": "2330", "shares": 37, "cost": 2400, "note": "零股"})
        body = c.get("/api/portfolio").json()
        assert [(h["shares"], h["cost"]) for h in body["holdings"]] == [(1000, 1000.5), (37, 2400)]
        assert body["quotes"]["2330"]["close"] == 2420
        assert c.put(f"/api/portfolio/{hid}", json={"code": "2330", "shares": 2000, "cost": 990}).status_code == 200
        assert c.get("/api/portfolio").json()["holdings"][0]["shares"] == 2000
        assert c.delete(f"/api/portfolio/{hid}").status_code == 200
        assert c.delete(f"/api/portfolio/{hid}").status_code == 404
        assert c.put(f"/api/portfolio/{hid}", json={"code": "2330", "shares": 1, "cost": 1}).status_code == 404
