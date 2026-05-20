import shioaji as sj
import sys

API_KEY    = "<YOUR_SHIOAJI_API_KEY>"
SECRET_KEY = "<YOUR_SHIOAJI_SECRET_KEY>"

api = sj.Shioaji(simulation=True)
api.login(api_key=API_KEY, secret_key=SECRET_KEY, fetch_contract=False)

results = api.scanners(
    scanner_type=sj.constant.ScannerType.ChangePercentRank,
    ascending=True,   # True = 由大到小（漲幅最高在前）
    date="2026-04-28",
    count=10,
)

# 輸出用 UTF-8
sys.stdout.reconfigure(encoding='utf-8')

print(f"{'排名':<4} {'代號':<8} {'名稱':<10} {'漲幅%':>8} {'昨收':>8} {'開盤':>8} {'最高':>8} {'最低':>8} {'收盤':>8} {'成交量':>10}")
print("-" * 90)
for i, r in enumerate(results, 1):
    # 昨收 = 收盤 - 漲跌價
    yesterday_close = round(r.close - r.change_price, 2)
    print(f"{i:<4} {r.code:<8} {r.name:<10} {r.rank_value:>8.2f} {yesterday_close:>8} {r.open:>8} {r.high:>8} {r.low:>8} {r.close:>8} {r.total_volume:>10,}")

api.logout()
