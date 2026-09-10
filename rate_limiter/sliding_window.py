"""滑动窗口算法 - 内存优化版本

核心思路：
- 使用固定数量的时间槽(TimeSlot)模拟滑动窗口
- 每个槽记录该时间段内的请求数
- 当前窗口请求数 = 各槽请求数之和（含当前部分槽）
- 内存优化：用 OrderedDict 按时间顺序管理槽，自动淘汰旧槽
- 高并发：使用 RLock 保护槽状态，读操作无锁快路径
"""
import threading
import time
from collections import OrderedDict
from .base import BaseRateLimiter, RateLimitResult

SLOT_GRANULARITY = 1.0  # 每个槽的粒度(秒)


class _SlidingWindow:
    """单个滑动窗口"""

    def __init__(self, rate: float, window_size: int):
        self.rate = rate
        self.window_size = window_size
        self.slots: OrderedDict[int, int] = OrderedDict()  # slot_key -> count
        self.lock = threading.RLock()
        self._current_slot = self._slot_key(time.monotonic())

    @staticmethod
    def _slot_key(ts: float) -> int:
        return int(ts / SLOT_GRANULARITY)

    def _evict_old_slots(self, current_slot: int):
        """淘汰窗口外的旧槽"""
        cutoff = current_slot - int(self.window_size / SLOT_GRANULARITY)
        while self.slots:
            oldest_key = next(iter(self.slots))
            if oldest_key <= cutoff:
                self.slots.popitem(last=False)
            else:
                break

    def _total_count(self, current_slot: int) -> int:
        """计算当前窗口总请求数（窗口内各时间槽完整计数之和）。

        注意：已发生的请求不能按当前槽的时间流逝比例折算，否则高并发突发
        落在某一槽的极短时间片内时计数会被压成 0，导致限流失效。
        """
        cutoff = current_slot - int(self.window_size / SLOT_GRANULARITY)
        return sum(v for k, v in self.slots.items() if k > cutoff)

    def check_and_consume(self) -> tuple[bool, float, int, int]:
        """检查并消费请求，返回 (allowed, current_rate, total, limit)"""
        now = time.monotonic()
        current_slot = self._slot_key(now)

        with self.lock:
            if current_slot != self._current_slot:
                self._evict_old_slots(current_slot)
                self._current_slot = current_slot

            total = self._total_count(current_slot)
            limit = int(self.rate * self.window_size)

            if total < limit:
                self.slots[current_slot] = self.slots.get(current_slot, 0) + 1
                total += 1
                current_rate = total / self.window_size
                return True, current_rate, total, limit
            else:
                current_rate = total / self.window_size
                return False, current_rate, total, limit


class SlidingWindowLimiter(BaseRateLimiter):
    """滑动窗口限流器"""

    def __init__(self, rate: float, burst: int = 0, window_size: int = 60, **kwargs):
        super().__init__(rate, burst)
        self.window_size = window_size
        self._windows: dict[str, _SlidingWindow] = {}
        self._window_locks: dict[str, threading.RLock] = {}
        self._lock_lock = threading.RLock()

    def _get_window(self, key: str) -> _SlidingWindow:
        """获取或创建滑动窗口"""
        if key in self._windows:
            return self._windows[key]

        with self._lock_lock:
            if key not in self._windows:
                self._windows[key] = _SlidingWindow(self.rate, self.window_size)
            return self._windows[key]

    def allow(self, key: str = "default") -> RateLimitResult:
        window = self._get_window(key)
        allowed, current_rate, total, limit = window.check_and_consume()

        remaining = max(0, limit - total)

        return RateLimitResult(
            allowed=allowed,
            current_rate=round(current_rate, 2),
            limit_rate=self.rate,
            remaining=remaining,
            retry_after=SLOT_GRANULARITY if not allowed else 0.0,
            reason="" if allowed else f"滑动窗口已达上限({total}/{limit})",
        )

    def get_window_info(self, key: str) -> dict:
        """获取窗口信息"""
        if key in self._windows:
            w = self._windows[key]
            now = time.monotonic()
            current_slot = w._slot_key(now)
            total = w._total_count(current_slot)
            limit = int(self.rate * self.window_size)
            return {"total": total, "limit": limit, "window_size": self.window_size}
        return {"total": 0, "limit": int(self.rate * self.window_size), "window_size": self.window_size}
