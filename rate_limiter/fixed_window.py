"""固定窗口算法

核心思路：
- 按固定时间窗口计数
- 每个窗口有固定容量，超过则拒绝
- 实现简单高效，适合对精度要求不高的场景
"""
import threading
import time
from .base import BaseRateLimiter, RateLimitResult


class _FixedWindow:
    """单个固定窗口"""

    def __init__(self, rate: float, window_size: int):
        self.rate = rate
        self.window_size = window_size
        self.window_capacity = int(rate * window_size)
        self.current_count = 0
        self.window_start = self._current_window_start()
        self.lock = threading.RLock()

    @staticmethod
    def _current_window_start() -> float:
        now = time.time()
        return now - (now % 60)  # 按分钟对齐

    def check_and_consume(self) -> tuple[bool, int, int]:
        """检查并消费，返回 (allowed, current_count, capacity)"""
        now = time.time()
        current_start = now - (now % self.window_size)

        with self.lock:
            if current_start != self.window_start:
                # 新窗口，重置计数
                self.window_start = current_start
                self.current_count = 0

            if self.current_count < self.window_capacity:
                self.current_count += 1
                return True, self.current_count, self.window_capacity
            else:
                return False, self.current_count, self.window_capacity


class FixedWindowLimiter(BaseRateLimiter):
    """固定窗口限流器"""

    def __init__(self, rate: float, burst: int = 0, window_size: int = 60, **kwargs):
        super().__init__(rate, burst)
        self.window_size = window_size
        self._windows: dict[str, _FixedWindow] = {}
        self._lock_lock = threading.RLock()

    def _get_window(self, key: str) -> _FixedWindow:
        if key in self._windows:
            return self._windows[key]
        with self._lock_lock:
            if key not in self._windows:
                self._windows[key] = _FixedWindow(self.rate, self.window_size)
            return self._windows[key]

    def allow(self, key: str = "default") -> RateLimitResult:
        window = self._get_window(key)
        allowed, count, capacity = window.check_and_consume()

        return RateLimitResult(
            allowed=allowed,
            current_rate=count / self.window_size,
            limit_rate=self.rate,
            remaining=max(0, capacity - count),
            retry_after=self.window_size - (time.time() % self.window_size) if not allowed else 0.0,
            reason="" if allowed else f"固定窗口已达上限({count}/{capacity})",
        )

    def get_window_info(self, key: str) -> dict:
        if key in self._windows:
            w = self._windows[key]
            return {"count": w.current_count, "capacity": w.window_capacity, "window_size": w.window_size}
        return {"count": 0, "capacity": int(self.rate * self.window_size), "window_size": self.window_size}
