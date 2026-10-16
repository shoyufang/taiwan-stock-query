"""證券櫃檯買賣中心 OpenAPI（https://www.tpex.org.tw/openapi/）。"""

from __future__ import annotations

import httpx

BASE = "https://www.tpex.org.tw/openapi/v1"


async def _get(client: httpx.AsyncClient, path: str) -> list[dict]:
    r = await client.get(f"{BASE}/{path}", headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 twstock"})
    r.raise_for_status()
    return r.json()


async def disposal(client: httpx.AsyncClient) -> list[dict]:
    return await _get(client, "tpex_disposal_information")


async def warning(client: httpx.AsyncClient) -> list[dict]:
    return await _get(client, "tpex_trading_warning_information")
