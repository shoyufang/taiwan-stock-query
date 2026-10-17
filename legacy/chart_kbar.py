"""
K 線圖工具：查詢分鐘 K → resample 成日 K → 畫蠟燭圖
用法：python chart_kbar.py [代號] [開始日期] [結束日期]
範例：python chart_kbar.py 2330 2026-01-01 2026-04-28
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import mplfinance as mpf
from sinopac_query import login

sys.stdout.reconfigure(encoding="utf-8")


def fetch_daily_kbar(code: str, start: str, end: str) -> pd.DataFrame:
    """取得日 K（從分鐘 K resample）"""
    print(f"正在下載 {code} 分鐘 K 資料（{start} ~ {end}）...")
    api = login(fetch_contract=True)
    contract = api.Contracts.Stocks[code]
    kbars = api.kbars(contract, start=start, end=end)
    api.logout()

    df = pd.DataFrame({**kbars})
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df.index = df.index.tz_localize("Asia/Taipei")

    # resample 分鐘 K → 日 K
    daily = df.resample("1D").agg({
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }).dropna()

    print(f"共 {len(daily)} 個交易日")
    return daily


def plot_kbar(code: str, start: str, end: str):
    daily = fetch_daily_kbar(code, start, end)

    # 台股：漲為紅，跌為綠
    mc = mpf.make_marketcolors(
        up="red", down="green",
        edge="inherit",
        wick="inherit",
        volume={"up": "red", "down": "green"},
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridstyle="--",
        gridcolor="#e0e0e0",
        facecolor="white",
        figcolor="white",
    )

    # 計算 MA5 / MA20 / MA60
    ma5  = daily["Close"].rolling(5).mean()
    ma20 = daily["Close"].rolling(20).mean()
    ma60 = daily["Close"].rolling(60).mean()

    add_plots = [
        mpf.make_addplot(ma5,  color="orange", width=1.0),
        mpf.make_addplot(ma20, color="blue",   width=1.0),
        mpf.make_addplot(ma60, color="purple", width=1.2),
    ]

    fig, axes = mpf.plot(
        daily,
        type="candle",
        style=style,
        title=f"\n{code} 日 K 線圖（{start} ~ {end}）",
        ylabel="價格（元）",
        volume=True,
        ylabel_lower="成交量（張）",
        addplot=add_plots,
        figsize=(14, 8),
        returnfig=True,
    )

    # 手動建圖例（避免被蠟燭圖色塊污染）
    import matplotlib.lines as mlines
    leg_ma5  = mlines.Line2D([], [], color="orange", linewidth=1.0, label="MA5")
    leg_ma20 = mlines.Line2D([], [], color="blue",   linewidth=1.0, label="MA20")
    leg_ma60 = mlines.Line2D([], [], color="purple", linewidth=1.2, label="MA60")
    axes[0].legend(handles=[leg_ma5, leg_ma20, leg_ma60], loc="upper left", fontsize=9, framealpha=0.7)

    out_path = f"{code}_daily_kbar.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"圖表已儲存：{out_path}")
    mpf.show()


if __name__ == "__main__":
    args = sys.argv[1:]
    code  = args[0] if len(args) > 0 else "2330"
    start = args[1] if len(args) > 1 else "2026-01-01"
    end   = args[2] if len(args) > 2 else "2026-04-28"
    plot_kbar(code, start, end)
