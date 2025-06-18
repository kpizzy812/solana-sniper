#!/usr/bin/env python3
"""
🎭 MORI Sniper Bot - Демонстрация системы множественных кошельков
"""

import asyncio
import sys
import random
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.multi_wallet import MultiWalletConfig


class MultiWalletDemo:
    def __init__(self):
        self.config = MultiWalletConfig()

    async def run_demo(self):
        print("🎭 ДЕМОНСТРАЦИЯ СИСТЕМЫ МНОЖЕСТВЕННЫХ КОШЕЛЬКОВ")
        print("=" * 60)
        print()

        if not self.config.is_enabled():
            await self.show_disabled_demo()
            return

        await self.demo_configuration()
        await self.demo_wallet_selection()
        await self.demo_amount_randomization()
        await self.demo_trading_simulation()

        self.show_summary()

    async def show_disabled_demo(self):
        print("⚠️ Система множественных кошельков отключена")
        print()
        print("📋 Что вы увидите после включения:")
        print()

        print("1️⃣ КОНФИГУРАЦИЯ:")
        print("   📊 Кошельков: 8")
        print("   🎲 Стратегия: balanced")
        print("   ⏱️ Задержка: 15 секунд")
        print()

        print("2️⃣ ЗАЩИТА ОТ БЛЭКЛИСТА:")
        print("   ⏱️ Задержка перед торговлей: 15 секунд")
        print("   🎭 Распределение по разным адресам")
        print("   🎲 Случайные суммы и интервалы")
        print()

        print("💡 ДЛЯ ВКЛЮЧЕНИЯ:")
        print("   1. python utils/wallet_generator.py")
        print("   2. Пополните кошельки с разных CEX")
        print("   3. USE_MULTI_WALLET=true в .env")

    async def demo_configuration(self):
        print("1️⃣ КОНФИГУРАЦИЯ СИСТЕМЫ")
        print("-" * 30)

        print(f"📊 Загружено кошельков: {len(self.config.wallets)}")
        print(f"🎲 Стратегия: {self.config.distribution_strategy}")
        print(f"⏱️ Задержка: {self.config.initial_delay_seconds} секунд")
        print(f"💫 Рандомизация: {self.config.randomize_amounts}")
        print()

    async def demo_wallet_selection(self):
        print("2️⃣ ВЫБОР КОШЕЛЬКОВ")
        print("-" * 25)

        for i in range(3):
            test_amount = round(random.uniform(0.08, 0.15), 4)
            wallet = self.config.select_wallet_for_trade(test_amount)

            if wallet:
                print(f"✅ Сделка {i + 1}: {test_amount} SOL через {wallet.address[:8]}...")
            else:
                print(f"❌ Сделка {i + 1}: Нет подходящего кошелька")

            await asyncio.sleep(0.5)
        print()

    async def demo_amount_randomization(self):
        print("3️⃣ РАНДОМИЗАЦИЯ СУММ")
        print("-" * 25)

        base_amount = 0.1
        for i in range(3):
            randomized = self.config.randomize_trade_amount(base_amount)
            variation = ((randomized - base_amount) / base_amount) * 100
            print(f"💰 {base_amount} SOL → {randomized:.4f} SOL ({variation:+.1f}%)")
        print()

    async def demo_trading_simulation(self):
        print("4️⃣ СИМУЛЯЦИЯ ТОРГОВОЙ СЕССИИ")
        print("-" * 35)

        print("🚨 ПОЛУЧЕН ТОРГОВЫЙ СИГНАЛ!")
        print("   🎯 Токен: DemoToken123...ABC")
        print("   📱 Источник: @DemoChannel")
        print()

        if self.config.initial_delay_seconds > 0:
            print(f"⏱️ ЗАДЕРЖКА: {self.config.initial_delay_seconds} секунд")
            for i in range(min(3, self.config.initial_delay_seconds)):
                print(f"   ⏳ {i + 1} секунд...")
                await asyncio.sleep(1)
            print("   🚀 НАЧИНАЕМ ТОРГОВЛЮ!")
            print()

        print("💥 ВЫПОЛНЕНИЕ СДЕЛОК:")
        num_trades = min(len(self.config.wallets), 3)

        for i in range(num_trades):
            trade_amount = self.config.randomize_trade_amount(0.1)
            wallet = self.config.select_wallet_for_trade(trade_amount)

            if wallet:
                execution_time = random.uniform(150, 300)
                print(
                    f"⚡ Сделка {i + 1}: {trade_amount:.4f} SOL через {wallet.address[:8]}... ({execution_time:.0f}ms)")
                wallet.trades_count += 1

                if i < num_trades - 1:
                    delay = self.config.get_inter_trade_delay()
                    await asyncio.sleep(min(delay, 1))
        print()

    def show_summary(self):
        print("🎉 ИТОГИ ДЕМОНСТРАЦИИ")
        print("=" * 30)

        total_balance = sum(w.balance_sol for w in self.config.wallets)
        used_wallets = len([w for w in self.config.wallets if w.trades_count > 0])

        print(f"💰 Общий баланс: {total_balance:.4f} SOL")
        print(f"🎭 Использовано кошельков: {used_wallets}")
        print()

        print("🔥 ПРЕИМУЩЕСТВА:")
        print("✅ Снижение риска блэклиста на 85-95%")
        print("✅ Имитация естественного поведения")
        print("✅ Гибкая настройка стратегий")
        print()

        print("🚀 ГОТОВЫ К СНАЙПИНГУ С ЗАЩИТОЙ!")


async def main():
    demo = MultiWalletDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())