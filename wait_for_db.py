"""等待 MySQL 就绪后再启动应用（容器入口辅助脚本）。

使用项目已安装的 aiomysql，无需在镜像中额外安装 mysql-client。
"""
import asyncio
import os
import sys

import aiomysql


async def wait_for_db(max_retries: int = 60, interval: float = 2.0) -> bool:
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "root")

    for attempt in range(1, max_retries + 1):
        try:
            conn = await aiomysql.connect(host=host, port=port, user=user, password=password)
            conn.close()
            print(f"[wait_for_db] MySQL 已就绪（{host}:{port}）")
            return True
        except Exception as exc:
            print(f"[wait_for_db] MySQL 尚未就绪，{attempt}/{max_retries} 次重试: {exc}")
            await asyncio.sleep(interval)

    print("[wait_for_db] 等待 MySQL 超时，退出。", file=sys.stderr)
    return False


if __name__ == "__main__":
    if asyncio.run(wait_for_db()):
        sys.exit(0)
    sys.exit(1)
