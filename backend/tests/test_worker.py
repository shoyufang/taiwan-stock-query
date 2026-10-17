from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app import worker

MI_OK = {"stat": "OK", "tables": [{"title": "每日收盤行情(全部)", "data": [["2330"]]}]}
MI_NONE = {"stat": "很抱歉，沒有符合條件的資料!", "tables": []}
T86_OK = {"stat": "OK", "data": [["2330"]]}
T86_NONE = {"stat": "很抱歉，沒有符合條件的資料!", "data": []}


@pytest.mark.asyncio
async def test_find_asof_skips_weekend_and_missing_t86():
    # 2026-10-19（一）MI 有但 T86 未公布 → 跳過；10/17、10/18 為週末 → 跳過；10/16（五）兩者都有
    async def mi(client, d):
        return MI_OK if d in (date(2026, 10, 19), date(2026, 10, 16)) else MI_NONE

    async def t86(client, d):
        return T86_OK if d == date(2026, 10, 16) else T86_NONE

    with patch.object(worker.twse, "mi_index", AsyncMock(side_effect=mi)) as m_mi, \
         patch.object(worker.twse, "t86", AsyncMock(side_effect=t86)):
        asof, _, _ = await worker.find_asof(None, date(2026, 10, 19))
    assert asof == date(2026, 10, 16)
    called = [c.args[1] for c in m_mi.call_args_list]
    assert date(2026, 10, 17) not in called and date(2026, 10, 18) not in called


def test_months_span():
    assert worker._months(date(2026, 10, 16), 6)[0] == date(2026, 4, 1)
    assert worker._months(date(2026, 2, 3), 2) == [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]
