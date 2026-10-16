#!/bin/sh
# home server 的 git hook：收到 main 分支推送後，部署並重建新網站。
# 安裝位置：~/git/twstock.git/hooks/post-receive（chmod +x）
set -e
GIT_DIR="$HOME/git/twstock.git"
TARGET="$HOME/apps/twstock"
mkdir -p "$TARGET"

while read -r old new ref; do
  [ "$ref" = "refs/heads/main" ] || continue
  echo "=== [twstock] 部署 $(git --git-dir="$GIT_DIR" rev-parse --short "$new") ==="
  git --git-dir="$GIT_DIR" --work-tree="$TARGET" checkout -f main
  cd "$TARGET"
  if [ ! -f deploy/.env ]; then
    echo "!!! 缺少 $TARGET/deploy/.env（參考 deploy/.env.example），停止部署"
    exit 1
  fi
  APP_VERSION=$(git --git-dir="$GIT_DIR" rev-parse --short "$new") \
    docker compose -f deploy/compose.yml up -d --build --remove-orphans
  echo "=== [twstock] 部署完成 ==="
done
