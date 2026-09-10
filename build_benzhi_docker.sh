#!/bin/bash
# build_benzhi_docker.sh - Go 项目评测镜像构建脚本

set -e

# ============================================================
# 1. 基础配置
# ============================================================
IMAGE_NAME="${1:-benzhi-go-app}"
IMAGE_TAG="${2:-latest}"
PLATFORM="${3:-linux/amd64}"
CONTEXT_PATH="${4:-.}"

# ============================================================
# 2. 前置检查
# ============================================================
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 服务未启动，请先启动 Docker"
    exit 1
fi

if [ ! -f "${CONTEXT_PATH}/benzhi.Dockerfile" ]; then
    echo "错误: 找不到 benzhi.Dockerfile，请确保它在 ${CONTEXT_PATH} 目录下"
    exit 1
fi

# ============================================================
# 3. 核心构建命令
# ============================================================
echo "开始构建镜像: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "目标平台: ${PLATFORM}"
echo "构建上下文: ${CONTEXT_PATH}"

docker build \
    -f "${CONTEXT_PATH}/benzhi.Dockerfile" \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    --platform "${PLATFORM}" \
    "${CONTEXT_PATH}"

# ============================================================
# 4. 后置操作
# ============================================================
if [ $? -eq 0 ]; then
    echo "✅ 镜像构建成功: ${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    echo "查看镜像信息:"
    docker images "${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    echo "进入容器验证（示例）:"
    echo "  docker run --rm -it ${IMAGE_NAME}:${IMAGE_TAG} /bin/bash"
    echo ""
    echo "构建其他架构:"
    echo "  ./build_benzhi_docker.sh ${IMAGE_NAME} ${IMAGE_TAG} linux/amd64"
    echo "  ./build_benzhi_docker.sh ${IMAGE_NAME} ${IMAGE_TAG} linux/arm64"
else
    echo "❌ 镜像构建失败，请检查错误信息"
    exit 1
fi