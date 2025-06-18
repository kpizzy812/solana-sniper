#!/usr/bin/env python3
"""
🧪 MORI Sniper Bot - Тест системы множественных кошельков
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings
from config.multi_wallet import MultiWalletConfig
from trading.jupiter import jupiter_trader


class MultiWalletTester:
    def __init__(self):
        self.test_results = {}

    async def run_all_tests(self):
        logger.info("🧪 Тестирование системы множественных кошельков")
        logger.info("=" * 60)

        await self.test_multi_wallet_config()
        await self.test_jupiter_integration()
        await self.test_balance_checks()
        await self.test_distribution_logic()

        self.print_summary()

    async def test_multi_wallet_config(self):
        logger.info("⚙️ Тестирование конфигурации...")

        try:
            config = MultiWalletConfig()

            if not config.is_enabled():
                logger.warning("⚠️ Множественные кошельки отключены")
                self.test_results['config'] = False
                return

            if not config.wallets:
                logger.error("❌ Кошельки не загружены")
                self.test_results['config'] = False
                return

            logger.success(f"✅ Загружено {len(config.wallets)} кошельков")
            self.test_results['config'] = True

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования конфигурации: {e}")
            self.test_results['config'] = False

    async def test_jupiter_integration(self):
        logger.info("🚀 Тестирование интеграции с Jupiter...")

        try:
            success = await jupiter_trader.start()

            if success:
                logger.success("✅ Jupiter торговая система запущена")

                health = await jupiter_trader.health_check()
                multi_wallet_status = health.get('components', {}).get('multi_wallet', 'not_found')

                if multi_wallet_status == 'healthy':
                    logger.success("✅ Система множественных кошельков интегрирована")
                    self.test_results['jupiter_integration'] = True
                elif multi_wallet_status == 'not_found':
                    logger.info("📱 Используется стандартный режим торговли")
                    self.test_results['jupiter_integration'] = True
                else:
                    logger.warning(f"⚠️ Проблемы с множественными кошельками: {multi_wallet_status}")
                    self.test_results['jupiter_integration'] = False

                await jupiter_trader.stop()
            else:
                logger.error("❌ Не удалось запустить Jupiter")
                self.test_results['jupiter_integration'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Jupiter: {e}")
            self.test_results['jupiter_integration'] = False

    async def test_balance_checks(self):
        logger.info("💰 Тестирование проверки балансов...")

        try:
            config = MultiWalletConfig()

            if not config.is_enabled():
                self.test_results['balance_checks'] = None
                return

            await jupiter_trader.start()

            if jupiter_trader.multi_wallet_manager:
                await jupiter_trader.multi_wallet_manager.update_all_balances()

                total_balance = config.get_total_available_balance()
                available_wallets = len(config.get_available_wallets())

                logger.info(f"💎 Общий баланс: {total_balance:.4f} SOL")
                logger.info(f"✅ Готовых кошельков: {available_wallets}/{len(config.wallets)}")

                self.test_results['balance_checks'] = available_wallets > 0
            else:
                self.test_results['balance_checks'] = False

            await jupiter_trader.stop()

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования балансов: {e}")
            self.test_results['balance_checks'] = False

    async def test_distribution_logic(self):
        logger.info("🎲 Тестирование логики распределения...")

        try:
            config = MultiWalletConfig()

            if not config.is_enabled():
                self.test_results['distribution_logic'] = None
                return

            test_amount = 0.1

            for i in range(3):
                wallet = config.select_wallet_for_trade(test_amount)
                if wallet:
                    logger.info(f"🎯 Тест {i + 1}: Выбран кошелек {wallet.index}")
                else:
                    logger.warning(f"⚠️ Тест {i + 1}: Не найден подходящий кошелек")

            # Тест рандомизации
            base_amount = 0.1
            for i in range(3):
                randomized = config.randomize_trade_amount(base_amount)
                variation = ((randomized - base_amount) / base_amount) * 100
                logger.info(f"💰 {base_amount} SOL → {randomized:.4f} SOL ({variation:+.1f}%)")

            logger.success("✅ Логика распределения работает")
            self.test_results['distribution_logic'] = True

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования распределения: {e}")
            self.test_results['distribution_logic'] = False

    def print_summary(self):
        logger.info("\n" + "=" * 60)
        logger.info("📊 ИТОГИ ТЕСТИРОВАНИЯ")
        logger.info("=" * 60)

        total_tests = 0
        passed_tests = 0

        for test_name, result in self.test_results.items():
            if result is None:
                status = "⏭️ ПРОПУЩЕН"
            elif result:
                status = "✅ ПРОЙДЕН"
                passed_tests += 1
                total_tests += 1
            else:
                status = "❌ ПРОВАЛЕН"
                total_tests += 1

            logger.info(f"{test_name.replace('_', ' ').title():<25} {status}")

        if passed_tests == total_tests and total_tests > 0:
            logger.success(f"🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({passed_tests}/{total_tests})")
        elif total_tests == 0:
            logger.warning("⚠️ Все тесты пропущены - система отключена")
        else:
            logger.warning(f"⚠️ Тесты пройдены частично ({passed_tests}/{total_tests})")


async def main():
    tester = MultiWalletTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())