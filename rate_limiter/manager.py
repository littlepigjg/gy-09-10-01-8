"""限流管理器 - 管理多种限流算法，从数据库加载规则"""
import logging
import fnmatch
import time
import threading
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import RateLimitRule
from .token_bucket import TokenBucketLimiter
from .sliding_window import SlidingWindowLimiter
from .fixed_window import FixedWindowLimiter
from .base import RateLimitResult

logger = logging.getLogger(__name__)

ALGORITHM_MAP = {
    "token_bucket": TokenBucketLimiter,
    "sliding_window": SlidingWindowLimiter,
    "fixed_window": FixedWindowLimiter,
}


class RateLimitManager:
    """限流管理器 - 根据路径匹配规则，分发到对应算法"""

    def __init__(self):
        self._rules: dict[str, dict] = {}  # path_pattern -> rule_config
        self._limiters: dict[str, object] = {}  # path_pattern -> limiter_instance
        self._default_limiter = TokenBucketLimiter(rate=1000, burst=2000)
        self._lock = threading.RLock()
        self._stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "rejected_requests": 0,
        }
        self._stats_lock = threading.RLock()
        # 事件回调
        self._event_callback = None

    def set_event_callback(self, callback):
        self._event_callback = callback

    async def load_rules(self, session: AsyncSession):
        """从数据库加载限流规则"""
        result = await session.execute(select(RateLimitRule).where(RateLimitRule.enabled == True))
        rules = result.scalars().all()

        with self._lock:
            self._rules.clear()
            self._limiters.clear()

            for rule in rules:
                algo_cls = ALGORITHM_MAP.get(rule.algorithm, TokenBucketLimiter)
                limiter = algo_cls(
                    rate=rule.rate,
                    burst=rule.burst,
                    window_size=rule.window_size,
                )
                self._rules[rule.path] = {
                    "id": rule.id,
                    "path": rule.path,
                    "method": rule.method,
                    "algorithm": rule.algorithm,
                    "rate": rule.rate,
                    "burst": rule.burst,
                    "window_size": rule.window_size,
                }
                self._limiters[rule.path] = limiter

        logger.info(f"已加载 {len(rules)} 条限流规则")

    def _match_rule(self, path: str) -> tuple[str | None, object | None]:
        """匹配路径对应的限流规则，优先精确匹配"""
        # 先找精确匹配
        if path in self._limiters:
            return path, self._limiters[path]

        # 再找通配符匹配（按规则长度排序，最长优先）
        matched = sorted(
            [p for p in self._limiters if '*' in p or '?' in p],
            key=len, reverse=True
        )
        for pattern in matched:
            if fnmatch.fnmatch(path, pattern):
                return pattern, self._limiters[pattern]

        return None, None

    def check(self, path: str, client_ip: str = "", method: str = "GET") -> RateLimitResult:
        """检查请求是否被限流"""
        with self._stats_lock:
            self._stats["total_requests"] += 1

        pattern, limiter = self._match_rule(path)
        if limiter is None:
            with self._stats_lock:
                self._stats["allowed_requests"] += 1
            return RateLimitResult(
                allowed=True,
                current_rate=0,
                limit_rate=0,
                remaining=999999,
                reason="无匹配规则",
            )

        key = f"{pattern}:{client_ip}" if client_ip else pattern
        result = limiter.allow(key)

        with self._stats_lock:
            if result.allowed:
                self._stats["allowed_requests"] += 1
            else:
                self._stats["rejected_requests"] += 1

        # 异步事件回调（非阻塞）
        if self._event_callback and not result.allowed:
            try:
                self._event_callback(path, client_ip, self._rules.get(pattern, {}), result)
            except Exception as e:
                logger.error(f"事件回调异常: {e}")

        return result

    def get_stats(self) -> dict:
        with self._stats_lock:
            return dict(self._stats)

    def get_rules(self) -> list[dict]:
        with self._lock:
            return list(self._rules.values())

    def update_rule(self, path: str, config: dict):
        """动态更新限流规则"""
        with self._lock:
            if path in self._limiters:
                algo = config.get("algorithm", "token_bucket")
                algo_cls = ALGORITHM_MAP.get(algo, TokenBucketLimiter)
                self._limiters[path] = algo_cls(
                    rate=config.get("rate", 100),
                    burst=config.get("burst", 100),
                    window_size=config.get("window_size", 60),
                )
                if path in self._rules:
                    self._rules[path].update(config)
                logger.info(f"限流规则已更新: {path} -> {config}")

    def remove_rule(self, path: str):
        with self._lock:
            self._limiters.pop(path, None)
            self._rules.pop(path, None)

    def get_limiter_info(self, path: str) -> dict:
        """获取限流器详细信息"""
        if path in self._limiters:
            limiter = self._limiters[path]
            if hasattr(limiter, "get_bucket_info"):
                return limiter.get_bucket_info(path)
            elif hasattr(limiter, "get_window_info"):
                return limiter.get_window_info(path)
        return {}
