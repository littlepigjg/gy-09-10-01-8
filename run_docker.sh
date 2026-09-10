#!/bin/bash
set -e

# ========== 配置区 ==========
API_KEY="${API_KEY:-}"                              # 从环境变量读取，未设置时提示输入
IMAGE="adminfather/benzhi-claude-code"
# =============================

# 动态容器名：当前目录名
CONTAINER_NAME="$(basename "$PWD")"
# 本机工作目录：当前目录下的 workspace 子目录
RUN_DIR="$PWD/workspace"

echo "📁 项目名称: $CONTAINER_NAME"
echo "🐳 容器名:   $CONTAINER_NAME"

# 1. 检查容器是否已存在
if docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    if docker ps --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
        echo "⏳ 容器已在运行，直接进入对话..."
        docker exec -it "$CONTAINER_NAME" bash -lc "claude --resume || claude"
        exit 0
    else
        echo "⚠️  容器 $CONTAINER_NAME 已存在但未运行。"
        echo "   若需重建，请先执行: docker rm $CONTAINER_NAME"
        echo "   或直接执行 end_docker.sh 导出并删除后重来。"
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

# 3. 创建本机工作目录并初始化为空
mkdir -p "$RUN_DIR"

# 4. 创建并启动容器（bind mount，前台交互模式）
echo "🚀 创建容器 $CONTAINER_NAME ..."
docker run -it --init \
    --restart=no \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --name "$CONTAINER_NAME" \
    --mount "type=bind,src=$RUN_DIR,dst=/workspace" \
    -e "apikey=$API_KEY" \
    "$IMAGE"
