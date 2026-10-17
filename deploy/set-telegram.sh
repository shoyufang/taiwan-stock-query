#!/usr/bin/env bash
# 設定 Telegram 警示通知（由使用者本人輸入，token 不顯示）。
# 事前：1) 在 Telegram 找 @BotFather → /newbot 建立機器人，拿到 token
#       2) 在 Telegram 打開你的新機器人，隨便傳一句話給它（讓它知道要傳給誰）
# 用法（在自己電腦的終端機）：ssh -t home "bash ~/apps/twstock/deploy/set-telegram.sh"
set -euo pipefail

APP_DIR="$HOME/apps/twstock"
ENV_FILE="$APP_DIR/deploy/.env"

echo "=== 設定 Telegram 警示通知 ==="
echo "請先確認：已經在 Telegram 傳過一句話給你的機器人。"
echo "貼上 token 時畫面不會出現任何字，這是正常的，貼完按 Enter。"
echo
read -rsp "請貼上 BotFather 給你的 token，然後按 Enter：" TOKEN; echo
TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]')"
[ -n "$TOKEN" ] || { echo "沒有收到 token，沒有做任何變更。"; exit 1; }

echo "正在尋找你的聊天 ID…"
UPDATES="$(curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates")"
CHAT_ID="$(printf '%s' "$UPDATES" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("ok"):
    sys.exit(2)
ids = [u[k]["chat"]["id"] for u in d.get("result", []) for k in ("message", "edited_message") if k in u]
print(ids[-1] if ids else "")
' || true)"
if [ -z "$CHAT_ID" ]; then
  echo "找不到聊天紀錄：可能 token 不對，或還沒傳訊息給機器人。請在 Telegram 傳一句話給機器人後再執行一次。"
  exit 1
fi

umask 077
touch "$ENV_FILE"
TMP="$(mktemp)"
grep -vE '^(TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)=' "$ENV_FILE" > "$TMP" || true
{ cat "$TMP"; echo "TELEGRAM_BOT_TOKEN=$TOKEN"; echo "TELEGRAM_CHAT_ID=$CHAT_ID"; } > "$ENV_FILE"
rm -f "$TMP"
chmod 600 "$ENV_FILE"

curl -s -o /dev/null -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H 'Content-Type: application/json' \
  -d "{\"chat_id\": \"${CHAT_ID}\", \"text\": \"台股看盤：Telegram 通知設定完成\"}"
unset TOKEN

echo "已存好（只有你的帳號讀得到）。正在重新啟動 API…"
cd "$APP_DIR"
docker compose -f deploy/compose.yml up -d api >/dev/null
echo
echo "完成！你的 Telegram 應該已經收到一則「設定完成」訊息。可以關掉這個視窗了。"
