#!/usr/bin/env python3
"""
💰 MORI Sniper Bot - Быстрая проверка балансов
Показывает доступные средства для аварийной покупки
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings
from config.multi_wallet import MultiWalletConfig
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed


class BalanceChecker:
    """Быстрая проверка балансов"""

    def __init__(self):
        self.config = MultiWalletConfig()
        self.solana_client = None

    async def start(self):
        """Инициализация подключения"""
        try:
            self.solana_client = AsyncClient(
                endpoint=settings.solana.rpc_url,
                commitment=Confirmed
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к Solana: {e}")
            return False

    async def stop(self):
        """Закрытие подключения"""
        if self.solana_client:
            await self.solana_client.close()

    async def check_balances(self):
        """Проверка всех балансов"""
        print("💰 ПРОВЕРКА БАЛАНСОВ ДЛЯ АВАРИЙНОЙ ПОКУПКИ")
        print("=" * 60)

        if not self.config.is_enabled():
            # Один кошелек
            await self.check_single_wallet()
        else:
            # Множественные кошельки
            await self.check_multiple_wallets()

        self.show_trading_potential()

    async def check_single_wallet(self):
        """Проверка одиночного кошелька"""
        print("📱 РЕЖИМ: Одиночный кошелек")
        print("-" * 30)

        try:
            # Получаем кошелек из Jupiter trader
            from trading.jupiter import jupiter_trader
            if not await jupiter_trader.start():
                raise Exception("Не удалось запустить торговую систему")

            wallet_address = str(jupiter_trader.executor.wallet_keypair.pubkey())
            balance = await jupiter_trader.get_sol_balance()

            print(f"🏦 Адрес: {wallet_address}")
            print(f"💰 Баланс: {balance:.6f} SOL (~${balance * 200:.0f})")

            # Доступно для торговли (с учетом газа)
            gas_reserve = 0.01  # Резерв на газ
            available = max(0, balance - gas_reserve)
            print(f"✅ Доступно: {available:.6f} SOL")

            if available < settings.trading.trade_amount_sol:
                print(f"⚠️ Недостаточно для покупки {settings.trading.trade_amount_sol} SOL")
            else:
                max_trades = int(available / settings.trading.trade_amount_sol)
                print(f"🎯 Макс. сделок: {max_trades} x {settings.trading.trade_amount_sol} SOL")

            await jupiter_trader.stop()

        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")

    async def check_multiple_wallets(self):
        """Проверка множественных кошельков"""
        print(f"🎭 РЕЖИМ: Множественные кошельки ({len(self.config.wallets)})")
        print("-" * 30)

        if not self.config.wallets:
            print("❌ Кошельки не загружены")
            return

        # Получаем балансы параллельно
        balance_tasks = []
        for wallet in self.config.wallets:
            task = asyncio.create_task(self._get_wallet_balance(wallet))
            balance_tasks.append(task)

        results = await asyncio.gather(*balance_tasks, return_exceptions=True)

        # Обрабатываем результаты
        total_balance = 0.0
        total_available = 0.0
        ready_wallets = 0

        print("📊 ДЕТАЛИ ПО КОШЕЛЬКАМ:")
        for wallet, result in zip(self.config.wallets, results):
            if isinstance(result, Exception):
                status = "❌ Ошибка"
                balance = 0.0
            else:
                balance = result
                wallet.update_balance(balance)
                total_balance += balance
                total_available += wallet.available_balance

                if wallet.available_balance >= self.config.min_balance:
                    ready_wallets += 1
                    status = "✅ Готов"
                else:
                    status = "🔴 Мало"

            short_addr = f"{wallet.address[:8]}...{wallet.address[-8:]}"
            print(f"  {status} {short_addr}: {balance:.6f} SOL (доступно: {wallet.available_balance:.6f})")

        print("\n📈 ИТОГО:")
        print(f"💰 Общий баланс: {total_balance:.6f} SOL (~${total_balance * 200:.0f})")
        print(f"💎 Доступно для торговли: {total_available:.6f} SOL")
        print(f"✅ Готовых кошельков: {ready_wallets}/{len(self.config.wallets)}")

        if self.config.use_max_available_balance:
            print(f"🔥 РЕЖИМ: Потратим весь доступный баланс ({total_available:.6f} SOL)")
        else:
            trade_amount = settings.trading.trade_amount_sol
            num_trades = settings.trading.num_purchases
            max_possible = int(total_available / trade_amount)
            planned = ready_wallets * num_trades

            print(f"📊 Запланировано: {planned} x {trade_amount} SOL = {planned * trade_amount:.4f} SOL")
            print(f"🎯 Максимум возможно: {max_possible} x {trade_amount} SOL")

    async def _get_wallet_balance(self, wallet) -> float:
        """Получение баланса кошелька"""
        try:
            response = await self.solana_client.get_balance(wallet.keypair.pubkey())
            return response.value / 1e9 if response.value else 0.0
        except Exception as e:
            logger.debug(f"Ошибка баланса {wallet.address[:8]}...: {e}")
            return 0.0

    def show_trading_potential(self):
        """Показать торговый потенциал"""
        print("\n🎯 АВАРИЙНАЯ ПОКУПКА:")
        print("-" * 25)
        print("⚡ Команды для быстрой покупки:")
        print("   python emergency_buy.py    # Интерактивный режим")
        print("   python quick_buy.py CONTRACT  # Командная строка")
        print()
        print("📋 Пример:")
        print("   python quick_buy.py JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN")
        print()

    async def quick_check(self):
        """Быстрая проверка только итогов"""
        print("⚡ БЫСТРАЯ ПРОВЕРКА БАЛАНСОВ")
        print("=" * 40)

        try:
            if not self.config.is_enabled():
                # Один кошелек
                from trading.jupiter import jupiter_trader
                await jupiter_trader.start()
                balance = await jupiter_trader.get_sol_balance()
                await jupiter_trader.stop()

                print(f"📱 Баланс: {balance:.4f} SOL (~${balance * 200:.0f})")

                if balance >= settings.trading.trade_amount_sol:
                    print("✅ Готов к покупке")
                else:
                    print("❌ Недостаточно средств")
            else:
                # Множественные кошельки - быстрая проверка
                total_balance = 0.0
                ready_count = 0

                balance_tasks = []
                for wallet in self.config.wallets:
                    task = asyncio.create_task(self._get_wallet_balance(wallet))
                    balance_tasks.append(task)

                results = await asyncio.gather(*balance_tasks, return_exceptions=True)

                for wallet, result in zip(self.config.wallets, results):
                    if not isinstance(result, Exception):
                        balance = result
                        wallet.update_balance(balance)
                        total_balance += balance
                        if wallet.available_balance >= self.config.min_balance:
                            ready_count += 1

                print(f"🎭 Кошельков: {ready_count}/{len(self.config.wallets)} готовы")
                print(f"💰 Общий баланс: {total_balance:.4f} SOL")

                if self.config.use_max_available_balance:
                    total_available = sum(w.available_balance for w in self.config.wallets)
                    print(f"🔥 Потратим: {total_available:.4f} SOL (весь баланс)")

                if ready_count > 0:
                    print("✅ Готов к аварийной покупке")
                else:
                    print("❌ Нет готовых кошельков")

        except Exception as e:
            print(f"❌ Ошибка: {e}")


async def main():
    """Главная функция"""
    checker = BalanceChecker()

    # Проверяем аргументы командной строки
    quick_mode = len(sys.argv) > 1 and sys.argv[1] in ['--quick', '-q']

    try:
        if not await checker.start():
            sys.exit(1)

        if quick_mode:
            await checker.quick_check()
        else:
            await checker.check_balances()

    except KeyboardInterrupt:
        print("\n❌ Прервано пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await checker.stop()


if __name__ == "__main__":
    asyncio.run(main())