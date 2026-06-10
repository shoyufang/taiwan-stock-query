"""
資料來源客戶端套件 — 重新匯出所有公開數據查詢函數以實現向後相容
"""

from datasources.shioaji_client import (
    ShioajiConnectionPool,
    login,
    query_scanner,
    query_snapshot,
    query_kbars,
    query_ticks,
    query_shioaji_snapshot,
    query_shioaji_kbars,
    query_shioaji_contract_info,
    query_positions,
    query_position_detail,
    query_profit_loss,
    query_profit_loss_summary,
    query_account_balance,
    query_trading_limits,
    query_margin,
    query_settlements,
    analyze_shioaji_big_orders,
)

from datasources.finmind_client import (
    FinMindConnectionPool,
    get_finmind_token,
    FINMIND_TOKEN,
    query_institutional,
    query_institutional_summary,
    query_daily_kbar_finmind,
    query_per_pbr,
    query_day_trading,
    query_margin_short,
    query_shareholding,
    query_securities_lending,
    query_month_revenue,
    query_financial_statement,
    query_financial_statements,
    query_balance_sheet,
    query_dividend,
    query_futures_daily,
    query_futures_institutional,
    query_exchange_rate,
)

from datasources.twse_client import (
    query_twse_daily_all,
    query_twse_bwibbu,
    query_twse_institutional,
    query_twse_margin,
    query_twse_company,
    query_twse_disposition,
    query_twse_notice,
)

from datasources.futu_client import (
    query_futu_market_state,
    query_futu_kbar,
    query_futu_basicinfo,
    query_futu_capital_distribution,
    query_futu_capital_flow,
    _futu_to_yf,
    query_futu_plate_list,
    query_futu_plate_stocks,
    query_futu_owner_plate,
)

from datasources.news_client import (
    query_news,
    print_news,
    query_stock_news,
    query_market_news,
)
