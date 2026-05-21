import shioaji as sj

# ============================================================
# 填入你的 API Key（從永豐金後台取得）
API_KEY    = "<YOUR_SHIOAJI_API_KEY>"
SECRET_KEY = "<YOUR_SHIOAJI_SECRET_KEY>"
# ============================================================

def main():
    # 1. 初始化（模擬環境）
    api = sj.Shioaji(simulation=True)

    # 2. 登入
    accounts = api.login(api_key=API_KEY, secret_key=SECRET_KEY)
    print("登入成功，帳戶列表：")
    for acc in accounts:
        print(f"  {acc}")

    import time

    # 確認簽署狀態
    print(f"\n股票帳戶 signed: {api.stock_account.signed if api.stock_account else 'N/A'}")
    print(f"期貨帳戶 signed: {api.futopt_account.signed if api.futopt_account else '無期貨帳戶'}")

    # 3. 股票下單測試（台新金 2890，限價，1張）
    if api.stock_account:
        stock_contract = api.Contracts.Stocks.TSE["2890"]
        stock_order = api.Order(
            price=18,
            quantity=1,
            action=sj.constant.Action.Buy,
            price_type=sj.constant.StockPriceType.LMT,
            order_type=sj.constant.OrderType.ROD,
            account=api.stock_account,
        )
        stock_trade = api.place_order(stock_contract, stock_order)
        print(f"\n股票下單結果：{stock_trade}")
        time.sleep(2)
    else:
        print("\n無股票帳戶，跳過股票下單")

    # 4. 期貨下單測試（台指期近月，限價，1口）
    if api.futopt_account:
        futures_contract = min(
            [x for x in api.Contracts.Futures.TXF if x.code[-2:] not in ["R1", "R2"]],
            key=lambda x: x.delivery_date,
        )
        futures_order = api.Order(
            action=sj.constant.Action.Buy,
            price=15000,
            quantity=1,
            price_type=sj.constant.FuturesPriceType.LMT,
            order_type=sj.constant.OrderType.ROD,
            octype=sj.constant.FuturesOCType.Auto,
            account=api.futopt_account,
        )
        futures_trade = api.place_order(futures_contract, futures_order)
        print(f"期貨下單結果：{futures_trade}")
    else:
        print("無期貨帳戶，跳過期貨下單")

    # 5. 登出
    api.logout()
    print("\n測試完成，已登出。")


if __name__ == "__main__":
    main()
