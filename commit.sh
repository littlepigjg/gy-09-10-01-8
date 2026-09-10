#!/bin/bash
set -e

# ============================================
#  提交代码并推送到 GitHub 仓库
#  自动识别当前分支，首次推送自动设置上游
# ============================================

# 1. 提示输入 session ID（用作提交信息）
read -p "请输入 session ID: " sessionId

# 2. 将自身脚本和隐藏目录从暂存区排除
SELF="$(basename "$0")"
git add .
git reset -- "$SELF" 2>/dev/null || true

# 排除任意层级隐藏目录（如 .idea/、src/.cache/）内的文件，保留 .gitignore 等隐藏文件
git diff --cached --name-only | grep -E '(^|/)\.[^/]+/' | while IFS= read -r f; do
    git reset -q -- "$f"
done

# 3. 检查是否有变更需要提交
if git diff --cached --quiet 2>/dev/null; then
    echo "[INFO] 没有需要提交的变更"
else
    git commit -m "$sessionId"
    echo "[OK] 提交成功"
fi

# 4. 获取当前分支名并推送到远程
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if git push 2>/dev/null; then
    :
else
    echo "[INFO] 首次推送，设置上游分支 origin/$CURRENT_BRANCH"
    git push -u origin "$CURRENT_BRANCH"
fi

# 5. 显示 commit ID
echo
echo "========================================"
echo "分支    : $CURRENT_BRANCH"
echo "最新 commit ID:"
git log --format=%H -1

# 从远程 URL 解析仓库信息
REMOTE_URL="$(git remote get-url origin 2>/dev/null)"
if [ -n "$REMOTE_URL" ]; then
    REPO_PATH="$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]([^/]+/[^/.]+)(\.git)?.*|\1|')"
    echo "远程分支: https://github.com/${REPO_PATH}/tree/${CURRENT_BRANCH}"
fi
echo "========================================"
echo "完成！"
