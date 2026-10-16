import json
from pathlib import Path

from app.services import fundamentals as fu

FIX = Path(__file__).parent / "fixtures"


def rows(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["data"]


def test_income_quarters_single_quarter_and_margins():
    q = fu.income_quarters(rows("finmind_TaiwanStockFinancialStatements_2330"))
    last = q[-1]
    assert last["quarter"] == "2026Q2" and last["revenue"] == 1270380250000.0  # ＝4～6 月營收合計
    assert last["eps"] == 27.25 and last["gross_margin"] == round(860310695000 / 1270380250000 * 100, 2)
    assert last["revenue_yoy"] is not None
    assert fu.eps_ttm(q) is not None


def test_bank_has_no_gross_profit():
    q = fu.income_quarters(rows("finmind_TaiwanStockFinancialStatements_2881"))
    assert q[-1]["gross_margin"] is None and q[-1]["eps"] is not None


def test_balance_and_dividends():
    b = fu.balance_quarters(rows("finmind_TaiwanStockBalanceSheet_2330"))
    assert b[-1]["quarter"] == "2026Q2" and 0 < b[-1]["debt_ratio"] < 100 and b[-1]["book_value_per_share"] > 0
    inc = fu.income_quarters(rows("finmind_TaiwanStockFinancialStatements_2330"), 40)
    d = fu.dividend_years(rows("finmind_TaiwanStockDividend_2330"), inc)
    y2025 = next(x for x in d if x["year"] == 2025)
    assert y2025["times"] == 4 and y2025["eps"] is not None and y2025["payout"] is not None
