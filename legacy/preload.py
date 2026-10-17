"""
資料預先加載模組 — Phase 6 Task 2
在應用啟動時後台預加載常用查詢，減少用戶等待時間
"""

import asyncio
import time
from typing import List, Dict, Any
from datetime import date, timedelta
from collections import Counter
import query_wrapper as qw
from config import load_history, load_watchlist
from logging_config import main_logger

class PreloadManager:
    """管理資料預先加載 (Phase 7 Task 7.2: 智能動態預載)"""

    def __init__(self):
        self.preload_status = {}
        self.preload_start_time = None
        self.is_preloading = False
        # 默認預加載清單
        self.frequent_queries = {
            "snapshots": ["2330", "2412", "3008", "0050"],  # 龍頭股 + ETF
            "rankings": ["up", "down", "volume"],  # 排行
            "kbars": ["2330"],  # 龍頭股 K線
        }

    def _update_frequent_queries_from_history(self):
        """根據查詢歷史或手動清單更新預加載清單 (Task 7.2 改良)"""
        try:
            # 1. 優先檢查是否有手動自選名單 (透過 config 模組)
            manual_list = load_watchlist()
            if manual_list.get("snapshots"):
                main_logger.info(f"智能預載: 偵測到手動自選名單: {manual_list['snapshots']}")
                self.frequent_queries["snapshots"] = manual_list["snapshots"]
                if manual_list.get("kbars"):
                    self.frequent_queries["kbars"] = manual_list["kbars"]
                return # 使用手動名單後直接返回

            # 2. 若無手動名單，執行原本的歷史紀錄分析
            history = load_history(limit=200)
            if not history:
                return

            codes = []
            for item in history:
                params = item.get("params", {})
                # 從單一代號參數提取
                if "code" in params and params["code"]:
                    codes.append(params["code"])
                # 從多代號列表參數提取
                if "codes" in params and isinstance(params["codes"], list):
                    codes.extend(params["codes"])
            
            if not codes:
                return

            # 統計頻率最高的 Top 5
            most_common = [code for code, count in Counter(codes).most_common(5)]
            
            if most_common:
                # 過濾出合法台股代號（4位數字或4位數字+英文後綴，排除期貨/測試代號）
                valid_codes = [c for c in most_common if c.isdigit() and len(c) <= 6]
                main_logger.info(f"智能動態預載: 根據歷史紀錄更新關注名單: {valid_codes}")
                if valid_codes:
                    self.frequent_queries["snapshots"] = list(dict.fromkeys(valid_codes + ["2330", "0050"]))[:8]
                    self.frequent_queries["kbars"] = valid_codes[:2]
                
        except Exception as e:
            main_logger.warning(f"智能更新預載清單失敗: {str(e)}")

    async def preload_snapshots(self) -> Dict[str, Any]:
        """預加載快照數據（一次查詢所有代號，避免並行 C extension 衝突）"""
        start = time.time()
        codes = self.frequent_queries["snapshots"]
        main_logger.info(f"開始預加載快照: {codes}")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: qw.query_snapshot(codes)
            )
            elapsed = (time.time() - start) * 1000
            count = len(result) if result is not None and not result.empty else 0
            main_logger.info(f"快照預加載完成: {count} 筆, 耗時 {elapsed:.1f}ms")
            self.preload_status["snapshots"] = {
                "success": True,
                "count": count,
                "elapsed_ms": elapsed
            }
            return {"snapshots": result}

        except Exception as e:
            main_logger.warning(f"快照預加載失敗: {str(e)}")
            self.preload_status["snapshots"] = {
                "success": False,
                "error": str(e)
            }
            return {}

    async def preload_rankings(self) -> Dict[str, Any]:
        """預加載排行數據（順序執行各排行類型）"""
        start = time.time()
        main_logger.info(f"開始預加載排行: {self.frequent_queries['rankings']}")
        results = []

        try:
            loop = asyncio.get_event_loop()
            for ranking_type in self.frequent_queries["rankings"]:
                r = await loop.run_in_executor(
                    None,
                    lambda rt=ranking_type: qw.query_ranking(rt, 10)
                )
                results.append(r)

            elapsed = (time.time() - start) * 1000
            main_logger.info(f"排行預加載完成: {len(results)} 筆, 耗時 {elapsed:.1f}ms")
            self.preload_status["rankings"] = {
                "success": True,
                "count": len(results),
                "elapsed_ms": elapsed
            }
            return {"rankings": results}

        except Exception as e:
            main_logger.warning(f"排行預加載失敗: {str(e)}")
            self.preload_status["rankings"] = {
                "success": False,
                "error": str(e)
            }
            return {}

    async def preload_kbars(self) -> Dict[str, Any]:
        """預加載 K 線數據（順序執行各代號）"""
        start = time.time()
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        main_logger.info(f"開始預加載 K 線: {self.frequent_queries['kbars']}")
        results = []

        try:
            loop = asyncio.get_event_loop()
            for code in self.frequent_queries["kbars"]:
                r = await loop.run_in_executor(
                    None,
                    lambda c=code: qw.query_daily_kbar(c, start_date, end_date)
                )
                results.append(r)

            elapsed = (time.time() - start) * 1000
            main_logger.info(f"K 線預加載完成: {len(results)} 筆, 耗時 {elapsed:.1f}ms")
            self.preload_status["kbars"] = {
                "success": True,
                "count": len(results),
                "elapsed_ms": elapsed
            }
            return {"kbars": results}

        except Exception as e:
            main_logger.warning(f"K 線預加載失敗: {str(e)}")
            self.preload_status["kbars"] = {
                "success": False,
                "error": str(e)
            }
            return {}

    async def run_all_preloads(self):
        """執行所有預加載任務"""
        self.is_preloading = True
        self.preload_start_time = time.time()

        main_logger.info("=" * 60)
        main_logger.info("開始預加載常用數據 (智能模式)...")
        main_logger.info("=" * 60)

        try:
            # 1. 先更新清單
            self._update_frequent_queries_from_history()

            # 2. 順序執行所有預加載任務（避免並行呼叫 C extension 造成 segfault）
            results = []
            for task_coro in [
                self.preload_rankings(),
                self.preload_snapshots(),
                self.preload_kbars(),
            ]:
                r = await task_coro
                results.append(r)

            total_time = (time.time() - self.preload_start_time) * 1000
            successful = sum(1 for status in self.preload_status.values() if status.get("success"))
            total_tasks = len(self.preload_status)

            main_logger.info("=" * 60)
            main_logger.info(f"預加載完成: {successful}/{total_tasks} 成功, 總耗時 {total_time:.1f}ms")
            main_logger.info("=" * 60)

            self.is_preloading = False
            return results

        except Exception as e:
            main_logger.error(f"預加載過程中出錯: {str(e)}")
            self.is_preloading = False
            return None

    def get_status(self) -> Dict[str, Any]:
        """獲取預加載狀態"""
        return {
            "is_preloading": self.is_preloading,
            "start_time": self.preload_start_time,
            "status": self.preload_status
        }

    def get_status_summary(self) -> str:
        """獲取預加載狀態摘要（用於 UI）"""
        if self.is_preloading:
            return "⏳ 正在預加載數據..."

        if not self.preload_status:
            return "⚪ 未預加載"

        successful = sum(1 for s in self.preload_status.values() if s.get("success"))
        total = len(self.preload_status)

        if successful == total:
            return f"✅ 預加載完成 ({total}/{total})"
        else:
            return f"⚠️ 部分預加載失敗 ({successful}/{total})"


# 全局預加載管理器
preload_manager = PreloadManager()


def start_preload_background():
    """在後台啟動預加載任務（用於 Streamlit）"""
    main_logger.info("嘗試在後台啟動預加載...")

    try:
        # 嘗試獲取當前事件循環
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果沒有事件循環，創建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 檢查事件循環是否正在運行
        if loop.is_running():
            # Streamlit 環境中事件循環已運行，無法執行
            # 改用同步方式（非最優，但可行）
            main_logger.warning("事件循環已運行，改用同步預加載")
            # 同步執行（會阻塞，但必要時）
            loop.run_until_complete(preload_manager.run_all_preloads())
        else:
            # 事件循環未運行，直接執行
            loop.run_until_complete(preload_manager.run_all_preloads())

    except Exception as e:
        main_logger.error(f"預加載啟動失敗: {str(e)}", exc_info=True)


def get_preload_status() -> Dict[str, Any]:
    """獲取預加載狀態"""
    return preload_manager.get_status()


def get_preload_summary() -> str:
    """獲取預加載狀態摘要"""
    return preload_manager.get_status_summary()
