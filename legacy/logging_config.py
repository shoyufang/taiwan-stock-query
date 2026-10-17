"""
應用層日誌配置 — Phase 5.3 監控和日誌系統

提供：
- 日誌級別管理 (DEBUG, INFO, WARNING, ERROR)
- 控制檯和檔案日誌輸出
- 查詢性能追蹤
- API 調用統計
- 緩存命中率追蹤
"""

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import json

# 日誌檔案位置
LOG_DIR = Path.home() / ".app_config" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
PERF_LOG_FILE = LOG_DIR / f"performance_{datetime.now().strftime('%Y%m%d')}.log"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    設置應用層日誌系統

    level: "DEBUG" | "INFO" | "WARNING" | "ERROR"
    """
    logger = logging.getLogger("sinopac_app")

    # 避免重複設置
    if logger.handlers:
        return logger

    # 設置日誌級別
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # 日誌格式
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制檯處理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 檔案處理器（每日循環）
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=7,  # 保留 7 天
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def setup_performance_logger() -> logging.Logger:
    """設置性能日誌記錄器（獨立）"""
    logger = logging.getLogger("performance")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt='%(asctime)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    handler = logging.handlers.RotatingFileHandler(
        PERF_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=7,
        encoding='utf-8'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


# 性能追蹤類
class PerformanceTracker:
    """追蹤查詢性能和緩存命中率"""

    def __init__(self):
        self.query_times: Dict[str, List[float]] = {}  # {func_name: [times]}
        self.cache_stats: Dict[str, Dict] = {}  # {func_name: {hits, misses}}
        self.api_calls: Dict[str, int] = {}  # {api_name: count}

    def record_query_time(self, func_name: str, elapsed_ms: float):
        """記錄查詢耗時"""
        if func_name not in self.query_times:
            self.query_times[func_name] = []
        self.query_times[func_name].append(elapsed_ms)

    def record_cache_hit(self, func_name: str, is_hit: bool):
        """記錄緩存命中"""
        if func_name not in self.cache_stats:
            self.cache_stats[func_name] = {"hits": 0, "misses": 0}

        if is_hit:
            self.cache_stats[func_name]["hits"] += 1
        else:
            self.cache_stats[func_name]["misses"] += 1

    def record_api_call(self, api_name: str, count: int = 1):
        """記錄 API 調用次數"""
        if api_name not in self.api_calls:
            self.api_calls[api_name] = 0
        self.api_calls[api_name] += count

    def get_avg_query_time(self, func_name: str) -> float:
        """取得平均查詢耗時"""
        if func_name not in self.query_times or not self.query_times[func_name]:
            return 0
        return sum(self.query_times[func_name]) / len(self.query_times[func_name])

    def get_cache_hit_rate(self, func_name: str) -> float:
        """取得緩存命中率 (%)"""
        if func_name not in self.cache_stats:
            return 0
        stats = self.cache_stats[func_name]
        total = stats["hits"] + stats["misses"]
        if total == 0:
            return 0
        return (stats["hits"] / total) * 100

    def get_summary(self) -> Dict:
        """取得性能總結"""
        return {
            "query_times": {
                func: {
                    "count": len(times),
                    "min": min(times),
                    "max": max(times),
                    "avg": self.get_avg_query_time(func)
                }
                for func, times in self.query_times.items()
            },
            "cache_stats": {
                func: {
                    **stats,
                    "hit_rate": self.get_cache_hit_rate(func)
                }
                for func, stats in self.cache_stats.items()
            },
            "api_calls": self.api_calls
        }

    def save_report(self, filepath: Path = None):
        """儲存性能報告"""
        if filepath is None:
            filepath = LOG_DIR / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.get_summary(), f, indent=2, ensure_ascii=False)


# 全局追蹤器
perf_tracker = PerformanceTracker()

# 初始化日誌
main_logger = setup_logging("INFO")
perf_logger = setup_performance_logger()
