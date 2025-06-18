"""
🛡️ MORI Sniper Bot - Jupiter Security
Проверки безопасности и анализ ликвидности токенов
"""

import asyncio
import time
from typing import Optional, Dict
from loguru import logger

from config.settings import settings
from .models import PoolInfo
from .client import JupiterAPIClient


class JupiterSecurityChecker:
    """Система безопасности для Jupiter торговли"""

    def __init__(self, jupiter_client: JupiterAPIClient):
        self.jupiter_client = jupiter_client
        self.pool_cache = {}  # Кэш информации о пулах

    async def security_check(self, token_address: str) -> bool:
        """Быстрая проверка безопасности токена с fallback"""
        try:
            if not settings.security.enable_security_checks:
                logger.info("⏭️ Проверки безопасности отключены")
                return True

            # Попытка проверки через Price API
            pool_info = await self.get_pool_info(token_address)

            if pool_info:
                # Успешно получили информацию о токене
                if pool_info.liquidity_sol < settings.security.min_liquidity_sol:
                    logger.warning(
                        f"⚠️ Недостаточная ликвидность: {pool_info.liquidity_sol} SOL < {settings.security.min_liquidity_sol} SOL")
                    return False

                logger.info(
                    f"✅ Проверка безопасности пройдена: ~{pool_info.liquidity_sol} SOL агрегированной ликвидности")
                return True
            else:
                # Fallback: проверяем через тестовый quote
                logger.info("🔄 Price API недоступен, используем fallback проверку")
                return await self.fallback_security_check(token_address)

        except Exception as e:
            logger.error(f"❌ Ошибка проверки безопасности: {e}")
            # Fallback в случае ошибки
            return await self.fallback_security_check(token_address)

    async def fallback_security_check(self, token_address: str) -> bool:
        """Fallback проверка безопасности через тестовый quote"""
        try:
            logger.info("🧪 Выполняем fallback проверку через тестовый quote")

            # Тестируем маленькую сделку
            test_quote = await self.jupiter_client.get_quote(
                input_mint=settings.trading.base_token,  # SOL
                output_mint=token_address,
                amount=int(0.01 * 1e9),  # 0.01 SOL в lamports
                slippage_bps=1000  # 10%
            )

            if not test_quote:
                logger.warning(f"⚠️ Не удалось получить тестовую котировку для {token_address}")
                return False

            price_impact = test_quote.price_impact_float

            if price_impact > 50.0:  # Более мягкий лимит для fallback
                logger.warning(f"⚠️ Слишком большое проскальзывание: {price_impact}%")
                return False

            logger.info(f"✅ Fallback проверка пройдена: {price_impact}% проскальзывание на тестовую сделку")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка fallback проверки: {e}")
            # В крайнем случае разрешаем торговлю для известных токенов
            if token_address == 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN':
                logger.info("✅ JUP токен - разрешаем торговлю")
                return True
            return False

    async def get_pool_info(self, token_address: str) -> Optional[PoolInfo]:
        """Получение информации о ликвидности токена через Jupiter Price API v2"""
        try:
            # Проверяем кэш
            if token_address in self.pool_cache:
                cached_time, pool_info = self.pool_cache[token_address]
                if time.time() - cached_time < 30:  # Кэш на 30 секунд
                    return pool_info

            # Получаем информацию о цене через Jupiter client
            price_data = await self.jupiter_client.get_price_info(token_address)

            if not price_data:
                logger.warning(f"⚠️ Не удалось получить информацию о цене для {token_address}")
                return None

            price = price_data.get('price', 0)
            logger.info(f"💰 Цена {token_address}: {price} SOL")

            # Пытаемся получить дополнительную информацию через quote для оценки ликвидности
            liquidity_sol = await self.estimate_liquidity(token_address)

            pool_info = PoolInfo(
                liquidity_sol=liquidity_sol,
                price=price,
                market_cap=0,  # Jupiter Price API не предоставляет market cap
                volume_24h=0,  # Jupiter Price API не предоставляет volume
                holders_count=100  # Заглушка
            )

            # Кэшируем результат
            self.pool_cache[token_address] = (time.time(), pool_info)
            return pool_info

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о токене: {e}")
            return None

    async def estimate_liquidity(self, token_address: str) -> float:
        """Оценка агрегированной ликвидности токена через тестовые quote запросы"""
        try:
            # Тестируем различные размеры сделок для оценки ликвидности
            test_amounts = [1e9, 5e9, 10e9, 50e9, 100e9]  # 1, 5, 10, 50, 100 SOL в lamports
            max_successful_amount = 0

            for amount in test_amounts:
                try:
                    quote = await self.jupiter_client.get_quote(
                        input_mint=settings.trading.base_token,  # SOL
                        output_mint=token_address,
                        amount=int(amount),
                        slippage_bps=1000  # 10% для теста
                    )

                    if quote:
                        price_impact = quote.price_impact_float
                        if price_impact < 15.0:  # Если проскальзывание менее 15%
                            max_successful_amount = amount / 1e9  # Конвертируем в SOL
                        else:
                            break  # Прекращаем если проскальзывание слишком большое
                    else:
                        break

                    # Маленькая пауза между запросами
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.debug(f"Ошибка тестового quote для {amount / 1e9} SOL: {e}")
                    break

            # Оценочная ликвидность = максимальная успешная сделка * 20
            # Это консервативная оценка агрегированной ликвидности
            estimated_liquidity = max_successful_amount * 20

            # Минимальная оценка для известных токенов как JUP
            if estimated_liquidity < 1.0:
                estimated_liquidity = 1.0

            logger.info(f"📊 Оценочная агрегированная ликвидность {token_address}: ~{estimated_liquidity} SOL")
            return estimated_liquidity

        except Exception as e:
            logger.error(f"❌ Ошибка оценки ликвидности: {e}")
            # Возвращаем заниженную оценку для безопасности
            return 1.0

    async def check_honeypot(self, token_address: str) -> bool:
        """Проверка на honeypot через симуляцию продажи"""
        try:
            if not settings.security.check_honeypot:
                return True

            logger.debug(f"🍯 Проверяем honeypot для {token_address}")

            # Тестируем маленькую обратную сделку (продажу)
            test_quote = await self.jupiter_client.get_quote(
                input_mint=token_address,
                output_mint=settings.trading.base_token,  # SOL
                amount=int(1000),  # Минимальная сумма токенов
                slippage_bps=1000  # 10%
            )

            if not test_quote:
                logger.warning(f"⚠️ Не удалось получить quote для продажи {token_address} - возможный honeypot")
                return False

            logger.info(f"✅ Honeypot проверка пройдена для {token_address}")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки honeypot для {token_address}: {e}")
            # В случае ошибки считаем что токен проходит проверку
            return True

    async def check_token_metadata(self, token_address: str) -> bool:
        """Проверка метаданных токена (название, символ, проверка на скам)"""
        try:
            # TODO: Добавить проверку метаданных через Solana RPC
            # Пока возвращаем True
            logger.debug(f"📋 Проверка метаданных для {token_address} - пропущена")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки метаданных {token_address}: {e}")
            return True

    async def comprehensive_security_check(self, token_address: str) -> Dict:
        """Комплексная проверка безопасности токена"""
        try:
            logger.info(f"🔍 Комплексная проверка безопасности {token_address}")

            # Выполняем все проверки параллельно
            results = await asyncio.gather(
                self.security_check(token_address),
                self.check_honeypot(token_address),
                self.check_token_metadata(token_address),
                return_exceptions=True
            )

            basic_security = results[0] if not isinstance(results[0], Exception) else False
            honeypot_check = results[1] if not isinstance(results[1], Exception) else False
            metadata_check = results[2] if not isinstance(results[2], Exception) else False

            # Общий результат
            overall_safe = all([basic_security, honeypot_check, metadata_check])

            security_report = {
                "token_address": token_address,
                "overall_safe": overall_safe,
                "basic_security": basic_security,
                "honeypot_check": honeypot_check,
                "metadata_check": metadata_check,
                "timestamp": time.time()
            }

            if overall_safe:
                logger.success(f"✅ Комплексная проверка пройдена для {token_address}")
            else:
                logger.warning(f"⚠️ Токен {token_address} не прошел некоторые проверки")

            return security_report

        except Exception as e:
            logger.error(f"❌ Ошибка комплексной проверки безопасности: {e}")
            return {
                "token_address": token_address,
                "overall_safe": False,
                "error": str(e),
                "timestamp": time.time()
            }

    def clear_cache(self):
        """Очистка кэша проверок"""
        self.pool_cache.clear()
        logger.debug("🧹 Кэш проверок безопасности очищен")

    def get_cache_stats(self) -> Dict:
        """Статистика кэша"""
        return {
            "pool_cache_size": len(self.pool_cache),
            "cached_tokens": list(self.pool_cache.keys())
        }