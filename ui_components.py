"""
UI 元件和可復用組件 — 相容墊片

實作已拆分至 ui/ 套件（2026-07-07）：
  ui/display.py — 通用查詢結果顯示（display_result 等）
  ui/sidebar.py — 側邊欄導航、書籤/歷史、設定面板、輸入元件
  ui/us.py      — 美股專屬渲染
  ui/shioaji.py — 永豐金 Shioaji 專屬渲染
本檔重新匯出全部符號以維持既有 `from ui_components import X` 呼叫路徑相容。
"""

from ui.display import (
    display_result,
    display_table,
    display_kbar,
    display_ranking,
    display_financial,
    display_single_value,
)
from ui.sidebar import (
    render_sidebar_menu,
    render_search_box,
    render_bookmarks_section,
    render_history_section,
    render_settings_panel,
    date_input_section,
    code_input_section,
    us_code_input_section,
)
from ui.us import (
    render_us_company_profile,
    render_us_financials,
    render_us_holders,
    render_us_analyst_info,
    render_us_sector_performance_dashboard,
)
from ui.shioaji import (
    render_shioaji_snapshot,
    render_shioaji_contract,
    render_shioaji_big_orders,
)
