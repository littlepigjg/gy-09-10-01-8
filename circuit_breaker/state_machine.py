"""熔断器状态机

状态转换：
  CLOSED --[失败次数>=阈值]--> OPEN
  OPEN   --[超时]--> HALF_OPEN
  HALF_OPEN --[试探成功>=阈值]--> CLOSED
  HALF_OPEN --[试探失败]--> OPEN

关键设计：
- 每个服务独立的状态机实例
- 使用 RLock 保证状态转换原子性
- 半开状态限制试探请求数量
- 状态变更回调用于持久化和通知
"""
import time
import threading
import logging
from enum import Enum
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # 正常状态，允许所有请求
    OPEN = "open"           # 熔断状态，拒绝所有请求
    HALF_OPEN = "half_open" # 半开状态，允许少量试探请求


class CircuitBreaker:
    """熔断器状态机"""

    def __init__(
        self,
        service_name: str,
        backend_url: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        on_state_change: Optional[Callable] = None,
    ):
        self.service_name = service_name
        self.backend_url = backend_url
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change = time.time()
        self._total_requests = 0
        self._total_failures = 0

        self._lock = threading.RLock()
        self._on_state_change = on_state_change
        self._enabled = True

    @property
    def state(self) -> CircuitState:
        with self._lock:
            # 检查OPEN状态是否超时，自动转为HALF_OPEN
            if self._state == CircuitState.OPEN and self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def record_success(self):
        """记录成功请求"""
        with self._lock:
            self._total_requests += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(f"[{self.service_name}] 半开状态试探成功，恢复正常")
                    self._reset()
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # 重置失败计数

    def record_failure(self):
        """记录失败请求"""
        with self._lock:
            self._total_requests += 1
            self._total_failures += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"[{self.service_name}] 半开状态试探失败，重新熔断")
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    logger.warning(f"[{self.service_name}] 失败次数达到阈值({self._failure_count}/{self.failure_threshold})，触发熔断")
                    self._transition_to(CircuitState.OPEN)

    def allow_request(self) -> bool:
        """检查是否允许请求通过"""
        if not self._enabled:
            return True

        current_state = self.state  # 触发超时检查

        if current_state == CircuitState.CLOSED:
            return True
        elif current_state == CircuitState.OPEN:
            return False
        elif current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
        return False

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        if new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._reset()
        elif new_state == CircuitState.OPEN:
            self._last_failure_time = time.time()

        logger.info(f"[{self.service_name}] 状态变更: {old_state.value} -> {new_state.value}")

        if self._on_state_change:
            try:
                self._on_state_change(self.service_name, old_state.value, new_state.value)
            except Exception as e:
                logger.error(f"状态变更回调异常: {e}")

    def _reset(self):
        """重置计数器"""
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def set_enabled(self, enabled: bool):
        with self._lock:
            self._enabled = enabled

    def get_info(self) -> dict:
        """获取熔断器信息"""
        current_state = self.state  # 触发超时检查
        return {
            "service_name": self.service_name,
            "backend_url": self.backend_url,
            "state": current_state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "half_open_max_calls": self.half_open_max_calls,
            "success_threshold": self.success_threshold,
            "half_open_calls": self._half_open_calls,
            "last_failure_time": datetime.fromtimestamp(self._last_failure_time).isoformat() if self._last_failure_time else None,
            "last_state_change": datetime.fromtimestamp(self._last_state_change).isoformat(),
            "total_requests": self._total_requests,
            "total_failures": self._total_failures,
            "enabled": self._enabled,
        }

    def reset_to_closed(self):
        """手动重置为关闭状态"""
        with self._lock:
            self._reset()
            self._last_failure_time = None
            self._transition_to(CircuitState.CLOSED)
