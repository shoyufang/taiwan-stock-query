"""
Tabs 子模組 — 為未來拆分 app.py 做準備

目前階段：保持向後相容，從 app.py 匯入所有 render 函數
未來階段：逐步將 render 函數遷移到各自的子模組
"""

# 向後相容：從 app.py 匯入所有 render 函數
# 這樣其他模組可以從 tabs 匯入，而不需要直接依賴 app.py

def _import_from_app():
    """延遲匯入，避免循環依賴"""
    import app
    return {
        'render_dashboard': app.render_dashboard,
        'render_dashboard_fragment': app.render_dashboard_fragment,
        'render_taistock_market': app.render_taistock_market,
        'render_twse_section': app.render_twse_section,
        'render_finmind': app.render_finmind,
        'render_futures_forex': app.render_futures_forex,
        'render_us_stocks': app.render_us_stocks,
        'render_hk_us_stocks': app.render_hk_us_stocks,
        'render_news': app.render_news,
        'render_tools': app.render_tools,
        'render_deepseek_chat': app.render_deepseek_chat,
        'render_us_calendar_consensus': app.render_us_calendar_consensus,
        'render_us_screener': app.render_us_screener,
        'render_screener': app.render_screener,
        'render_technical_analysis': app.render_technical_analysis,
        'render_snapshot_fragment': app.render_snapshot_fragment,
    }

# 建立模組級別的匯入
_globals = _import_from_app()
for _name, _func in _globals.items():
    globals()[_name] = _func
