"""
健康檢查模組 — Phase 5.3 監控系統

提供：
- API 連線狀態檢查
- 配置完整性檢查
- 檔案系統可用性檢查
"""

import os
from pathlib import Path
from typing import Dict, Tuple
import json
from datetime import datetime

from logging_config import main_logger


class HealthChecker:
    """系統健康檢查"""

    @staticmethod
    def check_shioaji_connection() -> Tuple[bool, str]:
        """檢查 Shioaji API 連線狀態"""
        try:
            import shioaji as sj
            api = sj.Shioaji(simulation=True)
            # 不需要真正登入，只測試模塊是否可導入和初始化
            main_logger.debug("Shioaji 模塊已載入")
            return True, "✅ Shioaji 已連線"
        except ImportError:
            main_logger.warning("Shioaji 模塊未安裝")
            return False, "❌ Shioaji 未安裝"
        except Exception as e:
            main_logger.warning(f"Shioaji 連線檢查失敗: {str(e)}")
            return False, f"⚠️ 連線失敗: {str(e)[:30]}"

    @staticmethod
    def check_config_completeness() -> Tuple[bool, str]:
        """檢查配置檔案完整性"""
        try:
            config_path = Path.home() / ".app_config" / "config.json"

            if not config_path.exists():
                main_logger.warning(f"配置檔案不存在: {config_path}")
                return False, "❌ 配置檔案不存在"

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 檢查必要的鍵
            required_keys = ["api_key", "export_format"]
            missing_keys = [k for k in required_keys if k not in config]

            if missing_keys:
                main_logger.warning(f"配置檔案缺少鍵: {missing_keys}")
                return False, f"⚠️ 缺少配置: {', '.join(missing_keys[:2])}"

            main_logger.debug("配置檔案檢查通過")
            return True, "✅ 配置已完整"
        except json.JSONDecodeError:
            main_logger.error("配置檔案格式錯誤")
            return False, "❌ 配置檔案格式錯誤"
        except Exception as e:
            main_logger.error(f"配置檢查失敗: {str(e)}")
            return False, f"❌ 檢查失敗: {str(e)[:20]}"

    @staticmethod
    def check_filesystem() -> Tuple[bool, str]:
        """檢查檔案系統可用性"""
        try:
            log_dir = Path.home() / ".app_config" / "logs"
            config_dir = Path.home() / ".app_config"

            # 檢查主配置目錄是否存在且可寫
            if not config_dir.exists():
                config_dir.mkdir(parents=True, exist_ok=True)
                main_logger.info(f"建立配置目錄: {config_dir}")

            # 檢查寫入權限
            test_file = config_dir / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                main_logger.debug(f"檔案系統可寫: {config_dir}")
            except PermissionError:
                main_logger.error(f"檔案系統無寫入權限: {config_dir}")
                return False, f"❌ 無寫入權限: {config_dir.name}"

            # 檢查日誌目錄
            if not log_dir.exists():
                log_dir.mkdir(parents=True, exist_ok=True)
                main_logger.info(f"建立日誌目錄: {log_dir}")

            main_logger.debug("檔案系統檢查通過")
            return True, "✅ 檔案系統正常"
        except Exception as e:
            main_logger.error(f"檔案系統檢查失敗: {str(e)}")
            return False, f"❌ 系統檢查失敗: {str(e)[:20]}"

    @staticmethod
    def get_health_status() -> Dict[str, Tuple[bool, str]]:
        """取得完整健康狀態"""
        return {
            "shioaji": HealthChecker.check_shioaji_connection(),
            "config": HealthChecker.check_config_completeness(),
            "filesystem": HealthChecker.check_filesystem()
        }

    @staticmethod
    def get_summary_status() -> Tuple[str, str]:
        """取得健康狀態摘要 (emoji, 文字)"""
        status = HealthChecker.get_health_status()
        all_ok = all(ok for ok, _ in status.values())

        if all_ok:
            return "✅", "系統正常"
        else:
            failed_count = sum(1 for ok, _ in status.values() if not ok)
            return "⚠️", f"{failed_count} 項檢查未通過"
