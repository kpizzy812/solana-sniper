#!/usr/bin/env python3
"""
💰 MORI Sniper Bot - Проверка балансов множественных кошельков
Проверяет балансы всех настроенных кошельков и показывает готовность к торговле
"""

import asyncio
import sys
from pathlib import Path
from typing import Tuple, Optional
import time

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

        # Настройки для rate limiting
        self.max_concurrent_requests = 10  # Максимум одновременных запросов
        self.batch_size = 5  # Размер батча для обработки
        self.batch_delay = 0.5  # Задержка между батчами
        self.retry_attempts = 3  # Количество повторных попыток
        self.retry_delay = 1.0  # Начальная задержка для retry

    async def start(self):
        """Инициализация подключения к Solana"""
        try:
            from config.settings import settings
            self.solana_client = AsyncClient(
                endpoint=settings.solana.rpc_url,
                commitment=Confirmed,
                timeout=2  # Увеличиваем таймаут
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
        """Проверка балансов всех кошельков с батчинг и rate limiting"""
        if not self.config.is_enabled():
            logger.warning("⚠️ Система множественных кошельков отключена")
            logger.info("💡 Установите USE_MULTI_WALLET=true в .env для включения")
            return

        if not self.config.wallets:
            logger.error("❌ Кошельки не загружены")
            logger.info("💡 Проверьте MULTI_WALLET_PRIVATE_KEYS в .env")
            return

        logger.info(f"🔍 Проверка балансов {len(self.config.wallets)} кошельков...")
        logger.info(f"⚙️ Настройки: батчи по {self.batch_size}, макс. {self.max_concurrent_requests} одновременно")
        print("=" * 80)

        # Создаем семафор для ограничения одновременных запросов
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        # Разбиваем кошельки на батчи
        wallets = self.config.wallets
        total_balance = 0.0
        total_available = 0.0
        ready_wallets = 0
        failed_wallets = 0

        for i in range(0, len(wallets), self.batch_size):
            batch = wallets[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(wallets) + self.batch_size - 1) // self.batch_size

            logger.info(f"📦 Обрабатываем батч {batch_num}/{total_batches} ({len(batch)} кошельков)")

            # Обрабатываем батч параллельно с ограничениями
            batch_tasks = []
            for wallet in batch:
                task = asyncio.create_task(self._get_balance_with_retry(wallet, semaphore))
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Обрабатываем результаты батча
            for wallet, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Кошелек {wallet.index}: Критическая ошибка - {result}")
                    failed_wallets += 1
                    continue

                balance, status_emoji, status_text, success = result

                if not success:
                    logger.error(
                        f"❌ Кошелек {wallet.index}: Не удалось получить баланс после {self.retry_attempts} попыток")
                    failed_wallets += 1
                    continue

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

            # Задержка между батчами для снижения нагрузки
            if i + self.batch_size < len(wallets):
                logger.debug(f"⏳ Пауза {self.batch_delay}s между батчами...")
                await asyncio.sleep(self.batch_delay)

        # Итоговая статистика
        self._print_summary(total_balance, total_available, ready_wallets, failed_wallets)

    async def _get_balance_with_retry(self, wallet, semaphore) -> Tuple[float, str, str, bool]:
        """Получение баланса с повторными попытками и rate limiting"""
        async with semaphore:  # Ограничиваем количество одновременных запросов

            for attempt in range(self.retry_attempts):
                try:
                    # Получаем баланс
                    response = await self.solana_client.get_balance(wallet.keypair.pubkey())
                    balance = response.value / 1e9 if response.value else 0.0

                    # Определяем статус
                    if balance < self.config.min_balance:
                        return balance, "🔴", "Недостаточно средств", True
                    elif balance < self.config.min_balance * 2:
                        return balance, "🟡", "Минимальный баланс", True
                    else:
                        return balance, "🟢", "Готов к торговле", True

                except asyncio.TimeoutError:
                    error_msg = f"Таймаут запроса (попытка {attempt + 1}/{self.retry_attempts})"
                    logger.warning(f"⏱️ Кошелек {wallet.index}: {error_msg}")

                except Exception as e:
                    error_msg = f"Ошибка RPC: {str(e)} (попытка {attempt + 1}/{self.retry_attempts})"
                    logger.warning(f"⚠️ Кошелек {wallet.index}: {error_msg}")

                # Если не последняя попытка, ждем перед повтором
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Экспоненциальная задержка
                    logger.debug(f"🔄 Повтор через {delay:.1f}s для кошелька {wallet.index}")
                    await asyncio.sleep(delay)

            # Все попытки исчерпаны
            return 0.0, "❌", "Ошибка получения баланса", False

    def _print_summary(self, total_balance: float, total_available: float, ready_wallets: int, failed_wallets: int):
        """Печать итоговой сводки"""
        print("=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print("=" * 80)

        successful_wallets = len(self.config.wallets) - failed_wallets

        print(f"💰 Общий баланс: {total_balance:.6f} SOL (~${total_balance * 150:.0f})")
        print(f"💎 Доступно для торговли: {total_available:.6f} SOL")
        print(f"🎭 Готовых кошельков: {ready_wallets}/{successful_wallets}")
        print(f"✅ Успешно проверено: {successful_wallets}/{len(self.config.wallets)}")

        if failed_wallets > 0:
            print(f"❌ Ошибок при проверке: {failed_wallets}")

        print(f"⚙️ Минимальный баланс: {self.config.min_balance:.6f} SOL")
        print(f"⛽ Резерв газа: {self.config.gas_reserve:.6f} SOL на кошелек")
        print()

        # Рекомендации
        print("💡 РЕКОМЕНДАЦИИ:")

        if failed_wallets > len(self.config.wallets) * 0.1:  # Более 10% ошибок
            print("⚠️ Много ошибок при проверке кошельков!")
            print("   - Проверьте интернет соединение")
            print("   - Попробуйте другой RPC провайдер")
            print("   - Уменьшите количество одновременных запросов")

        if ready_wallets == 0:
            print("❌ НЕТ КОШЕЛЬКОВ ГОТОВЫХ К ТОРГОВЛЕ!")
            print("   - Пополните кошельки с CEX бирж")
            print("   - Минимум на каждый кошелек: 0.05+ SOL")
        elif ready_wallets < successful_wallets // 2:
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
        print()
        print("⚙️ ПРОИЗВОДИТЕЛЬНОСТЬ:")
        print(f"   Размер батча: {self.batch_size}")
        print(f"   Макс. одновременных запросов: {self.max_concurrent_requests}")
        print(f"   Задержка между батчами: {self.batch_delay}s")

    async def quick_balance_check(self):
        """Быстрая проверка только общего баланса"""
        if not self.config.is_enabled():
            print("⚠️ Множественные кошельки отключены")
            return

        logger.info("⚡ Быстрая проверка балансов...")

        # Создаем семафор для ограничения запросов
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        total_balance = 0.0
        ready_count = 0
        checked_count = 0

        # Создаем задачи для всех кошельков с ограничениями
        balance_tasks = []
        for wallet in self.config.wallets:
            task = asyncio.create_task(self._quick_check_wallet(wallet, semaphore))
            balance_tasks.append(task)

        # Выполняем все задачи
        results = await asyncio.gather(*balance_tasks, return_exceptions=True)

        # Обрабатываем результаты
        for wallet, result in zip(self.config.wallets, results):
            if isinstance(result, Exception):
                logger.debug(f"Ошибка проверки кошелька {wallet.index}: {result}")
                continue

            balance, is_ready = result
            total_balance += balance
            checked_count += 1

            if is_ready:
                ready_count += 1

        print(f"💰 Общий баланс: {total_balance:.4f} SOL")
        print(f"✅ Готовых кошельков: {ready_count}/{checked_count}")

        if checked_count < len(self.config.wallets):
            failed = len(self.config.wallets) - checked_count
            print(f"⚠️ Не удалось проверить: {failed} кошельков")

    async def _quick_check_wallet(self, wallet, semaphore) -> Tuple[float, bool]:
        """Быстрая проверка одного кошелька"""
        async with semaphore:
            try:
                response = await self.solana_client.get_balance(wallet.keypair.pubkey())
                balance = response.value / 1e9 if response.value else 0.0
                is_ready = balance >= self.config.min_balance
                return balance, is_ready
            except Exception as e:
                # В быстром режиме просто возвращаем ошибку
                raise Exception(f"Ошибка получения баланса: {e}")


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