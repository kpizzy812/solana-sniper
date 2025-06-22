#!/usr/bin/env python3
"""
🚨 MORI Sniper Bot - Аварийный скрипт покупки
Экстренная покупка токена без мониторинга - ввел контракт и купил
"""

import asyncio
import sys
import time
import re
from pathlib import Path
from typing import Optional, List

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings
from config.multi_wallet import MultiWalletConfig
from trading.jupiter import jupiter_trader
from utils.addresses import is_valid_solana_address, is_wrapped_sol


class EmergencyBuyer:
    """Аварийная система покупки токенов"""

    def __init__(self):
        self.multi_wallet_config = MultiWalletConfig()
        self.start_time = None

    def print_header(self):
        """Печать заголовка"""
        print("🚨 MORI SNIPER - АВАРИЙНАЯ ПОКУПКА")
        print("=" * 60)
        print("⚡ Экстренная покупка токена без мониторинга")
        print("🎯 Ввести контракт → мгновенная покупка")
        print("=" * 60)
        print()

    def show_current_settings(self):
        """Показать текущие настройки"""
        print("⚙️ ТЕКУЩИЕ НАСТРОЙКИ:")
        print("-" * 30)

        # Основные настройки торговли
        if self.multi_wallet_config.is_enabled():
            if self.multi_wallet_config.use_max_available_balance:
                print("💰 Режим: ТРАТИМ ВЕСЬ ДОСТУПНЫЙ БАЛАНС с множественных кошельков")
                print(f"🎭 Кошельков загружено: {len(self.multi_wallet_config.wallets)}")
                print(f"📊 Стратегия: {self.multi_wallet_config.distribution_strategy}")
                print(f"⏱️ Задержка перед торговлей: {self.multi_wallet_config.initial_delay_seconds}s")
            else:
                print("💰 Режим: Фиксированные суммы с множественных кошельков")
                print(f"🎭 Кошельков: {len(self.multi_wallet_config.wallets)}")
                print(f"💵 Сумма на кошелек: {settings.trading.trade_amount_sol} SOL")
                print(f"🔢 Сделок на кошелек: {settings.trading.num_purchases}")
        else:
            print("💰 Режим: Обычный одиночный кошелек")
            print(f"💵 Размер сделки: {settings.trading.trade_amount_sol} SOL")
            print(f"🔢 Количество покупок: {settings.trading.num_purchases}")

        print(f"📊 Проскальзывание: {settings.trading.slippage_bps / 100}%")
        print(f"⚡ Приоритет комиссии: {settings.trading.priority_fee:,} microlamports")
        print(f"🌐 Сеть: {settings.solana.network}")
        print(f"🛡️ Проверки безопасности: {'Включены' if settings.security.enable_security_checks else 'Отключены'}")
        print()

    def get_token_input(self) -> Optional[str]:
        """Получение адреса токена от пользователя"""
        print("🎯 ВВОД ТОКЕНА ДЛЯ ПОКУПКИ:")
        print("-" * 30)
        print("💡 Поддерживаемые форматы:")
        print("   • Прямой контракт: JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN")
        print("   • Jupiter ссылка: https://jup.ag/swap/SOL-CONTRACT")
        print("   • Dexscreener: https://dexscreener.com/solana/CONTRACT")
        print("   • Любой URL с контрактом")
        print()

        while True:
            user_input = input("🔗 Введите контракт токена или URL: ").strip()

            if not user_input:
                print("❌ Ввод не может быть пустым")
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("❌ Операция отменена")
                return None

            # Извлекаем контракт из ввода
            contract = self.extract_contract_from_input(user_input)

            if contract:
                # Проверяем что это не базовый токен
                if is_wrapped_sol(contract):
                    print("❌ Это Wrapped SOL - покупка не нужна")
                    continue

                print(f"✅ Контракт найден: {contract}")

                # Подтверждение
                confirm = input("\n🚨 ПОДТВЕРДИТЬ ПОКУПКУ? [y/N]: ").strip().lower()
                if confirm in ['y', 'yes', 'да', 'д']:
                    return contract
                else:
                    print("❌ Покупка отменена")
                    return None
            else:
                print("❌ Не удалось найти валидный контракт токена")
                print("💡 Проверьте формат ввода и попробуйте снова")
                continue

    def extract_contract_from_input(self, user_input: str) -> Optional[str]:
        """Извлечение контракта из пользовательского ввода"""
        try:
            # Если это уже готовый контракт
            if is_valid_solana_address(user_input):
                return user_input

            # Если это URL - используем наши парсеры
            if 'http' in user_input.lower():
                from utils.addresses import extract_addresses_from_any_url
                addresses = extract_addresses_from_any_url(user_input)
                if addresses:
                    return addresses[0]  # Берем первый найденный

            # Поиск контракта в произвольном тексте
            from utils.addresses import extract_addresses_fast
            addresses = extract_addresses_fast(user_input, settings.ai)
            if addresses:
                return addresses[0]  # Берем первый найденный

            return None

        except Exception as e:
            logger.error(f"Ошибка извлечения контракта: {e}")
            return None

    async def execute_emergency_buy(self, token_contract: str):
        """Выполнение аварийной покупки"""
        self.start_time = time.time()

        logger.critical("🚨 НАЧАЛАСЬ АВАРИЙНАЯ ПОКУПКА!")
        logger.critical(f"🎯 Контракт: {token_contract}")

        try:
            # Инициализируем Jupiter trader
            logger.info("🚀 Инициализация торговой системы...")
            if not await jupiter_trader.start():
                raise Exception("Не удалось запустить торговую систему")

            # Проверяем здоровье системы
            health = await jupiter_trader.health_check()
            if health.get('status') != 'healthy':
                logger.warning(f"⚠️ Проблемы с торговой системой: {health}")

            # Создаем данные для торговли (имитируем сигнал)
            trading_signal = {
                'platform': 'emergency_manual',
                'source': 'Аварийная покупка',
                'author': 'Manual Input',
                'url': 'manual://emergency',
                'contracts': [token_contract],
                'confidence': 1.0,  # Максимальная уверенность для ручного ввода
                'urgency': 'high',
                'timestamp': time.time(),
                'content_preview': f"Аварийная покупка токена {token_contract}",
                'emergency': True
            }

            # Выполняем покупку
            if (hasattr(jupiter_trader, 'multi_wallet_manager') and
                    jupiter_trader.multi_wallet_manager and
                    self.multi_wallet_config.is_enabled()):

                # Множественные кошельки
                await self.execute_multi_wallet_buy(token_contract, trading_signal)
            else:
                # Обычная покупка
                await self.execute_single_wallet_buy(token_contract, trading_signal)

        except Exception as e:
            logger.error(f"❌ Критическая ошибка аварийной покупки: {e}")
            print(f"\n❌ ОШИБКА: {e}")
        finally:
            # Останавливаем Jupiter trader
            await jupiter_trader.stop()

    async def execute_multi_wallet_buy(self, token_contract: str, trading_signal: dict):
        """Покупка с множественными кошельками"""
        logger.critical("🎭 ПОКУПКА С МНОЖЕСТВЕННЫМИ КОШЕЛЬКАМИ")

        if self.multi_wallet_config.use_max_available_balance:
            # Тратим весь доступный баланс
            result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                token_address=token_contract,
                base_trade_amount=0,  # Игнорируется в режиме max balance
                num_trades=0,  # Игнорируется в режиме max balance
                source_info=trading_signal
            )
        else:
            # Фиксированные суммы
            result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                token_address=token_contract,
                base_trade_amount=settings.trading.trade_amount_sol,
                num_trades=settings.trading.num_purchases,
                source_info=trading_signal
            )

        # Показываем результаты
        self.show_multi_wallet_results(result)

    async def execute_single_wallet_buy(self, token_contract: str, trading_signal: dict):
        """Покупка с одиночным кошельком"""
        logger.critical("📱 ПОКУПКА С ОДИНОЧНЫМ КОШЕЛЬКОМ")

        results = await jupiter_trader.execute_sniper_trades(
            token_address=token_contract,
            source_info=trading_signal
        )

        # Показываем результаты
        self.show_single_wallet_results(results)

    def show_multi_wallet_results(self, result):
        """Показ результатов множественных кошельков"""
        execution_time = (time.time() - self.start_time)

        print("\n" + "=" * 60)
        print("🎭 РЕЗУЛЬТАТЫ МУЛЬТИ-КОШЕЛЬКОВОЙ ПОКУПКИ")
        print("=" * 60)

        print(f"⏱️ Время выполнения: {execution_time:.1f} секунд")
        print(f"🎯 Всего сделок: {result.total_trades}")
        print(f"✅ Успешных: {result.successful_trades}")
        print(f"❌ Неудачных: {result.failed_trades}")
        print(f"📈 Процент успеха: {result.success_rate:.1f}%")
        print(f"💰 Потрачено SOL: {result.total_sol_spent:.6f}")
        print(f"🪙 Куплено токенов: {result.total_tokens_bought:,.0f}")

        if result.delayed_start:
            print(f"⏱️ Была задержка: {self.multi_wallet_config.initial_delay_seconds}s")

        # Показываем детали по кошелькам
        if result.wallet_results:
            print(f"\n📊 ДЕТАЛИ ПО КОШЕЛЬКАМ:")
            unique_wallets = {}
            for wallet_addr, trade_result in result.wallet_results:
                short_addr = f"{wallet_addr[:8]}...{wallet_addr[-8:]}"
                if wallet_addr not in unique_wallets:
                    unique_wallets[wallet_addr] = {
                        'successful': 0,
                        'failed': 0,
                        'sol_spent': 0.0,
                        'tokens_bought': 0.0
                    }

                wallet_stats = unique_wallets[wallet_addr]
                if trade_result.success:
                    wallet_stats['successful'] += 1
                    wallet_stats['sol_spent'] += trade_result.input_amount
                    wallet_stats['tokens_bought'] += trade_result.output_amount or 0
                else:
                    wallet_stats['failed'] += 1

            for wallet_addr, stats in unique_wallets.items():
                short_addr = f"{wallet_addr[:8]}...{wallet_addr[-8:]}"
                print(
                    f"  🎭 {short_addr}: {stats['successful']}/{stats['successful'] + stats['failed']} успешно, {stats['sol_spent']:.4f} SOL")

        # Подписи транзакций
        signatures = [r.signature for _, r in result.wallet_results if r.success and r.signature]
        if signatures:
            print(f"\n📝 ПОДПИСИ УСПЕШНЫХ ТРАНЗАКЦИЙ:")
            for i, sig in enumerate(signatures):
                print(f"  {i + 1}. {sig}")

    def show_single_wallet_results(self, results: List):
        """Показ результатов одиночного кошелька"""
        execution_time = (time.time() - self.start_time)
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        print("\n" + "=" * 60)
        print("📱 РЕЗУЛЬТАТЫ ПОКУПКИ")
        print("=" * 60)

        print(f"⏱️ Время выполнения: {execution_time:.1f} секунд")
        print(f"🎯 Всего сделок: {len(results)}")
        print(f"✅ Успешных: {len(successful)}")
        print(f"❌ Неудачных: {len(failed)}")
        print(f"📈 Процент успеха: {len(successful) / max(len(results), 1) * 100:.1f}%")

        if successful:
            total_sol = sum(r.input_amount for r in successful)
            total_tokens = sum(r.output_amount or 0 for r in successful)
            avg_time = sum(r.execution_time_ms for r in successful) / len(successful)

            print(f"💰 Потрачено SOL: {total_sol:.6f}")
            print(f"🪙 Куплено токенов: {total_tokens:,.0f}")
            print(f"⚡ Среднее время: {avg_time:.0f}ms")

            # Подписи транзакций
            print(f"\n📝 ПОДПИСИ УСПЕШНЫХ ТРАНЗАКЦИЙ:")
            for i, result in enumerate(successful):
                if result.signature:
                    print(f"  {i + 1}. {result.signature}")

        # Ошибки
        if failed:
            print(f"\n❌ ОШИБКИ:")
            for i, result in enumerate(failed):
                print(f"  {i + 1}. {result.error}")

    async def run_emergency_mode(self):
        """Запуск аварийного режима"""
        try:
            self.print_header()
            self.show_current_settings()

            # Получаем контракт от пользователя
            token_contract = self.get_token_input()
            if not token_contract:
                return

            print(f"\n🚨 НАЧИНАЕМ АВАРИЙНУЮ ПОКУПКУ: {token_contract}")
            print("=" * 60)

            # Выполняем покупку
            await self.execute_emergency_buy(token_contract)

            print("\n🎉 АВАРИЙНАЯ ПОКУПКА ЗАВЕРШЕНА!")

        except KeyboardInterrupt:
            print("\n❌ Операция прервана пользователем")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")

    def show_quick_help(self):
        """Показать быструю справку"""
        print("💡 БЫСТРАЯ СПРАВКА:")
        print("-" * 20)
        print("🎯 Этот скрипт для экстренной покупки без мониторинга")
        print("⚡ Просто введите контракт токена и он купит по настройкам")
        print("🎭 Поддерживает как один кошелек, так и множественные")
        print("🛡️ Все проверки безопасности работают как в основном боте")
        print()


async def main():
    """Главная функция"""
    buyer = EmergencyBuyer()
    buyer.show_quick_help()
    await buyer.run_emergency_mode()


if __name__ == "__main__":
    # Запуск аварийного режима
    asyncio.run(main())