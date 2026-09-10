"""令牌桶算法 - 高并发优化版本

核心思路：
- 每个key维护一个桶，桶内有令牌数和上次补充时间
- 请求到来时按时间差补充令牌，然后消费一个令牌
- 使用 threading.RLock 保证单key原子性，不同key无锁竞争
- 内存中维护活跃桶，惰性清理超时桶
"""
import threading
import time
from collections import defaultdict
from .base import BaseRateLimiter, RateLimitResult


class _Bucket:
    """单个令牌桶（线程安全）"""
    __slots__ = ('tokens', 'last_refill', 'rate', 'burst', 'lock')

    def __init__(self, rate: float, burst: int):
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
        self.rate = rate
        self.burst = burst
        self.lock = threading.RLock()

    def consume(self) -> tuple[bool, float]:
        """尝试消费一个令牌，返回 (allowed, retry_after)"""
        with self.lock:
            now = time.monotonic()
            # 按时间差补充令牌
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True, 0.0
            else:
                # 计算需要等待多久才能获得一个令牌
                wait_time = (1.0 - self.tokens) / self.rate
                return False, wait_time

    def get_state(self) -> tuple[float, float]:
        """获取当前令牌数和速率"""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            current_tokens = min(self.burst, self.tokens + elapsed * self.rate)
            return current_tokens, self.rate


class TokenBucketLimiter(BaseRateLimiter):
    """令牌桶限流器"""

    def __init__(self, rate: float, burst: int = 0, **kwargs):
        super().__init__(rate, burst)
        self._buckets: dict[str, _Bucket] = {}
        self._bucket_locks: dict[str, threading.RLock] = defaultdict(threading.RLock)
        self._cleanup_interval = 60.0
        self._last_cleanup = time.monotonic()

    def allow(self, key: str = "default") -> RateLimitResult:
        # 惰性清理过期桶
        self._maybe_cleanup()

        # 获取或创建桶（使用key级锁避免竞态）
        lock = self._bucket_locks[key]
        with lock:
            if key not in self._buckets:
                self._buckets[key] = _Bucket(self.rate, self.burst)
            bucket = self._buckets[key]

        allowed, retry_after = bucket.consume()
        current_tokens, rate = bucket.get_state()

        return RateLimitResult(
            allowed=allowed,
            current_rate=rate - current_tokens / self.burst * rate if self.burst else rate,
            limit_rate=self.rate,
            remaining=max(0, int(current_tokens)),
            retry_after=retry_after,
            reason="" if allowed else f"令牌桶已空,需等待{retry_after:.2f}s",
        )

    def _maybe_cleanup(self):
        """惰性清理超时的空桶"""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        timeout = self._cleanup_interval * 2
        expired_keys = []
        for k, b in list(self._buckets.items()):
            if now - b.last_refill > timeout:
                expired_keys.append(k)
        for k in expired_keys:
            self._buckets.pop(k, None)
            self._bucket_locks.pop(k, None)

    def get_bucket_info(self, key: str) -> dict:
        """获取桶信息（供API使用）"""
        if key in self._buckets:
            tokens, rate = self._buckets[key].get_state()
            return {"tokens": round(tokens, 2), "rate": rate, "burst": self.burst}
        return {"tokens": self.burst, "rate": self.rate, "burst": self.burst}
