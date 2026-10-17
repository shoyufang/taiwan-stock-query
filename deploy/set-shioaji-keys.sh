#!/usr/bin/env bash
# 在 home server 上設定永豐金 API 金鑰（由使用者本人輸入，畫面不顯示）。
# 用法（在自己電腦的終端機）：ssh -t home "bash ~/apps/twstock/deploy/set-shioaji-keys.sh"
set -euo pipefail

APP_DIR="$HOME/apps/twstock"
ENV_FILE="$APP_DIR/deploy/.env"

echo "=== 設定永豐金 API 金鑰 ==="
echo "貼上金鑰時畫面不會出現任何字，這是正常的，貼完直接按 Enter。"
echo
read -rsp "1/2 請貼上 API Key，然後按 Enter：" KEY; echo
read -rsp "2/2 請貼上 Secret Key，然後按 Enter：" SECRET; echo

KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
SECRET="$(printf '%s' "$SECRET" | tr -d '[:space:]')"
if [ -z "$KEY" ] || [ -z "$SECRET" ]; then
  echo "沒有收到金鑰，沒有做任何變更。"
  exit 1
fi

umask 077
touch "$ENV_FILE"
TMP="$(mktemp)"
grep -vE '^(SHIOAJI_API_KEY|SHIOAJI_SECRET_KEY|SHIOAJI_SIMULATION)=' "$ENV_FILE" > "$TMP" || true
{
  cat "$TMP"
  echo "SHIOAJI_API_KEY=$KEY"
  echo "SHIOAJI_SECRET_KEY=$SECRET"
  echo "SHIOAJI_SIMULATION=true"
} > "$ENV_FILE"
rm -f "$TMP"
chmod 600 "$ENV_FILE"
unset KEY SECRET

echo "金鑰已存好（只有你的帳號讀得到）。正在重新啟動行情服務…"
cd "$APP_DIR"
docker compose -f deploy/compose.yml up -d quote >/dev/null
echo
echo "完成！可以關掉這個視窗了。"
