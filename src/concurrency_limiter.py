"""并发限流器 - 使用 asyncio.Semaphore"""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ConcurrencyLimiter:
    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.active_requests = 0
        self.total_requests = 0
        logger.info(f"✅ 并发限流器初始化 (max={max_concurrency})")

    @asynccontextmanager
    async def acquire(self, timeout: Optional[float] = 30.0):
        self.total_requests += 1

        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout)
            self.active_requests += 1
            logger.info(f"🔑 获得许可，活跃: {self.active_requests}/{self.max_concurrency}")
            yield
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("请求排队超时（超过 30 秒），请稍后重试")
        finally:
            if self.active_requests > 0:
                self.semaphore.release()
                self.active_requests -= 1
                logger.info(f"🔓 释放资源，活跃: {self.active_requests}/{self.max_concurrency}")

    async def get_status(self) -> Dict[str, Any]:
        return {
            "max_concurrency": self.max_concurrency,
            "active_requests": self.active_requests,
            "available_slots": self.max_concurrency - self.active_requests,
            "total_requests": self.total_requests,
        }


_limiter_instance: Optional[ConcurrencyLimiter] = None


def get_limiter(max_concurrency: int = 5) -> ConcurrencyLimiter:
    global _limiter_instance
    if _limiter_instance is None:
        _limiter_instance = ConcurrencyLimiter(max_concurrency)
    return _limiter_instance
