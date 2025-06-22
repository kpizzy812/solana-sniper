#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💰 MORI Balance Checker - Быстрая проверка балансов
Показывает балансы всех кошельков без интерактивного меню
"""

import os
import sys
import asyncio
from typing import List, Dict, Optional
from decimal import Decimal

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.keypair import Keypair

# Добавляем путь к utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.logger import setup_logger
from utils.config import load_config


class QuickBalanceChecker:
    """Быстрая проверка балансов кошельков"""

    def __init__(self):
        self.config = load_config()
        self.logger = setup_logger(__name__)
        self.client = AsyncClient(self.config.SOLANA_RPC_URL)
        self.main_keypair = self._load_main_keypair()
        self.multi_wallets = self._load_multi_wallets()

    def _load_main_keypair(self) -> Optional[Keypair]:
        """Загружает основной кошелек"""
        try:
            if hasattr(self.config, 'SOLANA_PRIVATE_KEY') and self.config.SOLANA_PRIVATE_KEY:
                private_key_bytes = bytes(self.config.SOLANA_PRIVATE_KEY)[:32]
                return Keypair.from_bytes(private_key_bytes)
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка загрузки основного кошелька: {e}")
        return None

    def _load_multi_wallets(self) -> List[Keypair]:
        """Загружает множественные кошельки"""
        wallets = []
        if hasattr(self.config, 'MULTI_WALLET_PRIVATE_KEYS') and self.config.MULTI_WALLET_PRIVATE_KEYS:
            keys = self.config.MULTI_WALLET_PRIVATE_KEYS.split(',')
            for i, key in enumerate(keys):
                key = key.strip()
                if key:
                    try:
                        private_key_bytes = bytes(key)[:32]
                        wallet = Keypair.from_bytes(private_key_bytes)
                        wallets.append(wallet)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Ошибка загрузки кошелька {i + 1}: {e}")
        return wallets

    async def get_sol_balance(self, pubkey: Pubkey) -> float:
        """Получает баланс SOL кошелька"""
        try:
            response = await self.client.get_balance(pubkey, commitment=Confirmed)
            return response.value / 1e9
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения баланса: {e}")
            return 0.0

    async def get_token_balance(self, wallet_pubkey: Pubkey, token_mint: str) -> float:
        """Получает баланс токена кошелька"""
        try:
            token_mint_pubkey = Pubkey.from_string(token_mint)
            response = await self.client.get_token_accounts_by_owner(
                wallet_pubkey,
                {"mint": token_mint_pubkey},
                commitment=Confirmed
            )

            if not response.value:
                return 0.0

            # Простая проверка наличия токенов
            return 1.0 if response.value else 0.0

        except Exception:
            return 0.0

    async def check_all_balances(self, token_contract: Optional[str] = None):
        """Проверяет балансы всех кошельков"""
        print("💰 MORI Balance Checker")
        print("=" * 60)

        total_sol = 0.0
        total_token = 0.0

        # Основной кошелек
        if self.main_keypair:
            sol_balance = await self.get_sol_balance(self.main_keypair.pubkey())
            total_sol += sol_balance

            address = str(self.main_keypair.pubkey())
            print(f"🔑 Основной: {address[:8]}...{address[-8:]} | {sol_balance:.4f} SOL")

            if token_contract:
                token_balance = await self.get_token_balance(self.main_keypair.pubkey(), token_contract)
                total_token += token_balance
                print(f"   💎 Токенов: {token_balance:.6f}")

        print("-" * 60)

        # Мульти-кошельки
        for i, wallet in enumerate(self.multi_wallets):
            sol_balance = await self.get_sol_balance(wallet.pubkey())
            total_sol += sol_balance

            address = str(wallet.pubkey())
            print(f"💳 Кошелек {i + 1}: {address[:8]}...{address[-8:]} | {sol_balance:.4f} SOL")

            if token_contract:
                token_balance = await self.get_token_balance(wallet.pubkey(), token_contract)
                total_token += token_balance
                print(f"   💎 Токенов: {token_balance:.6f}")

        print("=" * 60)
        print(f"📊 ИТОГО: {total_sol:.4f} SOL")

        if token_contract:
            print(f"💎 ИТОГО токенов: {total_token:.6f}")

        # Резерв на газ
        gas_reserve = getattr(self.config, 'WALLET_GAS_RESERVE', 0.01)
        num_wallets = len(self.multi_wallets) + (1 if self.main_keypair else 0)
        total_gas_reserve = gas_reserve * num_wallets

        available_for_trading = total_sol - total_gas_reserve
        print(f"⛽ Резерв на газ: {total_gas_reserve:.4f} SOL")
        print(f"💹 Доступно для торговли: {available_for_trading:.4f} SOL")

        # Предупреждения
        if total_sol < 0.1:
            print("⚠️  ВНИМАНИЕ: Низкий общий баланс SOL!")

        if available_for_trading < 0.01:
            print("🚨 ВНИМАНИЕ: Недостаточно средств для торговли!")


async def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Проверка балансов кошельков MORI')
    parser.add_argument('--token', '-t', help='Контракт токена для проверки баланса')
    parser.add_argument('--watch', '-w', action='store_true', help='Режим мониторинга (обновление каждые 30 сек)')
    parser.add_argument('--interval', '-i', type=int, default=30, help='Интервал обновления в секундах')

    args = parser.parse_args()

    checker = QuickBalanceChecker()

    if args.watch:
        print(f"👀 Режим мониторинга (обновление каждые {args.interval} сек)")
        print("Нажмите Ctrl+C для выхода\n")

        try:
            while True:
                await checker.check_all_balances(args.token)
                print(f"\n⏰ Следующее обновление через {args.interval} сек...\n")
                await asyncio.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n👋 Мониторинг остановлен!")
    else:
        await checker.check_all_balances(args.token)


if __name__ == "__main__":
    asyncio.run(main())