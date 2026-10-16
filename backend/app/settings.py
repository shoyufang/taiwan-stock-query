"""新網站後端設定：一律從環境變數讀取（不讀 Streamlit secrets）。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    redis_url: str
    app_version: str
    tz: str


def load_settings() -> Settings:
    return Settings(
        redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        app_version=os.environ.get("APP_VERSION", "dev"),
        tz=os.environ.get("TZ", "Asia/Taipei"),
    )
