#!/bin/bash
set -e

# ========== 配置区 ==========
API_KEY="${API_KEY:-}"
IMAGE="adminfather/benzhi-claude-code:20260909-isolated-git"
# =============================

CONTAINER_NAME="$(basename "$PWD")"

# 1. 检查容器是否已存在
if docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    if docker ps --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
        echo "⏳ 容器已在运行，直接进入对话..."
        docker exec -it "$CONTAINER_NAME" bash -lc "claude --resume || claude"
        exit 0
    else
        echo "⚠️  容器 $CONTAINER_NAME 已存在但未运行。"
        echo "   若需重建，请先执行: docker rm $CONTAINER_NAME"
        exit 1
    fi
fi

# 2. 获取 API Key
if [ -z "$API_KEY" ]; then
    read -rsp "请输入 API Key: " API_KEY
    echo
    if [ -z "$API_KEY" ]; then
        echo "❌ API Key 不能为空"
        exit 1
    fi
fi

# 3. 清空并重建 workspace 目录（保证为空，满足容器启动检查）
rm -rf "$PWD/workspace"
mkdir -p "$PWD/workspace"

# 4. 后台启动容器（空 /workspace 通过入口检查）
echo "🚀 创建容器 $CONTAINER_NAME ..."
docker run -dit --init \
    --restart=no \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --name "$CONTAINER_NAME" \
    --mount "type=bind,src=$PWD/workspace,dst=/workspace" \
    -e "apikey=$API_KEY" \
    "$IMAGE"

# 5. 将项目文件复制到 workspace/项目名/（双向同步，容器内实时可见）
PROJECT_DIR="$(basename "$PWD")"
echo "📂 迁移项目到 workspace/$PROJECT_DIR/ ..."
rsync -a --exclude='workspace' --exclude='node_modules' --exclude='__pycache__' \
    --exclude='.idea' --exclude='.vscode' --exclude='.pytest_cache' --exclude='.venv' --exclude='venv' \
    "$PWD/" "$PWD/workspace/$PROJECT_DIR/"

# 6. 删除当前目录下已迁移的项目文件（保留 workspace/、run_docker.sh 和隐藏配置）
echo "🗑️  清理已迁移的项目文件..."
for item in "$PWD"/*; do
    name="$(basename "$item")"
    if [ "$name" = "workspace" ] || [ "$name" = "run_docker.sh" ]; then
        continue
    fi
    rm -rf "$item"
done

# 7. 进入容器
echo "🎯 进入容器..."
docker attach "$CONTAINER_NAME"
