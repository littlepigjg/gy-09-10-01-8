"""限流器基类"""
import time
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    """限流检查结果"""
    allowed: bool
    current_rate: float
    limit_rate: float
    remaining: int
    retry_after: float = 0.0
    reason: str = ""


class BaseRateLimiter:
    """限流器基类"""

    def __init__(self, rate: float, burst: int = 0, **kwargs):
        """
        Args:
            rate: 每秒允许的请求数
            burst: 突发容量(burst >= rate)
        """
        self.rate = rate
        self.burst = max(burst, int(rate))
        self._lock_free_ts = 0.0

    def allow(self, key: str = "default") -> RateLimitResult:
        """检查是否允许请求通过"""
        raise NotImplementedError

    def _now(self) -> float:
        return time.monotonic()
