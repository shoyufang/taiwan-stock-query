"""
行事曆引擎共用樣板（R2 重構，2026-07-08）

tw_calendar.py 與 us_calendar.py 原本各自複製貼上同一段「平行抓取股票池 +
24 小時 SQLite 快取」邏輯（142 行 vs 137 行近乎攣生），本檔抽出共用部分：
ThreadPoolExecutor 平行下載 + 快取讀寫 + 統一 log 格式。

各市場專屬的抓取函式（_fetch_single_tw_calendar_consensus /
_fetch_single_calendar_consensus）與資料欄位仍留在各自檔案，因為兩市場
回傳的 DataFrame schema 本來就不同（美股多分析師評等/目標價欄位），
沒有必要也不該勉強統一成同一組欄位。
"""

import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging_config import main_logger
from sqlite_cache import get_cache, set_cache


def fetch_consensus_pool(pool: list, fetch_fn, cache_key: str, log_label: str,
                          force_refresh: bool = False, max_workers: int = 10) -> pd.DataFrame:
    """
    平行抓取股票池資料 + 24 小時 SQLite 永久快取（TTL: 86400 秒）。

    pool: 股票代號/ticker 清單
    fetch_fn: callable(item) -> Optional[dict]，單檔抓取函式
    cache_key: SQLite 快取鍵
    log_label: log 訊息用的中文標籤（例："台股日曆"、"美股日曆與共識"）
    """
    ttl_seconds = 86400

    if not force_refresh:
        cached_df = get_cache(cache_key)
        if isinstance(cached_df, pd.DataFrame) and not cached_df.empty:
            main_logger.info(f"成功從 SQLite 快取讀取{log_label}數據")
            return cached_df

    main_logger.info(f"{log_label}快取失效，啟動並行抓取數據...")
    results = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_fn, item): item for item in pool}
        for future in as_completed(futures):
            item = futures[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception as exc:
                main_logger.error(f"{log_label}線程 {item} 產生異常: {exc}")

    main_logger.info(f"{log_label}並行下載完成，費時: {time.time() - start_time:.2f} 秒，共取得 {len(results)} 檔數據")

    if not results:
        main_logger.warning(f"所有{log_label}下載均失敗，回傳空 DataFrame")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    set_cache(cache_key, df, ttl=ttl_seconds)
    return df
