#!/usr/bin/env python3
"""
🧪 Тест режима трат всего доступного баланса
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.multi_wallet import MultiWalletConfig
from trading.jupiter import jupiter_trader


async def test_max_balance_mode():
    """Тест режима трат всего баланса"""
    logger.info("🧪 Тестирование режима трат всего баланса")
    logger.info("=" * 60)

    # Проверяем конфигурацию
    config = MultiWalletConfig()

    if not config.is_enabled():
        logger.error("❌ Множественные кошельки отключены")
        logger.info("💡 Установите USE_MULTI_WALLET=true в .env")
        return

    if not config.use_max_available_balance:
        logger.error("❌ Режим максимального баланса отключен")
        logger.info("💡 Установите USE_MAX_AVAILABLE_BALANCE=true в .env")
        return

    logger.success("✅ Режим максимального баланса включен")

    # Запускаем Jupiter trader
    if not await jupiter_trader.start():
        logger.error("❌ Не удалось запустить Jupiter trader")
        return

    # Обновляем балансы
    if jupiter_trader.multi_wallet_manager:
        await jupiter_trader.multi_wallet_manager.update_all_balances()

        logger.info("💰 АНАЛИЗ КОШЕЛЬКОВ:")

        for wallet in config.wallets:
            max_trade = config.get_max_trade_amount_for_wallet(wallet)
            logger.info(
                f"  {wallet.address[:8]}...: баланс={wallet.balance_sol:.6f}, доступно={wallet.available_balance:.6f}, потратим={max_trade:.6f}")

        # Тестовый план торговли
        trade_plan = jupiter_trader.multi_wallet_manager._create_trade_plan(0, 0)

        logger.critical("🎯 ПЛАН ТОРГОВЛИ:")
        total_will_spend = 0

        for wallet, amount in trade_plan:
            logger.critical(f"  Кошелек {wallet.address[:8]}...: потратим {amount:.6f} SOL")
            total_will_spend += amount

        logger.critical(f"💎 ИТОГО ПОТРАТИМ: {total_will_spend:.6f} SOL")

    else:
        logger.error("❌ Multi wallet manager не инициализирован")

    await jupiter_trader.stop()


if __name__ == "__main__":
    asyncio.run(test_max_balance_mode())