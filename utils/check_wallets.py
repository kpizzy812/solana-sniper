#!/usr/bin/env python3
"""
💰 MORI Sniper Bot - Проверка балансов множественных кошельков
Проверяет балансы всех настроенных кошельков и показывает готовность к торговле
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from config.multi_wallet import MultiWalletConfig


class WalletChecker:
    """Проверяльщик балансов кошельков"""

    def __init__(self):
        self.config = MultiWalletConfig()
        self.solana_client = None

    async def start(self):
        """Инициализация подключения к Solana"""
        try:
            from config.settings import settings
            self.solana_client = AsyncClient(
                endpoint=settings.solana.rpc_url,
                commitment=Confirmed
            )
            logger.info(f"🔗 Подключение к Solana: {settings.solana.rpc_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Solana: {e}")
            return False

    async def stop(self):
        """Закрытие подключения"""
        if self.solana_client:
            await self.solana_client.close()

    async def check_all_wallets(self):
        """Проверка балансов всех кошельков"""
        if not self.config.is_enabled():
            logger.warning("⚠️ Система множественных кошельков отключена")
            logger.info("💡 Установите USE_MULTI_WALLET=true в .env для включения")
            return

        if not self.config.wallets:
            logger.error("❌ Кошельки не загружены")
            logger.info("💡 Проверьте MULTI_WALLET_PRIVATE_KEYS в .env")
            return

        logger.info(f"🔍 Проверка балансов {len(self.config.wallets)} кошельков...")
        print("=" * 80)

        # Получаем балансы параллельно
        balance_tasks = []
        for wallet in self.config.wallets:
            task = asyncio.create_task(self._get_balance_with_info(wallet))
            balance_tasks.append(task)

        results = await asyncio.gather(*balance_tasks, return_exceptions=True)

        # Обрабатываем результаты
        total_balance = 0.0
        total_available = 0.0
        ready_wallets = 0

        for i, (wallet, result) in enumerate(zip(self.config.wallets, results)):
            if isinstance(result, Exception):
                logger.error(f"❌ Кошелек {i + 1}: Ошибка - {result}")
                continue

            balance, status_emoji, status_text = result
            wallet.update_balance(balance)

            total_balance += balance
            total_available += wallet.available_balance

            if wallet.available_balance >= self.config.min_balance:
                ready_wallets += 1

            # Форматированный вывод
            print(f"{status_emoji} Кошелек {wallet.index}:")
            print(f"   Адрес: {wallet.address}")
            print(f"   Баланс: {balance:.6f} SOL")
            print(f"   Доступно: {wallet.available_balance:.6f} SOL ({status_text})")
            print(f"   Резерв газа: {wallet.reserved_gas:.6f} SOL")
            print()

        # Итоговая статистика
        self._print_summary(total_balance, total_available, ready_wallets)

    async def _get_balance_with_info(self, wallet):
        """Получение баланса с дополнительной информацией"""
        try:
            response = await self.solana_client.get_balance(wallet.keypair.pubkey())
            balance = response.value / 1e9 if response.value else 0.0

            # Определяем статус
            if balance < self.config.min_balance:
                return balance, "🔴", "Недостаточно средств"
            elif balance < self.config.min_balance * 2:
                return balance, "🟡", "Минимальный баланс"
            else:
                return balance, "🟢", "Готов к торговле"

        except Exception as e:
            raise Exception(f"Ошибка получения баланса: {e}")

    def _print_summary(self, total_balance: float, total_available: float, ready_wallets: int):
        """Печать итоговой сводки"""
        print("=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print("=" * 80)

        print(f"💰 Общий баланс: {total_balance:.6f} SOL (~${total_balance * 150:.0f})")
        print(f"💎 Доступно для торговли: {total_available:.6f} SOL")
        print(f"🎭 Готовых кошельков: {ready_wallets}/{len(self.config.wallets)}")
        print(f"⚙️ Минимальный баланс: {self.config.min_balance:.6f} SOL")
        print(f"⛽ Резерв газа: {self.config.gas_reserve:.6f} SOL на кошелек")
        print()

        # Рекомендации
        print("💡 РЕКОМЕНДАЦИИ:")

        if ready_wallets == 0:
            print("❌ НЕТ КОШЕЛЬКОВ ГОТОВЫХ К ТОРГОВЛЕ!")
            print("   - Пополните кошельки с CEX бирж")
            print("   - Минимум на каждый кошелек: 0.05+ SOL")
        elif ready_wallets < len(self.config.wallets) // 2:
            print("⚠️ Мало готовых кошельков для оптимального снайпинга")
            print("   - Пополните дополнительные кошельки")
            print("   - Рекомендуется 80%+ кошельков готовых")
        else:
            print("✅ Система готова к снайпингу!")
            print(f"   - Можно торговать на сумму до {total_available:.4f} SOL")
            print("   - Все настройки корректны")

        print()
        print("🔧 НАСТРОЙКИ:")
        print(f"   Стратегия: {self.config.distribution_strategy}")
        print(f"   Рандомизация: {self.config.randomize_amounts}")
        print(f"   Начальная задержка: {self.config.initial_delay_seconds}s")
        print(f"   Максимум сделок на кошелек: {self.config.max_trades_per_wallet}")

    async def quick_balance_check(self):
        """Быстрая проверка только общего баланса"""
        if not self.config.is_enabled():
            print("⚠️ Множественные кошельки отключены")
            return

        logger.info("⚡ Быстрая проверка балансов...")

        total_balance = 0.0
        ready_count = 0

        for wallet in self.config.wallets:
            try:
                response = await self.solana_client.get_balance(wallet.keypair.pubkey())
                balance = response.value / 1e9 if response.value else 0.0
                total_balance += balance

                if balance >= self.config.min_balance:
                    ready_count += 1

            except Exception:
                continue

        print(f"💰 Общий баланс: {total_balance:.4f} SOL")
        print(f"✅ Готовых кошельков: {ready_count}/{len(self.config.wallets)}")


async def main():
    """Главная функция"""
    print("💰 Проверка балансов множественных кошельков")
    print("=" * 60)

    checker = WalletChecker()

    try:
        # Инициализация
        if not await checker.start():
            sys.exit(1)

        # Выбор режима проверки
        mode = input("Выберите режим (1 - полная проверка, 2 - быстрая): ").strip()

        if mode == "2":
            await checker.quick_balance_check()
        else:
            await checker.check_all_wallets()

    except KeyboardInterrupt:
        print("\n❌ Проверка прервана пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки: {e}")
    finally:
        await checker.stop()


if __name__ == "__main__":
    asyncio.run(main())