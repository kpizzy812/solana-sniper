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
        print(f"  ⛽ Резерв на газ: 0.015 SOL (добавлен автоматически)")

        if self.multi_wallet_config.is_enabled():
            wallet_count = len(self.multi_wallet_config.wallets)
            print(f"  🎭 Режим: Множественные кошельки ({wallet_count} шт)")

            if self.multi_wallet_config.use_max_available_balance:
                print(f"  💸 Стратегия: Весь доступный баланс с каждого кошелька (минус резерв)")
            else:
                total_per_wallet = settings.trading.trade_amount_sol * settings.trading.num_purchases
                gas_per_wallet = 0.015  # Увеличенный резерв
                total_needed_per_wallet = total_per_wallet + gas_per_wallet
                total_overall = total_needed_per_wallet * wallet_count
                print(
                    f"  💸 Стратегия: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases} с каждого кошелька")
                print(f"  📈 Нужно SOL на кошелек: {total_needed_per_wallet:.6f} SOL (включая газ)")
                print(f"  📊 Общий объем: {total_overall:.6f} SOL")
        else:
            total_investment = settings.trading.trade_amount_sol * settings.trading.num_purchases
            gas_reserve = 0.015
            total_needed = total_investment + gas_reserve
            print(f"  📱 Режим: Одиночный кошелек")
            print(
                f"  💸 Сумма покупки: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases} = {total_investment} SOL")
            print(f"  📊 Всего нужно: {total_needed:.6f} SOL (включая газ)")

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

    async def check_wallet_balance_before_trade(self, token_contract: str) -> bool:
        """Проверка баланса кошелька перед торговлей - НОВАЯ ФУНКЦИЯ"""
        try:
            print("\n💰 ПРОВЕРКА БАЛАНСА КОШЕЛЬКОВ...")
            print("=" * 50)

            if (hasattr(jupiter_trader, 'multi_wallet_manager') and
                    jupiter_trader.multi_wallet_manager and
                    self.multi_wallet_config.is_enabled()):

                # Проверка множественных кошельков
                print("🎭 Проверка множественных кошельков:")

                wallets_with_funds = 0
                total_available_sol = 0.0
                gas_reserve_per_wallet = 0.015  # Резерв на газ

                for i, wallet in enumerate(self.multi_wallet_config.wallets):
                    try:
                        # Получаем баланс
                        balance_response = await jupiter_trader.solana_client.get_balance(wallet.keypair.pubkey())
                        sol_balance = balance_response.value / 1e9

                        # Вычисляем доступную сумму (баланс - резерв на газ)
                        available_balance = max(0, sol_balance - gas_reserve_per_wallet)

                        wallet_addr = str(wallet.keypair.pubkey())
                        short_addr = f"{wallet_addr[:8]}...{wallet_addr[-8:]}"

                        if available_balance > 0.001:  # Минимум 0.001 SOL для торговли
                            print(f"  ✅ {short_addr}: {sol_balance:.6f} SOL (доступно: {available_balance:.6f})")
                            wallets_with_funds += 1
                            total_available_sol += available_balance
                        else:
                            print(f"  ❌ {short_addr}: {sol_balance:.6f} SOL (недостаточно средств)")

                    except Exception as e:
                        print(f"  ❌ {short_addr}: Ошибка проверки баланса - {e}")

                print(f"\n📊 Итого:")
                print(f"  💰 Кошельков с средствами: {wallets_with_funds}/{len(self.multi_wallet_config.wallets)}")
                print(f"  🪙 Общий доступный баланс: {total_available_sol:.6f} SOL")

                if wallets_with_funds == 0:
                    print("❌ НЕТ КОШЕЛЬКОВ С ДОСТАТОЧНЫМИ СРЕДСТВАМИ!")
                    return False

            else:
                # Проверка одиночного кошелька
                print("📱 Проверка основного кошелька:")

                try:
                    main_wallet = jupiter_trader.executor.wallet_keypair
                    balance_response = await jupiter_trader.solana_client.get_balance(main_wallet.pubkey())
                    sol_balance = balance_response.value / 1e9

                    # Рассчитываем сколько SOL нужно
                    required_sol = settings.trading.trade_amount_sol * settings.trading.num_purchases
                    gas_reserve = 0.015  # Резерв на газ
                    total_required = required_sol + gas_reserve

                    wallet_addr = str(main_wallet.pubkey())
                    short_addr = f"{wallet_addr[:8]}...{wallet_addr[-8:]}"

                    print(f"  🏦 Кошелек: {short_addr}")
                    print(f"  💰 Текущий баланс: {sol_balance:.6f} SOL")
                    print(f"  🎯 Требуется для торговли: {required_sol:.6f} SOL")
                    print(f"  ⛽ Резерв на газ: {gas_reserve:.6f} SOL")
                    print(f"  📊 Всего требуется: {total_required:.6f} SOL")

                    if sol_balance < total_required:
                        print(f"  ❌ НЕДОСТАТОЧНО СРЕДСТВ! Не хватает: {total_required - sol_balance:.6f} SOL")
                        return False
                    else:
                        print(f"  ✅ Средств достаточно! Остаток после торговли: {sol_balance - total_required:.6f} SOL")

                except Exception as e:
                    print(f"  ❌ Ошибка проверки баланса: {e}")
                    return False

            print("\n✅ Проверка баланса завершена успешно")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки баланса: {e}")
            print(f"❌ Ошибка проверки баланса: {e}")
            return False

    async def execute_emergency_buy(self, token_contract: str):
        """Выполнение аварийной покупки с проверкой баланса - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        print(f"\n🎯 НАЧИНАЕМ ПОКУПКУ: {token_contract}")
        print("=" * 60)

        # Инициализируем Jupiter
        await jupiter_trader.start()

        try:
            # НОВОЕ: Проверяем баланс ПЕРЕД торговлей
            if not await self.check_wallet_balance_before_trade(token_contract):
                print("\n❌ ПОКУПКА ОТМЕНЕНА: Недостаточно средств!")
                print("💡 Пополните кошелек(и) и попробуйте снова")
                return

            start_time = time.time()

            # Создаем сигнал для торговли
            trading_signal = {
                'platform': 'emergency',
                'source': 'manual_input',
                'timestamp': time.time(),
                'content_preview': f"Аварийная покупка {token_contract}",
                'emergency': True
            }

            # Выполняем покупку
            if (hasattr(jupiter_trader, 'multi_wallet_manager') and
                    jupiter_trader.multi_wallet_manager and
                    self.multi_wallet_config.is_enabled()):

                print("\n🎭 Режим: Множественные кошельки")

                if self.multi_wallet_config.use_max_available_balance:
                    print("💰 Стратегия: Весь доступный баланс (с резервом на газ)")
                    result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                        token_address=token_contract,
                        base_trade_amount=0,
                        num_trades=0,
                        source_info=trading_signal
                    )
                else:
                    print(f"💰 Стратегия: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases}")
                    result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                        token_address=token_contract,
                        base_trade_amount=settings.trading.trade_amount_sol,
                        num_trades=settings.trading.num_purchases,
                        source_info=trading_signal
                    )

                # Результаты множественных кошельков
                print(f"\n🎉 ПОКУПКА ЗАВЕРШЕНА!")
                print("=" * 60)
                print(f"✅ Успешных сделок: {result.successful_trades}/{result.total_trades}")
                print(f"💰 Потрачено SOL: {result.total_sol_spent:.6f}")
                print(f"🪙 Куплено токенов: {result.total_tokens_bought:,.6f}")
                print(f"⏱️ Общее время: {(time.time() - start_time):.1f}s")
                print(f"📊 Скорость: {result.execution_time_ms:.0f}ms")

                # Показываем результаты по кошелькам
                print(f"\n📋 ДЕТАЛИ ПО КОШЕЛЬКАМ:")
                print("-" * 60)

                successful_wallets = 0
                for wallet_addr, trade_result in result.wallet_results:
                    status = "✅" if trade_result.success else "❌"
                    short_addr = f"{wallet_addr[:8]}...{wallet_addr[-8:]}"
                    print(f"{status} {short_addr}")

                    if trade_result.success:
                        successful_wallets += 1
                        print(f"   💰 Потрачено: {trade_result.input_amount:.6f} SOL")
                        if trade_result.output_amount:
                            print(f"   🪙 Получено: {trade_result.output_amount:,.6f} токенов")
                        if trade_result.signature:
                            print(f"   📝 Подпись: {trade_result.signature}")
                    else:
                        print(f"   ❌ Ошибка: {trade_result.error}")
                    print()

            else:
                print("\n📱 Режим: Одиночный кошелек")

                results = await jupiter_trader.execute_sniper_trades(
                    token_address=token_contract,
                    source_info=trading_signal
                )

                successful = [r for r in results if r.success]

                print(f"\n🎉 ПОКУПКА ЗАВЕРШЕНА!")
                print("=" * 60)
                print(f"✅ Успешных сделок: {len(successful)}/{len(results)}")

                if successful:
                    total_sol = sum(r.input_amount for r in successful)
                    total_tokens = sum(r.output_amount or 0 for r in successful)
                    print(f"💰 Потрачено SOL: {total_sol:.6f}")
                    print(f"🪙 Куплено токенов: {total_tokens:,.6f}")
                    print(f"⏱️ Общее время: {(time.time() - start_time):.1f}s")

                    print(f"\n📋 ДЕТАЛИ СДЕЛОК:")
                    print("-" * 60)

                    for i, result in enumerate(successful):
                        print(f"✅ Сделка {i + 1}:")
                        print(f"   💰 Потрачено: {result.input_amount:.6f} SOL")
                        if result.output_amount:
                            print(f"   🪙 Получено: {result.output_amount:,.6f} токенов")
                        if result.signature:
                            print(f"   📝 Подпись: {result.signature}")
                        print()

        finally:
            await jupiter_trader.stop()

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