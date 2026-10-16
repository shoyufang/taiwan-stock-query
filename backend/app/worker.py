"""排程與預先計算（獨立容器：python -m app.worker）。

每 10 分鐘重算市場總覽並寫入 Redis；API 只讀 Redis，打開頁面即回。
失敗時保留上一份成功的資料，並把錯誤寫到 overview:status。
"""

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app import cache
from app.services import overview as ov
from app.services import attention as att
from app.services import calendar as cal
from app.services import global_mkt
from app.services import screener as sc
from app.services import us_stocks
from app.settings import load_settings
from app.sources import mops, tpex, twse, yahoo

log = logging.getLogger("worker")
TZ = ZoneInfo("Asia/Taipei")
INTERVAL_SEC = 600
SERIES_MONTHS = 6

KEY_OVERVIEW = "overview:latest"
KEY_SCREENER = "screener:base"
KEY_GLOBAL = "global:latest"
KEY_US = "us:latest"
KEY_CALENDAR = "calendar:latest"
KEY_ATTENTION = "attention:latest"
CALENDAR_EVERY = timedelta(hours=6)  # MOPS 有防爬限制，不要頻繁抓
US_EVERY = timedelta(minutes=30)
SCREENER_DAYS = 10
TECH_DAYS = 60
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


async def t86_history(client, rds, dates: list[str], asof_raw: dict) -> list[dict]:
    """最近幾個交易日的 T86（由舊到新，最後一筆為 asof）。過去日期不會再變，快取 30 天。"""
    out = []
    for d in dates[:-1]:
        key = f"twse:t86:{d}"
        cached = await rds.get(key)
        if cached:
            out.append(json.loads(cached))
            continue
        raw = await twse.t86(client, date.fromisoformat(d))
        if raw.get("stat") == "OK" and raw.get("data"):
            await rds.set(key, json.dumps(raw, ensure_ascii=False), ex=30 * 86400)
            out.append(raw)
    out.append(asof_raw)
    return out


async def ohlcv_history(client, rds, dates: list[str], asof_mi: dict) -> list[dict[str, dict]]:
    """最近 60 個交易日的普通股精簡 OHLCV（由舊到新，最後一筆為 asof）。過去日期快取 90 天。"""
    by_date: dict[str, dict[str, dict]] = {}
    missing: list[str] = []
    for d in dates[:-1]:
        cached = await rds.get(f"twse:ohlcv:{d}")
        if cached:
            by_date[d] = json.loads(cached)
        else:
            missing.append(d)
    # 由近到遠補抓尚未快取的日期（單輪最多補 25 天、間隔 0.6s，避免觸發證交所 307 限流）
    for d in reversed(missing[-25:]):
        try:
            raw = await twse.mi_index(client, date.fromisoformat(d))
            if ov.has_trading_data(raw):
                parsed = sc.parse_mi_ohlcv(raw)
                await rds.set(f"twse:ohlcv:{d}", json.dumps(parsed, separators=(",", ":")), ex=90 * 86400)
                by_date[d] = parsed
            await asyncio.sleep(0.6)
        except Exception as e:
            log.warning("回補 %s OHLCV 暫停（下一輪續補）：%s", d, e)
            break
    out = [by_date[d] for d in dates[:-1] if d in by_date]
    out.append(sc.parse_mi_ohlcv(asof_mi))
    return out



async def monthly_rev_map(client, rds) -> dict[str, dict]:
    cached = await rds.get("twse:rev_latest")
    if cached:
        return json.loads(cached)
    try:
        rows = await twse.monthly_revenue(client)
        parsed = sc.parse_monthly_revenue(rows)
        if parsed:
            await rds.set("twse:rev_latest", json.dumps(parsed, ensure_ascii=False), ex=6 * 3600)
        return parsed
    except Exception as e:
        log.warning("月營收彙總表抓取失敗：%s", e)
        return {}


async def industry_map(rds) -> dict[str, str]:
    cached = await rds.get("finmind:industry")
    if cached:
        return json.loads(cached)
    from app.services.stock import pick_profile
    from app.sources import finmind
    async with finmind.make_client(os.environ.get("FINMIND_TOKEN", "")) as fm:
        info = await finmind.fetch(fm, "TaiwanStockInfo")
    codes = {r["stock_id"] for r in info}
    mapping = {c: p["industry"] for c in codes if (p := pick_profile(info, c))}
    await rds.set("finmind:industry", json.dumps(mapping, ensure_ascii=False), ex=86400)
    return mapping


async def tpex_index_on(asof: date) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            rows = await tpex.index_history(client)
        return ov.parse_tpex_index(rows, asof)
    except Exception as e:
        log.warning("TPEx 櫃買指數抓取失敗：%s", e)
        return None


async def refresh_tdcc(rds) -> dict[str, dict] | None:
    if await rds.get("tdcc:checked"):
        return None
    from app.services import stock as st
    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
        csv_text = await tpex.tdcc_holding_csv(client)
    parsed = st.parse_tdcc_csv(csv_text)
    if parsed:
        await rds.set("tdcc:latest", json.dumps(parsed, ensure_ascii=False, separators=(",", ":")), ex=7 * 86400)
        await rds.set("tdcc:checked", "1", ex=12 * 3600)
        log.info("集保股權分散表已更新：%d 檔", len(parsed))
    return parsed


