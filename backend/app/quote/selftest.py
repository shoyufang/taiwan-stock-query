"""行情服務自我檢查（可在休市時執行）：登入 → 合約 → 訂閱 → 用量 → 登出。

用法（home server）：
  cd ~/apps/twstock && docker compose -f deploy/compose.yml run --rm --no-deps quote python -m app.quote.selftest
只印狀態，不印金鑰與帳戶資料。快照與排行各只查一次，符合使用規範。
"""

import os
import sys
import time

import shioaji as sj

from app.quote import normalize as nz
from app.quote.service import shioaji_factory


def main() -> int:
    ok = True
    print(f"shioaji {sj.__version__}｜模擬環境：{os.environ.get('SHIOAJI_SIMULATION', 'true')}")
    t = time.time()
    try:
        api = shioaji_factory()
    except Exception as e:
        print(f"[失敗] 登入：{type(e).__name__}: {e}")
        return 1
    print(f"[通過] 登入（{time.time() - t:.1f} 秒，含下載合約）")

    try:
        u = api.usage()
        print(f"[資訊] 連線數 {u.connections}｜今日流量 {u.bytes / 1048576:.1f} MB / 上限 {u.limit_bytes / 1048576:.0f} MB")

        events = []
        # info 可能含身分證字號：只保留訂閱頻道（QUO/... 開頭）的 info
        api.set_event_callback(lambda resp_code, event_code, info, event: events.append(
            (resp_code, event_code, info if str(info).startswith("QUO/") else "")))
        for code in ("IX0001", "2330"):
            c = api.contracts.get(code)
            if c is None:
                print(f"[失敗] 找不到合約 {code}")
                ok = False
                continue
            print(f"[通過] 合約 {code}：{getattr(c, 'name', '')}")
            api.subscribe(c, quote_type=sj.QuoteType.Quote)
        time.sleep(3)
        subs = [e for e in events if e[1] == 16]
        print(f"[{'通過' if len(subs) >= 2 else '注意'}] 訂閱回應 {len(subs)} 筆：" + "；".join(f"{e[0]} {e[2]}" for e in subs))
        if len(subs) < 2:
            ok = False

        snap = api.snapshots([api.contracts.get("2330")])
        if snap:
            s = snap[0]
            print(f"[資訊] 2330 快照：收 {s.close}，漲跌 {s.change_price}，總量 {s.total_volume} 張（模擬環境資料是否為真實行情，請與證交所比對）")

        items = api.scanners(scanner_type=sj.ScannerType.AmountRank, count=3, date="2026-10-16")
        rows = nz.from_scanner(items)
        print("[資訊] 10/16 成交金額排行前三：" + "、".join(f"{r['code']}{r['name']} {r['close']}" for r in rows))

        for code in ("IX0001", "2330"):
            api.unsubscribe(api.contracts.get(code), quote_type=sj.QuoteType.Quote)
    except Exception as e:
        print(f"[失敗] {type(e).__name__}: {e}")
        ok = False
    finally:
        api.logout()
        print("[資訊] 已登出")
    print("結果：" + ("全部通過" if ok else "有項目未通過"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
