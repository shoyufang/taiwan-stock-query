"""FinMind REST API v4（個股歷史：日 K、除權息、法人、融資券、本益比、月營收、股票清單）。

不帶 token 也能用（流量較低）；home server 的 deploy/.env 可設 FINMIND_TOKEN 提高上限。
"""

import httpx

URL = "https://api.finmindtrade.com/api/v4/data"


def make_client(token: str = "") -> httpx.AsyncClient:
    headers = {"User-Agent": "twstock"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(timeout=httpx.Timeout(30.0), headers=headers)


class FinMindError(RuntimeError):
    pass


async def fetch(client: httpx.AsyncClient, dataset: str, data_id: str | None = None,
                start: str | None = None, end: str | None = None) -> list[dict]:
    params = {"dataset": dataset}
    if data_id:
        params["data_id"] = data_id
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    r = await client.get(URL, params=params)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != 200:
        raise FinMindError(f"{dataset}: {body.get('msg')}")
    return body.get("data") or []
