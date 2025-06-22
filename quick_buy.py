#!/usr/bin/env python3
"""
⚡ MORI Sniper Bot - Мгновенная покупка через командную строку
Использование: python quick_buy.py CONTRACT_ADDRESS
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


class QuickBuyer:
    """Быстрая покупка без интерактивности"""

    def __init__(self):
        self.multi_wallet_config = MultiWalletConfig()

    def print_usage(self):
        """Показать использование"""
        print("⚡ MORI SNIPER - БЫСТРАЯ ПОКУПКА")
        print("=" * 50)
        print()
        print("📋 ИСПОЛЬЗОВАНИЕ:")
        print("  python quick_buy.py CONTRACT_ADDRESS")
        print("  python quick_buy.py 'https://jup.ag/swap/SOL-CONTRACT'")
        print()
        print("📝 ПРИМЕРЫ:")
        print("  python quick_buy.py JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN")
        print(
            "  python quick_buy.py 'jup.ag/swap/So11111111111111111111111111111111111111112-JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN'")
        print()
        print("⚙️ ТЕКУЩИЕ НАСТРОЙКИ:")
        if self.multi_wallet_config.is_enabled():
            if self.multi_wallet_config.use_max_available_balance:
                print(f"🎭 Режим: ВЕСЬ БАЛАНС с {len(self.multi_wallet_config.wallets)} кошельков")
            else:
                print(
                    f"🎭 Режим: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases} с {len(self.multi_wallet_config.wallets)} кошельков")
        else:
            print(f"📱 Режим: {settings.trading.trade_amount_sol} SOL x {settings.trading.num_purchases} (один кошелек)")
        print(f"📊 Проскальзывание: {settings.trading.slippage_bps / 100}%")
        print()

    def extract_contract(self, input_str: str) -> str:
        """Извлечение контракта из строки"""
        try:
            # Прямой контракт
            if is_valid_solana_address(input_str):
                return input_str

            # URL или текст с контрактом
            if 'http' in input_str.lower():
                from utils.addresses import extract_addresses_from_any_url
                addresses = extract_addresses_from_any_url(input_str)
                if addresses:
                    return addresses[0]

            # Поиск в произвольном тексте
            addresses = extract_addresses_fast(input_str, settings.ai)
            if addresses:
                return addresses[0]

            raise ValueError("Контракт не найден")

        except Exception as e:
            raise ValueError(f"Ошибка извлечения контракта: {e}")

    async def quick_buy(self, token_contract: str):
        """Быстрая покупка без подтверждений"""
        start_time = time.time()

        # Проверяем контракт
        if is_wrapped_sol(token_contract):
            raise ValueError("Это Wrapped SOL - покупка не нужна")

        logger.critical(f"⚡ БЫСТРАЯ ПОКУПКА: {token_contract}")

        try:
            # Запускаем Jupiter trader
            logger.info("🚀 Инициализация...")
            if not await jupiter_trader.start():
                raise Exception("Не удалось запустить торговую систему")

            # Создаем торговый сигнал
            trading_signal = {
                'platform': 'quick_buy_cli',
                'source': 'Quick Buy CLI',
                'author': 'Command Line',
                'url': 'cli://quick',
                'contracts': [token_contract],
                'confidence': 1.0,
                'urgency': 'high',
                'timestamp': time.time(),
                'content_preview': f"Быстрая покупка {token_contract}",
                'emergency': True
            }

            # Выполняем покупку
            if (hasattr(jupiter_trader, 'multi_wallet_manager') and
                    jupiter_trader.multi_wallet_manager and
                    self.multi_wallet_config.is_enabled()):

                logger.info("🎭 Покупка с множественными кошельками...")

                if self.multi_wallet_config.use_max_available_balance:
                    result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                        token_address=token_contract,
                        base_trade_amount=0,
                        num_trades=0,
                        source_info=trading_signal
                    )
                else:
                    result = await jupiter_trader.multi_wallet_manager.execute_multi_wallet_trades(
                        token_address=token_contract,
                        base_trade_amount=settings.trading.trade_amount_sol,
                        num_trades=settings.trading.num_purchases,
                        source_info=trading_signal
                    )

                # Компактные результаты
                print(f"✅ ГОТОВО: {result.successful_trades}/{result.total_trades} успешно")
                print(f"💰 Потрачено: {result.total_sol_spent:.6f} SOL")
                print(f"🪙 Куплено: {result.total_tokens_bought:,.0f} токенов")
                print(f"⏱️ Время: {(time.time() - start_time):.1f}s")

                # Подписи (только первые 3)
                signatures = [r.signature for _, r in result.wallet_results if r.success and r.signature]
                if signatures:
                    print("📝 Подписи:")
                    for i, sig in enumerate(signatures[:3]):
                        print(f"   {i + 1}. {sig}")
                    if len(signatures) > 3:
                        print(f"   ... и еще {len(signatures) - 3}")

            else:
                logger.info("📱 Покупка с одиночным кошельком...")

                results = await jupiter_trader.execute_sniper_trades(
                    token_address=token_contract,
                    source_info=trading_signal
                )

                successful = [r for r in results if r.success]
                print(f"✅ ГОТОВО: {len(successful)}/{len(results)} успешно")

                if successful:
                    total_sol = sum(r.input_amount for r in successful)
                    total_tokens = sum(r.output_amount or 0 for r in successful)
                    print(f"💰 Потрачено: {total_sol:.6f} SOL")
                    print(f"🪙 Куплено: {total_tokens:,.0f} токенов")
                    print(f"⏱️ Время: {(time.time() - start_time):.1f}s")

                    # Подписи
                    for i, result in enumerate(successful):
                        if result.signature:
                            print(f"📝 Подпись {i + 1}: {result.signature}")

        finally:
            await jupiter_trader.stop()


async def main():
    """Главная функция"""
    buyer = QuickBuyer()

    # Проверяем аргументы
    if len(sys.argv) != 2:
        buyer.print_usage()
        sys.exit(1)

    contract_input = sys.argv[1]

    try:
        # Извлекаем контракт
        token_contract = buyer.extract_contract(contract_input)
        print(f"🎯 Найден контракт: {token_contract}")

        # Быстрая покупка
        await buyer.quick_buy(token_contract)

    except ValueError as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())