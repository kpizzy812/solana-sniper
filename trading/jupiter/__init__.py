"""
🎯 MORI Sniper Bot - Jupiter Trading Module
Главный модуль для торговли через Jupiter DEX
"""

import aiohttp
from typing import Dict, List, Optional
from loguru import logger

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from config.settings import settings
from .models import TradeResult, PoolInfo
from .client import JupiterAPIClient
from .executor import JupiterTradeExecutor
from .security import JupiterSecurityChecker


class UltraFastJupiterTrader:
    """Ультра-быстрая торговая система Jupiter с модульной архитектурой"""

    def __init__(self):
        # Основные компоненты
        self.solana_client: Optional[AsyncClient] = None
        self.jupiter_client: Optional[JupiterAPIClient] = None
        self.executor: Optional[JupiterTradeExecutor] = None
        self.security_checker: Optional[JupiterSecurityChecker] = None

        # Состояние системы
        self.running = False

        # Статистика (агрегированная из executor)
        self._stats_cache = {}

    async def start(self) -> bool:
        """Инициализация торговой системы"""
        try:
            logger.info("🚀 Запуск Jupiter торговой системы...")

            # 1. Настройка Solana RPC клиента
            self.solana_client = AsyncClient(
                endpoint=settings.solana.rpc_url,
                commitment=Confirmed
            )
            logger.debug("✅ Solana RPC клиент инициализирован")

            # 2. Инициализация Jupiter API клиента
            self.jupiter_client = JupiterAPIClient()
            await self.jupiter_client.start()
            logger.debug("✅ Jupiter API клиент запущен")

            # 3. Инициализация исполнителя сделок
            self.executor = JupiterTradeExecutor(
                solana_client=self.solana_client,
                jupiter_client=self.jupiter_client
            )
            logger.debug("✅ Исполнитель сделок инициализирован")

            # 4. Инициализация системы безопасности
            self.security_checker = JupiterSecurityChecker(
                jupiter_client=self.jupiter_client
            )
            logger.debug("✅ Система безопасности инициализирована")

            # 5. Тестируем соединения
            health = await self.health_check()
            if health['status'] != 'healthy':
                raise Exception(f"Проблемы с подключением: {health}")

            self.running = True
            logger.success("✅ Jupiter торговая система запущена успешно")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Jupiter трейдера: {e}")
            await self.stop()
            return False

    async def stop(self):
        """Остановка и очистка ресурсов"""
        logger.info("🛑 Остановка Jupiter торговой системы...")

        self.running = False

        try:
            # Останавливаем Jupiter API клиент
            if self.jupiter_client:
                await self.jupiter_client.stop()
                logger.debug("✅ Jupiter API клиент остановлен")

            # Закрываем Solana RPC клиент
            if self.solana_client:
                await self.solana_client.close()
                logger.debug("✅ Solana RPC клиент закрыт")

        except Exception as e:
            logger.warning(f"⚠️ Ошибки при остановке: {e}")

        logger.info("🛑 Jupiter торговая система остановлена")

    async def execute_sniper_trades(self, token_address: str, source_info: Dict) -> List[TradeResult]:
        """
        Главный метод для выполнения снайперских сделок

        Args:
            token_address: Адрес токена для покупки
            source_info: Информация об источнике сигнала

        Returns:
            List[TradeResult]: Результаты всех сделок
        """
        if not self.running:
            logger.error("❌ Торговая система не запущена")
            return []

        if not self.executor:
            logger.error("❌ Исполнитель сделок не инициализирован")
            return []

        try:
            logger.critical(f"🚨 ПОЛУЧЕН ТОРГОВЫЙ СИГНАЛ: {token_address}")
            logger.info(
                f"📱 Источник: {source_info.get('platform', 'unknown')} - {source_info.get('source', 'unknown')}")

            # Предварительная проверка безопасности
            if settings.security.enable_security_checks and self.security_checker:
                logger.info("🔍 Выполняем проверки безопасности...")

                is_safe = await self.security_checker.security_check(token_address)
                if not is_safe:
                    logger.error(f"❌ Токен {token_address} не прошел проверку безопасности")
                    return []

                logger.success("✅ Проверки безопасности пройдены")

            # Выполняем снайперские сделки
            results = await self.executor.execute_sniper_trades(token_address, source_info)

            # Обновляем кэш статистики
            self._update_stats_cache()

            return results

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения снайперских сделок: {e}")
            return []

    async def get_pool_info(self, token_address: str) -> Optional[PoolInfo]:
        """Получение информации о ликвидности токена"""
        if not self.security_checker:
            logger.error("❌ Система безопасности не инициализирована")
            return None

        return await self.security_checker.get_pool_info(token_address)

    async def security_check(self, token_address: str) -> bool:
        """Проверка безопасности токена"""
        if not self.security_checker:
            logger.warning("⚠️ Система безопасности не инициализирована, пропускаем проверку")
            return True

        return await self.security_checker.security_check(token_address)

    async def get_sol_balance(self) -> float:
        """Получение баланса SOL кошелька"""
        if not self.executor:
            logger.error("❌ Исполнитель сделок не инициализирован")
            return 0.0

        return await self.executor.get_sol_balance()

    async def health_check(self) -> Dict:
        """Проверка здоровья всей торговой системы"""
        try:
            health_data = {
                "status": "healthy",
                "components": {},
                "wallet_info": {},
                "stats": {}
            }

            # Проверяем Solana RPC
            try:
                if self.solana_client:
                    response = await self.solana_client.get_version()
                    health_data["components"]["solana_rpc"] = "healthy" if response.value else "error"
                else:
                    health_data["components"]["solana_rpc"] = "not_initialized"
            except Exception as e:
                health_data["components"]["solana_rpc"] = f"error: {e}"
                logger.error(f"❌ Ошибка подключения к Solana RPC: {e}")

            # Проверяем Jupiter API
            try:
                if self.jupiter_client:
                    jupiter_health = await self.jupiter_client.health_check()
                    health_data["components"]["jupiter_api"] = jupiter_health.get("jupiter_api", "unknown")
                    health_data["jupiter_endpoint"] = jupiter_health.get("jupiter_endpoint", "unknown")
                else:
                    health_data["components"]["jupiter_api"] = "not_initialized"
            except Exception as e:
                health_data["components"]["jupiter_api"] = f"error: {e}"
                logger.error(f"❌ Ошибка подключения к Jupiter API: {e}")

            # Информация о кошельке
            try:
                if self.executor and self.executor.wallet_keypair:
                    health_data["wallet_info"]["address"] = str(self.executor.wallet_keypair.pubkey())
                    health_data["wallet_info"]["sol_balance"] = await self.get_sol_balance()
                else:
                    health_data["wallet_info"]["address"] = "not_configured"
                    health_data["wallet_info"]["sol_balance"] = 0.0
            except Exception as e:
                health_data["wallet_info"]["error"] = str(e)

            # Статистика торговли
            if self.executor:
                health_data["stats"] = self.executor.get_stats()

            # Определяем общий статус
            component_statuses = list(health_data["components"].values())
            if any("error" in str(status) for status in component_statuses):
                health_data["status"] = "degraded"
            elif any("not_initialized" in str(status) for status in component_statuses):
                health_data["status"] = "degraded"

            return health_data

        except Exception as e:
            logger.error(f"❌ Ошибка health check: {e}")
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики торговли"""
        if self.executor:
            return self.executor.get_stats()
        return {}

    def _update_stats_cache(self):
        """Обновление кэша статистики"""
        if self.executor:
            self._stats_cache = self.executor.get_stats()

    def reset_stats(self):
        """Сброс статистики торговли"""
        if self.executor:
            self.executor.reset_stats()
        self._stats_cache = {}

    def clear_cache(self):
        """Очистка всех кэшей"""
        if self.jupiter_client:
            self.jupiter_client.clear_cache()
        if self.security_checker:
            self.security_checker.clear_cache()
        logger.info("🧹 Все кэши очищены")

    async def estimate_liquidity(self, token_address: str) -> float:
        """Оценка ликвидности токена"""
        if not self.security_checker:
            logger.warning("⚠️ Система безопасности не инициализирована")
            return 0.0

        return await self.security_checker.estimate_liquidity(token_address)

    async def comprehensive_security_check(self, token_address: str) -> Dict:
        """Комплексная проверка безопасности токена"""
        if not self.security_checker:
            logger.warning("⚠️ Система безопасности не инициализирована")
            return {"overall_safe": True, "reason": "security_disabled"}

        return await self.security_checker.comprehensive_security_check(token_address)

    def is_running(self) -> bool:
        """Проверка состояния системы"""
        return self.running

    def get_component_status(self) -> Dict:
        """Получение статуса всех компонентов"""
        return {
            "solana_client": self.solana_client is not None,
            "jupiter_client": self.jupiter_client is not None,
            "executor": self.executor is not None,
            "security_checker": self.security_checker is not None,
            "running": self.running
        }


# Глобальный экземпляр трейдера (для совместимости с существующим кодом)
jupiter_trader = UltraFastJupiterTrader()

# Экспорт для удобного импорта
__all__ = [
    'UltraFastJupiterTrader',
    'jupiter_trader',
    'TradeResult',
    'PoolInfo'
]