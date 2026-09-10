"""应用配置"""
import os

# 数据库配置
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "ratelimiter")

# 应用配置
APP_HOST = "0.0.0.0"
APP_PORT = 8888

# 默认限流规则
DEFAULT_RULES = {
    "rate": 100,          # 每秒允许请求数
    "burst": 200,         # 突发容量
    "algorithm": "token_bucket",  # 默认算法: token_bucket / sliding_window / fixed_window
    "window_size": 60,    # 滑动窗口/固定窗口大小(秒)
}

# 熔断器默认配置
DEFAULT_CIRCUIT_BREAKER = {
    "failure_threshold": 5,       # 失败次数阈值
    "recovery_timeout": 30,       # 恢复超时(秒)
    "half_open_max_calls": 3,     # 半开状态最大试探请求数
    "success_threshold": 2,       # 半开状态恢复成功阈值
}
