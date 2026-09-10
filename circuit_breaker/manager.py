"""熔断器管理器 - 管理多个服务的熔断器"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import CircuitBreakerState
from .state_machine import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


class CircuitBreakerManager:
    """熔断器管理器"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._state_change_callback = None

    def set_state_change_callback(self, callback):
        self._state_change_callback = callback

    async def load_states(self, session: AsyncSession):
        """从数据库加载熔断器状态"""
        result = await session.execute(select(CircuitBreakerState))
        states = result.scalars().all()

        for s in states:
            breaker = CircuitBreaker(
                service_name=s.service_name,
                backend_url=s.backend_url,
                failure_threshold=s.failure_threshold,
                recovery_timeout=s.recovery_timeout,
                half_open_max_calls=s.half_open_max_calls,
                success_threshold=s.success_threshold,
                on_state_change=self._on_state_change,
            )
            breaker._state = CircuitState(s.state)
            breaker._failure_count = s.failure_count
            breaker._total_requests = s.total_requests
            breaker._total_failures = s.total_failures
            breaker._enabled = s.enabled

            self._breakers[s.service_name] = breaker

        logger.info(f"已加载 {len(states)} 个熔断器状态")

    def _on_state_change(self, service_name: str, old_state: str, new_state: str):
        """状态变更回调"""
        if self._state_change_callback:
            try:
                self._state_change_callback(service_name, old_state, new_state)
            except Exception:
                pass

    def allow_request(self, service_name: str) -> bool:
        """检查服务是否允许请求"""
        if service_name not in self._breakers:
            return True
        return self._breakers[service_name].allow_request()

    def record_success(self, service_name: str):
        if service_name in self._breakers:
            self._breakers[service_name].record_success()

    def record_failure(self, service_name: str):
        if service_name in self._breakers:
            self._breakers[service_name].record_failure()

    def get_all_states(self) -> list[dict]:
        """获取所有熔断器状态"""
        return [b.get_info() for b in self._breakers.values()]

    def get_state(self, service_name: str) -> dict | None:
        if service_name in self._breakers:
            return self._breakers[service_name].get_info()
        return None

    def update_breaker(self, service_name: str, config: dict):
        """动态更新熔断器配置"""
        if service_name in self._breakers:
            b = self._breakers[service_name]
            if "failure_threshold" in config:
                b.failure_threshold = config["failure_threshold"]
            if "recovery_timeout" in config:
                b.recovery_timeout = config["recovery_timeout"]
            if "half_open_max_calls" in config:
                b.half_open_max_calls = config["half_open_max_calls"]
            if "success_threshold" in config:
                b.success_threshold = config["success_threshold"]
            if "enabled" in config:
                b.set_enabled(config["enabled"])
            logger.info(f"熔断器配置已更新: {service_name} -> {config}")

    def add_breaker(self, service_name: str, backend_url: str, config: dict = None):
        """添加新的熔断器"""
        config = config or {}
        breaker = CircuitBreaker(
            service_name=service_name,
            backend_url=backend_url,
            failure_threshold=config.get("failure_threshold", 5),
            recovery_timeout=config.get("recovery_timeout", 30),
            half_open_max_calls=config.get("half_open_max_calls", 3),
            success_threshold=config.get("success_threshold", 2),
            on_state_change=self._on_state_change,
        )
        self._breakers[service_name] = breaker

    def remove_breaker(self, service_name: str):
        self._breakers.pop(service_name, None)

    def reset_breaker(self, service_name: str):
        """手动重置熔断器"""
        if service_name in self._breakers:
            self._breakers[service_name].reset_to_closed()
