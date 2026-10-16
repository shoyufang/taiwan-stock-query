import json
import time
from unittest.mock import patch

import fakeredis
from fastapi.testclient import TestClient

from app import main


def test_ws_sends_last_then_relays_live():
    server = fakeredis.FakeServer()
    async_rds = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    sync_rds = fakeredis.FakeRedis(server=server, decode_responses=True)
    sync_rds.set("q:last:2330", json.dumps({"code": "2330", "close": 2420}))

    with patch.object(main.cache, "make_client", return_value=async_rds), TestClient(main.app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"op": "subscribe", "codes": ["2330", "bad code!"]}))
            assert json.loads(ws.receive_text()) == {"code": "2330", "close": 2420}
            assert sync_rds.zscore("quote:interest", "2330") is not None
            assert sync_rds.zscore("quote:interest", "bad code!") is None
            ws.send_text(json.dumps({"op": "subscribe", "codes": ["ALERTS", "SCANNER"]}))
            time.sleep(0.2)
            assert sync_rds.zscore("quote:interest", "ALERTS") is None  # 不是股票，不交給行情服務

            time.sleep(0.3)
            sync_rds.publish("q:2330", json.dumps({"code": "2330", "close": 2425}))
            assert json.loads(ws.receive_text())["close"] == 2425
