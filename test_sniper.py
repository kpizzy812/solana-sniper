#!/usr/bin/env python3
"""
🧪 Тестовый скрипт для MORI Sniper Bot
Проверяет все компоненты системы перед запуском
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings
from ai.analyzer import analyzer
from trading.jupiter import jupiter_trader
from monitors.telegram import telegram_monitor
from monitors.twitter import twitter_monitor
from monitors.website import website_monitor


class SniperTester:
    """Тестер компонентов снайпер бота"""

    def __init__(self):
        self.test_results = {}

    async def run_all_tests(self):
        """Запуск всех тестов"""
        logger.info("🧪 Запуск тестирования MORI Sniper Bot")
        logger.info("=" * 50)

        # Тест конфигурации
        await self.test_configuration()

        # Тест AI анализатора
        await self.test_ai_analyzer()

        # Тест торговой системы
        await self.test_trading_system()

        # Тест мониторов
        await self.test_monitors()

        # Итоговый отчет
        self.print_summary()

    async def test_configuration(self):
        """Тест конфигурации"""
        logger.info("📋 Тестирование конфигурации...")

        try:
            # Проверяем обязательные параметры
            errors = []

            if not settings.solana.private_key:
                errors.append("SOLANA_PRIVATE_KEY не установлен")

            if not settings.monitoring.telegram_bot_token and not settings.monitoring.twitter_bearer_token:
                errors.append("Не установлен ни один API токен")

            if settings.trading.trade_amount_sol <= 0:
                errors.append("TRADE_AMOUNT_SOL должен быть больше 0")

            if errors:
                logger.error(f"❌ Ошибки конфигурации: {errors}")
                self.test_results['configuration'] = False
            else:
                logger.success("✅ Конфигурация в порядке")
                self.test_results['configuration'] = True

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования конфигурации: {e}")
            self.test_results['configuration'] = False

    async def test_ai_analyzer(self):
        """Тест AI анализатора"""
        logger.info("🤖 Тестирование AI анализатора...")

        try:
            # Тест быстрого анализа
            test_content = "Новый контракт: 11111111111111111111111111111114 - покупайте сейчас!"

            result = await analyzer.analyze_post(
                content=test_content,
                platform="test",
                author="tester"
            )

            if result.has_contract and len(result.addresses) > 0:
                logger.success(f"✅ AI анализатор работает: найден контракт {result.addresses}")
                self.test_results['ai_analyzer'] = True
            else:
                logger.warning("⚠️ AI анализатор не нашел тестовый контракт")
                self.test_results['ai_analyzer'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования AI анализатора: {e}")
            self.test_results['ai_analyzer'] = False

    async def test_trading_system(self):
        """Тест торговой системы"""
        logger.info("💰 Тестирование торговой системы...")

        try:
            # Инициализация трейдера
            if await jupiter_trader.start():
                logger.info("🔗 Подключение к Jupiter API...")

                # Проверка health check
                health = await jupiter_trader.health_check()

                if health.get('status') == 'healthy':
                    logger.success("✅ Торговая система готова")
                    logger.info(f"  💼 Адрес кошелька: {health.get('wallet_address')}")
                    logger.info(f"  💰 Баланс SOL: {health.get('sol_balance', 0):.4f}")
                    self.test_results['trading_system'] = True
                else:
                    logger.warning(f"⚠️ Проблемы с торговой системой: {health.get('status')}")
                    self.test_results['trading_system'] = False

                await jupiter_trader.stop()
            else:
                logger.error("❌ Не удалось запустить торговую систему")
                self.test_results['trading_system'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования торговой системы: {e}")
            self.test_results['trading_system'] = False

    async def test_monitors(self):
        """Тест всех мониторов"""
        logger.info("👁️ Тестирование мониторов...")

        # Тест Telegram монитора
        await self.test_telegram_monitor()

        # Тест Twitter монитора
        await self.test_twitter_monitor()

        # Тест Website монитора
        await self.test_website_monitor()

    async def test_telegram_monitor(self):
        """Тест Telegram монитора"""
        try:
            if settings.monitoring.telegram_bot_token:
                if await telegram_monitor.start():
                    health = await telegram_monitor.health_check()
                    if health.get('status') == 'healthy':
                        logger.success(f"✅ Telegram монитор: @{health.get('bot_username')}")
                        self.test_results['telegram_monitor'] = True
                    else:
                        logger.warning("⚠️ Проблемы с Telegram монитором")
                        self.test_results['telegram_monitor'] = False
                    await telegram_monitor.stop()
                else:
                    logger.error("❌ Не удалось запустить Telegram монитор")
                    self.test_results['telegram_monitor'] = False
            else:
                logger.info("⏭️ Telegram токен не настроен, пропускаем")
                self.test_results['telegram_monitor'] = None

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Telegram: {e}")
            self.test_results['telegram_monitor'] = False

    async def test_twitter_monitor(self):
        """Тест Twitter монитора"""
        try:
            if settings.monitoring.twitter_bearer_token:
                if await twitter_monitor.start():
                    health = await twitter_monitor.health_check()
                    if health.get('status') == 'healthy':
                        logger.success("✅ Twitter монитор работает")
                        self.test_results['twitter_monitor'] = True
                    else:
                        logger.warning("⚠️ Проблемы с Twitter монитором")
                        self.test_results['twitter_monitor'] = False
                    await twitter_monitor.stop()
                else:
                    logger.error("❌ Не удалось запустить Twitter монитор")
                    self.test_results['twitter_monitor'] = False
            else:
                logger.info("⏭️ Twitter токен не настроен, пропускаем")
                self.test_results['twitter_monitor'] = None

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Twitter: {e}")
            self.test_results['twitter_monitor'] = False

    async def test_website_monitor(self):
        """Тест Website монитора"""
        try:
            if settings.monitoring.website_urls and any(settings.monitoring.website_urls):
                if await website_monitor.start():
                    health = await website_monitor.health_check()
                    if health.get('status') in ['healthy', 'degraded']:
                        logger.success("✅ Website монитор работает")
                        self.test_results['website_monitor'] = True
                    else:
                        logger.warning("⚠️ Проблемы с Website монитором")
                        self.test_results['website_monitor'] = False
                    await website_monitor.stop()
                else:
                    logger.error("❌ Не удалось запустить Website монитор")
                    self.test_results['website_monitor'] = False
            else:
                logger.info("⏭️ Website URLs не настроены, пропускаем")
                self.test_results['website_monitor'] = None

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Website: {e}")
            self.test_results['website_monitor'] = False

    def print_summary(self):
        """Печать итогового отчета"""
        logger.info("\n" + "=" * 50)
        logger.info("📊 ИТОГИ ТЕСТИРОВАНИЯ")
        logger.info("=" * 50)

        total_tests = 0
        passed_tests = 0

        for component, result in self.test_results.items():
            if result is None:
                status = "⏭️ ПРОПУЩЕН"
            elif result:
                status = "✅ ПРОЙДЕН"
                passed_tests += 1
                total_tests += 1
            else:
                status = "❌ ПРОВАЛЕН"
                total_tests += 1

            logger.info(f"{component.replace('_', ' ').title():<20} {status}")

        logger.info("=" * 50)

        if total_tests == 0:
            logger.warning("⚠️ Все тесты пропущены - проверьте конфигурацию")
        elif passed_tests == total_tests:
            logger.success(f"🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({passed_tests}/{total_tests})")
            logger.success("🚀 Система готова к запуску: python main.py")
        else:
            logger.warning(f"⚠️ Тесты пройдены частично ({passed_tests}/{total_tests})")
            logger.info("🔧 Исправьте ошибки перед запуском системы")


async def main():
    """Главная функция"""
    tester = SniperTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(main())