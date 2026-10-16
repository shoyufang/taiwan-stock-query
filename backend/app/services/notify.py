"""通知管道：網頁內（Redis q:ALERTS）、ntfy（自架，走 Tailscale）、Telegram。

ntfy／Telegram 沒設定就略過；任一管道失敗不影響其他管道。
"""

from __future__ import annotations

import json
import logging
import os

import httpx

log = logging.getLogger("notify")


def config() -> dict:
    return {
        "ntfy_url": os.environ.get("NTFY_URL", ""),          # 例：http://ntfy（容器內部位址）
        "ntfy_topic": os.environ.get("NTFY_TOPIC", "twstock"),
        "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "public_url": os.environ.get("PUBLIC_URL", ""),      # 例：http://100.100.245.93:8600
    }


def channels(cfg: dict | None = None) -> dict:
    cfg = cfg or config()
    return {"web": True, "ntfy": bool(cfg["ntfy_url"]), "telegram": bool(cfg["telegram_token"] and cfg["telegram_chat"])}


async def send(rds, http: httpx.AsyncClient, *, title: str, message: str, code: str | None, at: str,
               cfg: dict | None = None) -> dict:
    cfg = cfg or config()
    link = f"{cfg['public_url']}/stock/{code}" if cfg["public_url"] and code else cfg["public_url"] or None
    result = {}

    payload = {"kind": "alert", "code": "ALERTS", "title": title, "message": message, "stock": code, "at": at}
    try:
        await rds.publish("q:ALERTS", json.dumps(payload, ensure_ascii=False))
        result["web"] = True
    except Exception:
        log.warning("網頁通知失敗", exc_info=True)
        result["web"] = False

    if cfg["ntfy_url"]:
        try:
            body = {"topic": cfg["ntfy_topic"], "title": title, "message": message, "tags": ["chart_with_upwards_trend"]}
            if link:
                body["click"] = link
            r = await http.post(cfg["ntfy_url"], json=body)
            result["ntfy"] = r.is_success
        except Exception:
            log.warning("ntfy 通知失敗", exc_info=True)
            result["ntfy"] = False

    if cfg["telegram_token"] and cfg["telegram_chat"]:
        try:
            text = f"{title}\n{message}" + (f"\n{link}" if link else "")
            r = await http.post(f"https://api.telegram.org/bot{cfg['telegram_token']}/sendMessage",
                                json={"chat_id": cfg["telegram_chat"], "text": text, "disable_web_page_preview": True})
            result["telegram"] = r.is_success
        except Exception:
            # 例外訊息可能含 token 網址，不寫入 log 內容
            log.warning("Telegram 通知失敗")
            result["telegram"] = False
    return result
