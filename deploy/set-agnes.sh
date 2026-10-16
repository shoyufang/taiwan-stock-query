#!/usr/bin/env bash
# 在 home server 上設定 AI 助理（Agnes）的金鑰與模型（由使用者本人輸入，畫面不顯示金鑰）。
# 用法（在自己電腦的終端機）：ssh -t home "bash ~/apps/twstock/deploy/set-agnes.sh"
set -euo pipefail

APP_DIR="$HOME/apps/twstock"
ENV_FILE="$APP_DIR/deploy/.env"
BASE_URL="${AGNES_BASE_URL:-https://apihub.agnes-ai.com/v1}"

echo "=== 設定 AI 助理（Agnes） ==="
echo "貼上金鑰時畫面不會出現任何字，這是正常的，貼完直接按 Enter。"
echo
read -rsp "請貼上 Agnes API Key，然後按 Enter：" KEY; echo
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
if [ -z "$KEY" ]; then
  echo "沒有收到金鑰，沒有做任何變更。"
  exit 1
fi

# 金鑰寫在只有自己讀得到的暫存檔再交給 curl，避免出現在指令列（ps 看得到）
umask 077
HDR="$(mktemp)"
trap 'rm -f "$HDR"' EXIT
printf 'Authorization: Bearer %s\n' "$KEY" > "$HDR"

echo "正在向 Agnes 查詢可用模型…"
if ! MODELS_JSON="$(curl -fsS --max-time 20 -H @"$HDR" "$BASE_URL/models")"; then
  echo "查詢失敗：金鑰可能不正確，或 Agnes 暫時連不上。沒有做任何變更。"
  exit 1
fi
mapfile -t MODELS < <(printf '%s' "$MODELS_JSON" | python3 -c 'import json,sys; [print(m["id"]) for m in json.load(sys.stdin).get("data", [])]')
if [ "${#MODELS[@]}" -eq 0 ]; then
  echo "金鑰有效，但沒有列出任何模型。沒有做任何變更。"
  exit 1
fi

echo
echo "可用模型："
for i in "${!MODELS[@]}"; do
  printf '  %d) %s\n' "$((i + 1))" "${MODELS[$i]}"
done
read -rp "請輸入要用的模型編號（直接按 Enter 用第 1 個）：" PICK
PICK="${PICK:-1}"
if ! [[ "$PICK" =~ ^[0-9]+$ ]] || [ "$PICK" -lt 1 ] || [ "$PICK" -gt "${#MODELS[@]}" ]; then
  echo "編號不正確，沒有做任何變更。"
  exit 1
fi
MODEL="${MODELS[$((PICK - 1))]}"

touch "$ENV_FILE"
TMP="$(mktemp)"
grep -vE '^(AGNES_API_KEY|AGNES_MODEL)=' "$ENV_FILE" > "$TMP" || true
{
  cat "$TMP"
  echo "AGNES_API_KEY=$KEY"
  echo "AGNES_MODEL=$MODEL"
} > "$ENV_FILE"
rm -f "$TMP"
chmod 600 "$ENV_FILE"
unset KEY

echo "已設定模型：$MODEL。正在重新啟動 API…"
cd "$APP_DIR"
docker compose -f deploy/compose.yml up -d api >/dev/null
echo
echo "完成！打開網站的「AI 助理」頁就能使用。可以關掉這個視窗了。"
