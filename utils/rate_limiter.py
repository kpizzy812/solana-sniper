"""
⚡ Rate Limiter для Solana RPC и Jupiter API
Оптимизированный для 59 кошельков + платные API
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class RateLimit:
    """Настройки лимита запросов"""
    requests_per_second: float
    max_burst: int = 10  # Максимум запросов в burst режиме

    def __post_init__(self):
        self.interval = 1.0 / self.requests_per_second
        self.tokens = self.max_burst
        self.last_update = time.time()


class AsyncRateLimiter:
    """Асинхронный rate limiter с token bucket алгоритмом"""

    def __init__(self, rate_limit: RateLimit):
        self.rate_limit = rate_limit
        self.tokens = rate_limit.max_burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Ожидание разрешения на выполнение запроса"""
        async with self._lock:
            now = time.time()

            # Добавляем токены на основе прошедшего времени
            elapsed = now - self.last_update
            self.tokens = min(
                self.rate_limit.max_burst,
                self.tokens + elapsed / self.rate_limit.interval
            )
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return

            # Ждем до следующего доступного токена
            wait_time = self.rate_limit.interval
            logger.debug(f"⏳ Rate limit: ожидание {wait_time:.3f}s")
            await asyncio.sleep(wait_time)
            self.tokens = 0


class GlobalRateLimitManager:
    """Глобальный менеджер rate limitов для всех API"""

    def __init__(self):
        self.limiters: Dict[str, AsyncRateLimiter] = {}
        self._setup_limiters()

    def _setup_limiters(self):
        """Настройка лимитеров на основе конфигурации"""
        from config.settings import settings

        # Solana RPC Rate Limiter
        solana_rps = getattr(settings.solana, 'max_rpc_requests_per_second', 45)
        self.limiters['solana_rpc'] = AsyncRateLimiter(
            RateLimit(requests_per_second=solana_rps, max_burst=15)
        )
        logger.info(f"🔄 Solana RPC Rate Limiter: {solana_rps} req/s")

        # Jupiter API Rate Limiter (только для бесплатного)
        if not settings.jupiter.api_key or settings.jupiter.use_lite_api:
            self.limiters['jupiter_api'] = AsyncRateLimiter(
                RateLimit(requests_per_second=1.0, max_burst=3)  # Бесплатный = 60/min
            )
            logger.info("🔄 Jupiter API Rate Limiter: 1 req/s (бесплатный)")
        else:
            logger.info("🚀 Jupiter API: платный режим (без лимитов)")

    async def acquire(self, service: str) -> None:
        """Получение разрешения на запрос к сервису"""
        if service in self.limiters:
            await self.limiters[service].acquire()


# Глобальный экземпляр
rate_limit_manager = GlobalRateLimitManager()


# Декоратор для автоматического применения rate limiting
def rate_limited(service: str):
    """Декоратор для применения rate limiting к функциям"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            await rate_limit_manager.acquire(service)
            return await func(*args, **kwargs)

        return wrapper

    return decorator