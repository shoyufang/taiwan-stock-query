"""證交所 rwd 端點（可指定日期，官方收盤資料）。

舊站的 datasources/twse_client.py 一被 import 就會連帶載入 shioaji、FinMind，
新後端只需要這幾個端點，所以在這裡獨立實作（見架構文件 §4.2）。
TWSE 憑證缺 Subject Key Identifier，必須關閉驗證。
"""

from datetime import date

import httpx

BASE = "https://www.twse.com.tw/rwd/zh"
TIMEOUT = httpx.Timeout(20.0)


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT, verify=False,
                             headers={"User-Agent": "Mozilla/5.0 twstock"})


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


async def _get(client: httpx.AsyncClient, path: str, **params) -> dict:
    r = await client.get(path, params={"response": "json", **params})
    r.raise_for_status()
    return r.json()


async def mi_index(client: httpx.AsyncClient, d: date) -> dict:
    """單日大盤：指數、成交統計、漲跌家數、全部個股收盤行情（不含權證）。"""
    return await _get(client, "/afterTrading/MI_INDEX", date=_ymd(d), type="ALLBUT0999")


async def t86(client: httpx.AsyncClient, d: date) -> dict:
    """單日三大法人買賣超（全部證券）。"""
    return await _get(client, "/fund/T86", date=_ymd(d), selectType="ALL")


async def fmtqik(client: httpx.AsyncClient, month_first_day: date) -> dict:
    """單月每日市場成交資訊（含加權指數收盤）。"""
    return await _get(client, "/afterTrading/FMTQIK", date=_ymd(month_first_day))
