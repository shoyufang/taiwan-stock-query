"""訂閱名額規劃（永豐金上限 200 檔，保留 10 檔緩衝）。

常駐：大盤指數與預設自選股；動態：瀏覽器最近 idle_sec 秒內關注過的代號（由 API 寫入
Redis 有序集合，分數為最後關注時間）。超過上限時保留最近被關注的。
"""

from __future__ import annotations

CAP = 190


def plan(current: set[str], pinned: list[str], interest: dict[str, float], now: float,
         idle_sec: float = 300, cap: int = CAP) -> tuple[list[str], list[str]]:
    desired: list[str] = []
    for c in pinned:
        if c not in desired:
            desired.append(c)
    recent = sorted((c for c, ts in interest.items() if now - ts <= idle_sec and c not in desired),
                    key=lambda c: interest[c], reverse=True)
    desired.extend(recent[: max(cap - len(desired), 0)])
    desired = desired[:cap]
    want = set(desired)
    to_add = [c for c in desired if c not in current]
    to_remove = sorted(current - want)
    return to_add, to_remove
