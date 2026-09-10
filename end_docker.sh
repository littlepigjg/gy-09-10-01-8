#!/bin/bash
set -e

# 动态容器名：当前目录名（与 run_docker.sh 一致）
CONTAINER_NAME="$(basename "$PWD")"

echo "🐳 容器名: $CONTAINER_NAME"

# 1. 检查容器是否存在
if ! docker ps -a --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
    echo "❌ 容器 $CONTAINER_NAME 不存在，无需清理。"
    exit 1
fi

# 2. 选择操作（默认 a）
echo ""
echo "请选择操作："
echo "  a) 仅复制轨迹（不关闭、不删除容器）"
echo "  b) 复制轨迹后关闭并删除容器"
read -r -p "请输入选项 [a/b]: " CHOICE
CHOICE="${CHOICE:-a}"

# 3. 导出轨迹到本地 traces/ 目录
TRACES_DIR="$PWD/traces"
echo ""
echo "📋 导出轨迹到 $TRACES_DIR ..."
mkdir -p "$TRACES_DIR"
if docker cp "$CONTAINER_NAME:/home/node/.claude/projects" "$TRACES_DIR" 2>/dev/null; then
    echo "✅ 轨迹已导出到 $TRACES_DIR"
else
    echo "⚠️  轨迹目录不存在或为空，可能尚未产生对话记录。"
fi

# 4. 显示 Session ID
echo ""
echo "📋 找到的 Session ID："
SESSION_IDS=$(find "$TRACES_DIR" -name "*.jsonl" -type f 2>/dev/null | sort -u)
if [ -n "$SESSION_IDS" ]; then
    echo "$SESSION_IDS" | while read -r f; do
        SID=$(basename "$f" .jsonl)
        echo "  - $SID  ($f)"
    done
else
    echo "  （未找到 .jsonl 会话文件）"
fi

# 5. 仅选项 b 才关闭并删除容器
if [ "$CHOICE" = "b" ]; then
    echo ""
    if docker ps --format '{{.Names}}' | grep -wq "$CONTAINER_NAME"; then
        echo "⏳ 停止容器 $CONTAINER_NAME ..."
        docker stop "$CONTAINER_NAME"
    fi
    echo "🗑️  删除容器 $CONTAINER_NAME ..."
    docker rm "$CONTAINER_NAME"
    echo ""
    echo "✅ 清理完成！容器已删除。"
else
    echo ""
    echo "✅ 轨迹已复制，容器 $CONTAINER_NAME 保持运行，未做任何修改。"
fi

echo "   - 代码已保存在本机（bind mount 映射目录未受影响）。"
echo "   - 轨迹文件已保存到 $TRACES_DIR"