async def refresh_overview(rds) -> dict:
    now = datetime.now(TZ)
    async with twse.make_client() as client:
        asof, mi, t = await find_asof(client, now.date())
        series = await index_series(client, rds, asof)
        intl, tpex_idx = await asyncio.gather(international(asof), tpex_index_on(asof))
        data = ov.build_overview(asof, mi, t, series, intl, now.isoformat(timespec="seconds"), tpex_index=tpex_idx)
        await rds.set(KEY_OVERVIEW, json.dumps(data, ensure_ascii=False))
        # 選股總表：沿用同一天的 MI_INDEX 與 T86，加上本益比、最近 10 日法人、近 60 日技術指標與月營收 YoY
        try:
            all_days = [p["date"] for p in series if p["date"] <= asof.isoformat()]
            t86_days = await t86_history(client, rds, all_days[-SCREENER_DAYS:], t)
            ohlcv_days = await ohlcv_history(client, rds, all_days[-TECH_DAYS:], mi)
            bw = await twse.bwibbu(client, asof)
            revs = await monthly_rev_map(client, rds)
            base = sc.build_base(asof.isoformat(), mi, t86_days, bw, await industry_map(rds),
                                 now.isoformat(timespec="seconds"), ohlcv_days=ohlcv_days, rev_map=revs)
            await rds.set(KEY_SCREENER, json.dumps(base, ensure_ascii=False))
        except Exception:
            log.exception("選股總表更新失敗（市場總覽不受影響）")
    try:
        await refresh_tdcc(rds)
    except Exception:
        log.exception("集保股權分散表更新失敗（市場總覽不受影響）")
    try:
        g = await global_mkt.build(now.isoformat(timespec="seconds"))
        await rds.set(KEY_GLOBAL, json.dumps(g, ensure_ascii=False))
    except Exception:
        log.exception("全球市場更新失敗（市場總覽不受影響）")
    try:
        await refresh_us(rds, now)
    except Exception:
        log.exception("美股選股與財報日曆更新失敗（市場總覽不受影響）")
    try:
        await refresh_attention(rds, asof, now)
    except Exception:
        log.exception("處置／注意股更新失敗（市場總覽不受影響）")
    try:
        await refresh_calendar(rds, now)
    except Exception:
        log.exception("行事曆更新失敗（市場總覽不受影響）")
    return data


async def refresh_us(rds, now: datetime, force: bool = False) -> dict | None:
    old = await rds.get(KEY_US)
    if old and not force:
        prev = json.loads(old)
        if now - datetime.fromisoformat(prev["generated_at"]) < US_EVERY:
            return None
    data = await us_stocks.fetch_and_build(now.date(), now.isoformat(timespec="seconds"))
    if data["rows"]:
        await rds.set(KEY_US, json.dumps(data, ensure_ascii=False))
        log.info("美股選股與財報日曆已更新：%d 檔", len(data["rows"]))
    return data


async def refresh_attention(rds, asof: date, now: datetime) -> dict:
    async with twse.make_client() as client:
        punish = await twse.punish(client, asof - timedelta(days=30), asof)
        notice = await twse.notice(client, asof)
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        tp_disposal, tp_warning = await tpex.disposal(client), await tpex.warning(client)
    data = att.build(asof, now.date(), att.twse_disposition(punish) + att.tpex_disposition(tp_disposal),
                     att.twse_notice(notice) + att.tpex_notice(tp_warning, asof), now.isoformat(timespec="seconds"))
    await rds.set(KEY_ATTENTION, json.dumps(data, ensure_ascii=False))
    return data


async def refresh_calendar(rds, now: datetime, force: bool = False) -> dict | None:
    old = await rds.get(KEY_CALENDAR)
    if old and not force:
        prev = json.loads(old)
        if now - datetime.fromisoformat(prev["generated_at"]) < CALENDAR_EVERY and prev["today"] == now.date().isoformat():
            return None
    async with twse.make_client() as client:
        dividends = cal.parse_twt48u(await twse.twt48u(client))
    first = now.date().replace(day=1)
    months = [first, (first + timedelta(days=32)).replace(day=1)]
    rows = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers={"User-Agent": "Mozilla/5.0 twstock"}) as client:
        for m in months:
            for market in ("sii", "otc"):
                try:
                    rows += mops.parse_conferences(await mops.conferences(client, m.year - 1911, m.month, market))
                except Exception:
                    log.warning("法說會抓取失敗：%s %s/%s", market, m.year, m.month, exc_info=True)
                await asyncio.sleep(2)
    data = cal.build(now.date(), dividends, cal.conference_events(rows), now.isoformat(timespec="seconds"))
    await rds.set(KEY_CALENDAR, json.dumps(data, ensure_ascii=False))
    log.info("行事曆已更新：%d 筆", len(data["events"]))
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
