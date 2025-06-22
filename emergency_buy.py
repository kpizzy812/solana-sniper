#!/usr/bin/env python3
"""
🚨 MORI Sniper Bot - Аварийная покупка с интерактивным интерфейсом
Система экстренной покупки токенов вручную
"""

import asyncio
import sys
import time
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings
from config.multi_wallet import MultiWalletConfig
from trading.jupiter import jupiter_trader
from utils.addresses import is_valid_solana_address, is_wrapped_sol, extract_addresses_fast


class EmergencyBuyer:
    """Аварийная покупка токенов с интерактивным интерфейсом"""

    def __init__(self):
        self.multi_wallet_config = MultiWalletConfig()
        self.start_time = 0.0

    def print_header(self):
        """Показать заголовок"""
        print("\n🚨 АВАРИЙНАЯ ПОКУПКА ТОКЕНОВ")
        print("=" * 60)
        print("⚡ Система быстрой покупки для критических ситуаций")
        print("🎯 Поддержка множественных кошельков и форматов ввода")
        print("🛡️ Все настройки безопасности активны")
        print("=" * 60)

    def show_current_settings(self):
        """Показать текущие настройки"""
        print("⚙️ ТЕКУЩИЕ НАСТРОЙКИ:")
        print(f"  📊 Проскальзывание: {settings.trading.slippage_bps / 100}%")
        print(f"  💰 Приоритетная комиссия: {settings.trading.priority_fee:,} microlamports")

        if self.multi_wallet_config.is_enabled():
            wallet_count = len(self.multi_wallet_config.wallets)
            print(f"  🎭 Режим: Множественные кошельки ({wallet_count} шт)")

            if self.multi_wallet_config.use_max_available_balance:
                print(f"  💸 Стратегия: Весь доступный баланс с каждого кошелька")
            else:
                total_per_wallet = settings.trading.trade_amount_sol * settings.trading.num_purchases
                total_overall = total_per_wallet * wallet_count
                print(
                    f"  💸 Стратегия: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases} с каждого кошелька")
                print(f"  📈 Общий объем: {total_overall} SOL")
        else:
            total_investment = settings.trading.trade_amount_sol * settings.trading.num_purchases
            print(f"  📱 Режим: Одиночный кошелек")
            print(
                f"  💸 Сумма покупки: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases} = {total_investment} SOL")

        print()

    def get_token_input(self) -> str:
        """Получить контракт токена от пользователя"""
        try:
            print("🎯 ВВОД КОНТРАКТА ТОКЕНА:")
            print("   Поддерживаемые форматы:")
            print("   • Прямой контракт: JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN")
            print("   • Jupiter ссылка: jup.ag/swap/SOL-CONTRACT")
            print("   • DEX ссылка: dexscreener.com/solana/CONTRACT")
            print("   • Произвольный текст с контрактом")
            print()

            user_input = input("📝 Введите контракт или ссылку: ").strip()

            if not user_input:
                print("❌ Пустой ввод")
                return ""

            # Извлечение контракта
            token_contract = self.extract_contract_from_input(user_input)

            # Проверка на Wrapped SOL
            if is_wrapped_sol(token_contract):
                print("⚠️ Это Wrapped SOL - покупка не требуется")
                return ""

            # Подтверждение
            print(f"\n✅ Найден контракт: {token_contract}")
            confirm = input("❓ Подтвердить покупку? [y/N]: ").lower()

            if confirm not in ['y', 'yes', 'да', '1']:
                print("❌ Покупка отменена")
                return ""

            return token_contract

        except Exception as e:
            logger.error(f"❌ Ошибка получения ввода: {e}")
            print(f"❌ Ошибка: {e}")
            return ""

    def extract_contract_from_input(self, user_input: str) -> str:
        """Извлечение контракта из пользовательского ввода"""
        try:
            # Прямой контракт
            if is_valid_solana_address(user_input):
                return user_input

            # URL или ссылка
            if 'http' in user_input.lower() or any(domain in user_input.lower() for domain in
                                                   ['jup.ag', 'dexscreener', 'raydium', 'birdeye']):
                from utils.addresses import extract_addresses_from_any_url
                addresses = extract_addresses_from_any_url(user_input)
                if addresses:
                    return addresses[0]

            # Поиск в произвольном тексте
            addresses = extract_addresses_fast(user_input, settings.ai)
            if addresses:
                return addresses[0]

            raise ValueError("Контракт не найден в введенном тексте")

        except Exception as e:
            raise ValueError(f"Не удалось извлечь контракт: {e}")

    async def start_trading_system_with_retries(self, max_retries: int = 3) -> bool:
        """Запуск торговой системы с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Попытка запуска торговой системы {attempt + 1}/{max_retries}...")

                if await jupiter_trader.start():
                    logger.success("✅ Торговая система запущена успешно")
                    return True
                else:
                    logger.warning(f"⚠️ Попытка {attempt + 1} не удалась")

            except Exception as e:
                logger.error(f"❌ Ошибка при попытке {attempt + 1}: {e}")

            # Ждем перед следующей попыткой (кроме последней)
            if attempt < max_retries - 1:
                retry_delay = 2 * (attempt + 1)  # Экспоненциальная задержка
                logger.info(f"⏳ Ожидание {retry_delay} секунд перед следующей попыткой...")
                await asyncio.sleep(retry_delay)

        logger.error(f"❌ Не удалось запустить торговую систему после {max_retries} попыток")
        return False

    async def check_trading_system_health(self) -> bool:
        """Проверка здоровья торговой системы с более мягкими требованиями"""
        try:
            health = await jupiter_trader.health_check()
            logger.info(f"🔍 Health check результат: {health}")

            # Более мягкие условия - принимаем "degraded" если основные компоненты работают
            status = health.get('status', 'unknown')
            components = health.get('components', {})

            # Проверяем критически важные компоненты
            solana_rpc = components.get('solana_rpc', 'unknown')
            wallet_info = health.get('wallet_info', {})

            if solana_rpc == 'healthy' and wallet_info.get('address'):
                logger.success("✅ Основные компоненты торговой системы работают")

                # Предупреждаем о проблемах с Jupiter API, но не блокируем
                jupiter_api = components.get('jupiter_api', 'unknown')
                if jupiter_api == 'error':
                    logger.warning("⚠️ Проблемы с Jupiter API, но будем пробовать торговать")

                return True
            else:
                logger.error(
                    f"❌ Критические компоненты не работают: Solana RPC={solana_rpc}, Wallet={bool(wallet_info.get('address'))}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка проверки здоровья: {e}")
            # В аварийном режиме пробуем продолжить даже при ошибках health check
            logger.warning("⚠️ Пропускаем health check и пробуем торговать напрямую")
            return True

    async def execute_emergency_buy(self, token_contract: str):
        """Выполнение аварийной покупки с улучшенной обработкой ошибок"""
        self.start_time = time.time()

        logger.critical(f"🎯 Контракт: {token_contract}")

        try:
            # Инициализируем Jupiter trader с ретраями
            logger.info("🚀 Инициализация торговой системы...")
            if not await self.start_trading_system_with_retries():
                raise Exception("Не удалось запустить торговую систему после всех попыток")

            # Проверяем здоровье системы (мягкая проверка)
            if not await self.check_trading_system_health():
                logger.warning("⚠️ Проблемы с торговой системой, но продолжаем аварийную покупку")

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
            try:
                await jupiter_trader.stop()
            except Exception as e:
                logger.error(f"❌ Ошибка остановки трейдера: {e}")

    async def execute_multi_wallet_buy(self, token_contract: str, trading_signal: dict):
        """Покупка через множественные кошельки"""
        logger.info("🎭 Покупка через множественные кошельки...")

        try:
            # Правильный вызов с учетом режима работы
            if self.multi_wallet_config.use_max_available_balance:
                # Режим "весь доступный баланс"
                logger.critical("💰 РЕЖИМ: Трата всего доступного баланса с каждого кошелька")
                result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                    token_address=token_contract,
                    base_trade_amount=0,  # Игнорируется в режиме max balance
                    num_trades=0,  # Игнорируется в режиме max balance
                    source_info=trading_signal
                )
            else:
                # Режим фиксированных сумм
                logger.critical(f"💰 РЕЖИМ: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases}")
                result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                    token_address=token_contract,
                    base_trade_amount=settings.trading.trade_amount_sol,
                    num_trades=settings.trading.num_purchases,
                    source_info=trading_signal
                )

            self.show_multi_wallet_results(result)

        except Exception as e:
            logger.error(f"❌ Ошибка покупки через множественные кошельки: {e}")
            print(f"❌ Ошибка множественных кошельков: {e}")

    async def execute_single_wallet_buy(self, token_contract: str, trading_signal: dict):
        """Покупка через одиночный кошелек"""
        logger.info("📱 Покупка через одиночный кошелек...")

        try:
            results = await jupiter_trader.execute_sniper_trades(
                token_address=token_contract,
                source_info=trading_signal
            )

            self.show_single_wallet_results(results)

        except Exception as e:
            logger.error(f"❌ Ошибка покупки через одиночный кошелек: {e}")
            print(f"❌ Ошибка одиночного кошелька: {e}")

    def show_multi_wallet_results(self, result):
        """Показ результатов множественных кошельков"""
        execution_time = (time.time() - self.start_time)

        print("\n" + "=" * 60)
        print("🎭 РЕЗУЛЬТАТЫ МНОЖЕСТВЕННЫХ КОШЕЛЬКОВ")
        print("=" * 60)

        print(f"⏱️ Время выполнения: {execution_time:.1f} секунд")
        print(f"🎯 Всего сделок: {result.total_trades}")
        print(f"✅ Успешных: {result.successful_trades}")
        print(f"❌ Неудачных: {result.failed_trades}")
        print(f"📈 Процент успеха: {result.success_rate:.1f}%")

        if result.successful_trades > 0:
            print(f"💰 Потрачено SOL: {result.total_sol_spent:.6f}")
            print(f"🪙 Куплено токенов: {result.total_tokens_bought:,.0f}")
            avg_time = result.execution_time_ms / max(result.total_trades, 1)
            print(f"⚡ Среднее время: {avg_time:.0f}ms")

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

    def show_single_wallet_results(self, results: list):
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