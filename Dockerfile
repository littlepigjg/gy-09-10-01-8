# API网关限流熔断服务 - 应用镜像
# 基础镜像默认走 Docker Hub；若拉取超时，可改为镜像加速器地址，例如：
#   docker.1ms.run/library/python:3.12-slim
FROM python:3.12-slim

# 设置时区和编码
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8

WORKDIR /app

# 先复制依赖文件，利用Docker缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目源码
COPY . .

EXPOSE 8888

# 健康检查：用 Python 请求接口，无需 curl
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=30s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8888/api/stats',timeout=3)" || exit 1

# 等待 MySQL 就绪后启动应用
CMD ["sh", "-c", "python wait_for_db.py && uvicorn main:app --host 0.0.0.0 --port 8888"]
