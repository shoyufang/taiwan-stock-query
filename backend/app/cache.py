"""Redis 存取。P0 只提供連線與健康檢查，之後放熱資料與即時行情 pub/sub。"""

import redis.asyncio as redis


def make_client(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


async def ping(client: redis.Redis) -> bool:
    try:
        return bool(await client.ping())
    except Exception:
        return False
