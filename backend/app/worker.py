"""排程與預先計算（獨立容器：python -m app.worker）。

每 10 分鐘重算市場總覽並寫入 Redis；API 只讀 Redis，打開頁面即回。
失敗時保留上一份成功的資料，並把錯誤寫到 overview:status。
"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import cache
from app.services import overview as ov
from app.settings import load_settings
from app.sources import twse, yahoo

log = logging.getLogger("worker")
TZ = ZoneInfo("Asia/Taipei")
INTERVAL_SEC = 600
SERIES_MONTHS = 6

KEY_OVERVIEW = "overview:latest"
KEY_STATUS = "overview:status"
KEY_FMTQIK = "twse:fmtqik:{ym}"

# (顯示名稱, Yahoo 代號, 日期規則)：美股取「台股該日開盤前已收盤」的交易日；匯率取當日或之前
INTERNATIONAL = [
    ("費城半導體", "^SOX", "before"),
    ("那斯達克", "^IXIC", "before"),
    ("標普 500", "^GSPC", "before"),
    ("台積電 ADR", "TSM", "before"),
    ("美元 / 台幣", "TWD=X", "inclusive"),
]


async def find_asof(client, today: date) -> tuple[date, dict, dict]:
    """往回找最近一個「MI_INDEX 與 T86 都已公布」的交易日。"""
    for back in range(0, 12):
        d = today - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        mi = await twse.mi_index(client, d)
        if not ov.has_trading_data(mi):
            continue
        t = await twse.t86(client, d)
        if t.get("stat") == "OK" and t.get("data"):
            return d, mi, t
        log.info("%s MI_INDEX 已有、T86 尚未公布，往前一天", d)
    raise RuntimeError("近 12 天找不到同時有 MI_INDEX 與 T86 的交易日")


def _months(asof: date, n: int) -> list[date]:
    y, m = asof.year, asof.month
    out = []
    for _ in range(n + 1):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


async def index_series(client, rds, asof: date) -> list[dict]:
    series = []
    for first in _months(asof, SERIES_MONTHS):
        key = KEY_FMTQIK.format(ym=first.strftime("%Y%m"))
        current_month = first.year == asof.year and first.month == asof.month
        cached = None if current_month else await rds.get(key)
        if cached:
            rows = json.loads(cached)
        else:
            rows = ov.parse_fmtqik(await twse.fmtqik(client, first))
            if not current_month and rows:
                await rds.set(key, json.dumps(rows), ex=60 * 86400)
        series.extend(rows)
    cutoff = (asof - timedelta(days=183)).isoformat()
    return [p for p in series if p["date"] >= cutoff]


async def international(asof: date) -> list[dict]:
    out = []
    async with yahoo.make_client() as client:
        for name, symbol, rule in INTERNATIONAL:
            try:
                bars = yahoo.parse_bars(await yahoo.daily_bars(client, symbol))
                pair = yahoo.last_before(bars, asof, inclusive=(rule == "inclusive"))
                if not pair:
                    continue
                last, prev = pair
                out.append({"name": name, "symbol": symbol, "date": last["date"].isoformat(),
                            "close": round(last["close"], 2),
                            "change_pct": round((last["close"] - prev["close"]) / prev["close"] * 100, 2)})
            except Exception as e:  # 單一國際指標失敗不影響整頁
                log.warning("Yahoo %s 失敗：%s", symbol, e)
    return out


async def refresh_overview(rds) -> dict:
    now = datetime.now(TZ)
    async with twse.make_client() as client:
        asof, mi, t = await find_asof(client, now.date())
        series = await index_series(client, rds, asof)
    intl = await international(asof)
    data = ov.build_overview(asof, mi, t, series, intl, now.isoformat(timespec="seconds"))
    await rds.set(KEY_OVERVIEW, json.dumps(data, ensure_ascii=False))
    return data


async def run_forever() -> None:
    settings = load_settings()
    rds = cache.make_client(settings.redis_url)
    while True:
        started = datetime.now(TZ)
        try:
            data = await refresh_overview(rds)
            status = {"ok": True, "asof": data["asof"], "at": started.isoformat(timespec="seconds")}
            log.info("市場總覽已更新：asof=%s", data["asof"])
        except Exception as e:
            status = {"ok": False, "error": str(e)[:300], "at": started.isoformat(timespec="seconds")}
            log.exception("市場總覽更新失敗")
        await rds.set(KEY_STATUS, json.dumps(status, ensure_ascii=False))
        await asyncio.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_forever())
