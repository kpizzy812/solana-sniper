#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 MORI Transfer Manager - Аварийный перевод средств
Интегрируется с существующей системой мультикошельков
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional
from decimal import Decimal

# Интеграция с существующей структурой проекта
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings
from config.multi_wallet import MultiWalletConfig
from utils.wallet_generator import MultiWalletGenerator, WalletInfo

# Solana imports
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price


class TransferManager:
    """Менеджер переводов SOL и SPL токенов"""

    def __init__(self):
        self.settings = settings
        self.multi_config = MultiWalletConfig()
        self.generator = MultiWalletGenerator()

        # Настраиваем RPC клиент
        self.client = AsyncClient(self.settings.solana.rpc_url)

        # Загружаем кошельки
        self.main_keypair = self._get_main_keypair()
        self.multi_wallets = self._get_multi_wallets()
        self.manual_wallets = self._get_manual_wallets()

        logger.info(f"💳 Основной кошелек: {str(self.main_keypair.pubkey())[:8]}...")
        logger.info(f"💳 Мульти-кошельков (снайпинг): {len(self.multi_wallets)}")
        logger.info(f"💳 Ручных кошельков: {len(self.manual_wallets)}")

    def _get_main_keypair(self) -> Keypair:
        """Получает основной кошелек из настроек"""
        try:
            if self.settings.solana.private_key:
                import base58
                private_key_bytes = base58.b58decode(self.settings.solana.private_key)
                return Keypair.from_bytes(private_key_bytes)
            else:
                logger.error("❌ Основной приватный ключ не найден в настройках")
                raise ValueError("Основной кошелек не настроен")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки основного кошелька: {e}")
            raise

    def _get_multi_wallets(self) -> List[Keypair]:
        """Получает мульти-кошельки из конфигурации"""
        if not self.multi_config.wallets:
            logger.warning("⚠️ Мульти-кошельки не настроены")
            return []

        return [wallet.keypair for wallet in self.multi_config.wallets]

    def _get_manual_wallets(self) -> List[Pubkey]:
        """Получает адреса ручных кошельков из .env"""
        manual_wallets = []

        # Ищем MANUAL_WALLET_1, MANUAL_WALLET_2, etc. в настройках
        import os
        for i in range(1, 11):  # До 10 ручных кошельков
            wallet_key = f"MANUAL_WALLET_{i}"
            wallet_address = os.getenv(wallet_key)

            if wallet_address:
                try:
                    pubkey = Pubkey.from_string(wallet_address.strip())
                    manual_wallets.append(pubkey)
                    logger.debug(f"✅ Ручной кошелек {i}: {str(pubkey)[:8]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Неверный адрес {wallet_key}: {e}")

        return manual_wallets

    async def get_sol_balance(self, pubkey: Pubkey) -> float:
        """Получает баланс SOL кошелька"""
        try:
            response = await self.client.get_balance(pubkey, commitment=Confirmed)
            return response.value / 1e9
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса SOL: {e}")
            return 0.0

    async def get_token_balance(self, wallet_pubkey: Pubkey, token_mint: Pubkey) -> float:
        """Получает баланс токена кошелька - ПРАВИЛЬНАЯ ВЕРСИЯ"""
        try:
            # Способ 1: Через Associated Token Account (самый надежный)
            from spl.token.instructions import get_associated_token_address

            # Получаем ATA адрес
            ata_address = get_associated_token_address(wallet_pubkey, token_mint)

            # Проверяем существование ATA
            account_info = await self.client.get_account_info(ata_address, commitment=Confirmed)

            if not account_info.value:
                logger.debug(f"📊 ATA не существует для {str(wallet_pubkey)[:8]}...")
                return 0.0

            # Парсим данные аккаунта токена вручную
            data = account_info.value.data

            if len(data) < 64:
                logger.debug(f"📊 Недостаточно данных в ATA")
                return 0.0

            # SPL Token Account layout:
            # 0-32: mint (32 bytes)
            # 32-64: owner (32 bytes)
            # 64-72: amount (8 bytes, little-endian uint64)
            # 72-73: delegate option (1 byte)
            # 73-74: state (1 byte)
            # etc...

            # Извлекаем amount (позиция 64-72)
            amount_bytes = data[64:72]
            amount_raw = int.from_bytes(amount_bytes, byteorder='little')

            if amount_raw == 0:
                return 0.0

            # Получаем decimals для токена
            decimals = await self.get_token_decimals(token_mint)

            # Вычисляем реальный баланс
            balance = amount_raw / (10 ** decimals)

            logger.debug(f"💰 Баланс {str(wallet_pubkey)[:8]}...: {balance:.6f} токенов")
            return balance

        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса токена: {e}")
            return 0.0

    async def get_token_decimals(self, token_mint: Pubkey) -> int:
        """Получает количество decimals для токена"""
        try:
            # Получаем информацию о mint аккаунте
            mint_info = await self.client.get_account_info(token_mint, commitment=Confirmed)

            if not mint_info.value:
                logger.debug(f"📊 Mint аккаунт не найден, используем 6 decimals по умолчанию")
                return 6  # Стандартное значение

            data = mint_info.value.data

            if len(data) < 44:
                return 6

            # SPL Token Mint layout:
            # 0-4: mint_authority option (4 bytes)
            # 4-8: supply (8 bytes)
            # 36: decimals (1 byte)
            decimals = data[44]  # decimals на позиции 44

            logger.debug(f"💰 Decimals для токена: {decimals}")
            return decimals

        except Exception as e:
            logger.debug(f"❌ Ошибка получения decimals: {e}, используем 6")
            return 6  # Fallback на стандартное значение

    async def transfer_sol(self, from_keypair: Keypair, to_pubkey: Pubkey, amount_sol: float) -> Dict:
        """Переводит SOL между кошельками"""
        try:
            amount_lamports = int(amount_sol * 1e9)

            # Создаем инструкцию перевода
            transfer_instruction = transfer(
                TransferParams(
                    from_pubkey=from_keypair.pubkey(),
                    to_pubkey=to_pubkey,
                    lamports=amount_lamports
                )
            )

            # Добавляем compute budget для приоритета
            compute_limit = set_compute_unit_limit(200_000)
            compute_price = set_compute_unit_price(self.settings.trading.priority_fee)

            # Создаем транзакцию
            instructions = [compute_limit, compute_price, transfer_instruction]

            # Получаем последний blockhash
            recent_blockhash = await self.client.get_latest_blockhash(commitment=Confirmed)

            # Создаем и подписываем сообщение
            message = MessageV0.try_compile(
                payer=from_keypair.pubkey(),
                instructions=instructions,
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash.value.blockhash,
            )

            transaction = VersionedTransaction(message, [from_keypair])

            # Отправляем транзакцию
            response = await self.client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed)
            )

            logger.success(f"✅ SOL перевод: {amount_sol:.4f} SOL → {str(to_pubkey)[:8]}...")

            return {
                'success': True,
                'tx_hash': str(response.value),
                'amount': amount_sol,
                'from_wallet': str(from_keypair.pubkey()),
                'to_wallet': str(to_pubkey)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка перевода SOL: {e}")
            return {
                'success': False,
                'error': str(e),
                'amount': amount_sol,
                'from_wallet': str(from_keypair.pubkey()),
                'to_wallet': str(to_pubkey)
            }

    async def transfer_token(self, from_keypair: Keypair, to_pubkey: Pubkey,
                             token_mint: Pubkey, amount: float) -> Dict:
        """Переводит SPL токены между кошельками - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Правильные импорты
            from spl.token.instructions import (
                transfer_checked,
                TransferCheckedParams,
                create_associated_token_account
            )
            from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
            from spl.token.instructions import get_associated_token_address

            from_ata = get_associated_token_address(from_keypair.pubkey(), token_mint)
            to_ata = get_associated_token_address(to_pubkey, token_mint)

            instructions = []

            # Проверяем существование target ATA и создаем если нужно
            to_account_info = await self.client.get_account_info(to_ata, commitment=Confirmed)
            if not to_account_info.value:
                # ИСПРАВЛЕНО: Правильные параметры для create_associated_token_account
                create_ata_ix = create_associated_token_account(
                    payer=from_keypair.pubkey(),
                    owner=to_pubkey,
                    mint=token_mint,
                    token_program_id=TOKEN_PROGRAM_ID,
                    associated_token_program_id=ASSOCIATED_TOKEN_PROGRAM_ID
                )
                instructions.append(create_ata_ix)

            # Получаем правильное количество decimals
            decimals = await self.get_token_decimals(token_mint)
            amount_with_decimals = int(amount * (10 ** decimals))

            # Создаем инструкцию перевода токена
            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=from_ata,
                    mint=token_mint,
                    dest=to_ata,
                    owner=from_keypair.pubkey(),
                    amount=amount_with_decimals,
                    decimals=decimals
                )
            )

            instructions.append(transfer_ix)

            # Добавляем compute budget
            compute_limit = set_compute_unit_limit(300_000)
            compute_price = set_compute_unit_price(self.settings.trading.priority_fee)

            all_instructions = [compute_limit, compute_price] + instructions

            # Получаем последний blockhash
            recent_blockhash = await self.client.get_latest_blockhash(commitment=Confirmed)

            # Создаем и подписываем транзакцию
            message = MessageV0.try_compile(
                payer=from_keypair.pubkey(),
                instructions=all_instructions,
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash.value.blockhash,
            )

            transaction = VersionedTransaction(message, [from_keypair])

            # Отправляем транзакцию
            response = await self.client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed)
            )

            logger.success(f"✅ Токен перевод: {amount:.6f} токенов → {str(to_pubkey)[:8]}...")

            return {
                'success': True,
                'tx_hash': str(response.value),
                'amount': amount,
                'from_wallet': str(from_keypair.pubkey()),
                'to_wallet': str(to_pubkey)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка перевода токена: {e}")
            return {
                'success': False,
                'error': str(e),
                'amount': amount,
                'from_wallet': str(from_keypair.pubkey()),
                'to_wallet': str(to_pubkey)
            }

    async def distribute_sol(self, custom_amounts: List[float] = None) -> List[Dict]:
        """
        Распределяет SOL с основного кошелька по мульти-кошелькам

        Args:
            custom_amounts: Список конкретных сумм для каждого кошелька (в SOL).
                          Если None - распределяет поровну весь доступный баланс
        """
        if not self.multi_wallets:
            logger.error("❌ Мульти-кошельки не настроены!")
            return []

        results = []

        # Получаем баланс основного кошелька
        main_balance = await self.get_sol_balance(self.main_keypair.pubkey())
        gas_reserve = self.multi_config.gas_reserve
        available_balance = main_balance - gas_reserve

        if available_balance <= 0:
            logger.warning(f"⚠️ Недостаточно SOL для распределения. Баланс: {main_balance:.4f}, резерв: {gas_reserve}")
            return results

        num_wallets = len(self.multi_wallets)

        # Если указаны конкретные суммы
        if custom_amounts is not None:
            if len(custom_amounts) != num_wallets:
                logger.error(
                    f"❌ Количество сумм ({len(custom_amounts)}) не совпадает с количеством кошельков ({num_wallets})")
                return results

            total_needed = sum(custom_amounts)
            if total_needed > available_balance:
                logger.error(f"❌ Запрошено {total_needed:.4f} SOL, доступно {available_balance:.4f} SOL")
                return results

            amounts = custom_amounts
            logger.info(f"💰 Распределяем по указанным суммам: {total_needed:.4f} SOL на {num_wallets} кошельков")
            for i, amount in enumerate(amounts):
                logger.info(f"💳 Кошелек {i + 1}: {amount:.4f} SOL")

        else:
            # Стандартная логика - поровну
            amount_per_wallet = available_balance / num_wallets
            amounts = [amount_per_wallet] * num_wallets
            logger.info(f"💰 Распределяем поровну {available_balance:.4f} SOL на {num_wallets} кошельков")
            logger.info(f"💳 По {amount_per_wallet:.4f} SOL на кошелек")

        # Переводим на каждый кошелек
        for i, (wallet, amount) in enumerate(zip(self.multi_wallets, amounts)):
            if amount <= 0:
                logger.info(f"⏭️ Кошелек {i + 1}: пропускаем (сумма {amount:.4f} SOL)")
                continue

            logger.info(f"📤 Перевод {i + 1}/{num_wallets}: {amount:.4f} SOL → {str(wallet.pubkey())[:8]}...")

            result = await self.transfer_sol(
                self.main_keypair,
                wallet.pubkey(),
                amount
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            # Небольшая задержка между переводами
            await asyncio.sleep(1)

        return results

    async def transfer_to_manual_wallets_sol(self) -> List[Dict]:
        """Собирает SOL с мульти-кошельков и переводит на ручные кошельки"""
        if not self.manual_wallets:
            logger.error("❌ Ручные кошельки не настроены в .env!")
            logger.info("💡 Добавьте в .env: MANUAL_WALLET_1=address1, MANUAL_WALLET_2=address2...")
            return []

        results = []

        # Сначала собираем все SOL с мульти-кошельков на основной
        logger.info("📥 Собираем SOL с мульти-кошельков...")
        collect_results = await self.collect_sol()

        successful_collects = sum(1 for r in collect_results if r['success'])
        if successful_collects == 0:
            logger.warning("⚠️ Не удалось собрать SOL с мульти-кошельков")
            return results

        # Даем время на подтверждение транзакций
        logger.info("⏳ Ожидание подтверждения транзакций...")
        await asyncio.sleep(3)

        # Получаем обновленный баланс основного кошелька
        main_balance = await self.get_sol_balance(self.main_keypair.pubkey())
        gas_reserve = self.multi_config.gas_reserve
        available_balance = main_balance - gas_reserve

        if available_balance <= 0:
            logger.warning(f"⚠️ Недостаточно SOL для распределения на ручные кошельки")
            return results

        # Рассчитываем сумму на каждый ручной кошелек
        num_manual_wallets = len(self.manual_wallets)
        amount_per_wallet = available_balance / num_manual_wallets

        logger.info(f"💰 Распределяем {available_balance:.4f} SOL на {num_manual_wallets} ручных кошельков")
        logger.info(f"💳 По {amount_per_wallet:.4f} SOL на кошелек")

        # Переводим на каждый ручной кошелек
        for i, manual_wallet in enumerate(self.manual_wallets):
            logger.info(f"📤 Перевод {i + 1}/{num_manual_wallets} на ручной кошелек {str(manual_wallet)[:8]}...")

            result = await self.transfer_sol(
                self.main_keypair,
                manual_wallet,
                amount_per_wallet
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            await asyncio.sleep(1)

        return results

    async def transfer_to_manual_wallets_token(self, token_contract: str) -> List[Dict]:
        """Собирает токены с мульти-кошельков и переводит на ручные кошельки"""
        if not self.manual_wallets:
            logger.error("❌ Ручные кошельки не настроены в .env!")
            return []

        results = []

        try:
            token_mint = Pubkey.from_string(token_contract)
        except Exception as e:
            logger.error(f"❌ Неверный контракт токена: {e}")
            return results

        # Сначала собираем все токены с мульти-кошельков на основной
        logger.info("📥 Собираем токены с мульти-кошельков...")
        collect_results = await self.collect_token(token_contract)

        successful_collects = sum(1 for r in collect_results if r['success'])
        if successful_collects == 0:
            logger.warning("⚠️ Не удалось собрать токены с мульти-кошельков")
            return results

        # Даем время на подтверждение транзакций
        logger.info("⏳ Ожидание подтверждения транзакций...")
        await asyncio.sleep(5)

        # Получаем обновленный баланс токенов основного кошелька
        main_token_balance = await self.get_token_balance(self.main_keypair.pubkey(), token_mint)

        if main_token_balance <= 0:
            logger.warning(f"⚠️ Нет токенов для распределения на ручные кошельки")
            return results

        # Рассчитываем сумму на каждый ручной кошелек
        num_manual_wallets = len(self.manual_wallets)
        amount_per_wallet = main_token_balance / num_manual_wallets

        logger.info(f"💰 Распределяем {main_token_balance:.6f} токенов на {num_manual_wallets} ручных кошельков")
        logger.info(f"💳 По {amount_per_wallet:.6f} токенов на кошелек")

        # Переводим на каждый ручной кошелек
        for i, manual_wallet in enumerate(self.manual_wallets):
            logger.info(f"📤 Перевод {i + 1}/{num_manual_wallets} на ручной кошелек {str(manual_wallet)[:8]}...")

            result = await self.transfer_token(
                self.main_keypair,
                manual_wallet,
                token_mint,
                amount_per_wallet
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            await asyncio.sleep(2)

        return results

    async def distribute_sol_to_manual(self) -> List[Dict]:
        """Распределяет SOL с основного кошелька на ручные кошельки (без сбора с мульти)"""
        if not self.manual_wallets:
            logger.error("❌ Ручные кошельки не настроены в .env!")
            return []

        results = []

        # Получаем баланс основного кошелька
        main_balance = await self.get_sol_balance(self.main_keypair.pubkey())
        gas_reserve = self.multi_config.gas_reserve
        available_balance = main_balance - gas_reserve

        if available_balance <= 0:
            logger.warning(f"⚠️ Недостаточно SOL для распределения. Баланс: {main_balance:.4f}, резерв: {gas_reserve}")
            return results

        # Рассчитываем сумму на каждый ручной кошелек
        num_manual_wallets = len(self.manual_wallets)
        amount_per_wallet = available_balance / num_manual_wallets

        logger.info(f"💰 Распределяем {available_balance:.4f} SOL на {num_manual_wallets} ручных кошельков")
        logger.info(f"💳 По {amount_per_wallet:.4f} SOL на кошелек")

        # Переводим на каждый ручной кошелек
        for i, manual_wallet in enumerate(self.manual_wallets):
            logger.info(f"📤 Перевод {i + 1}/{num_manual_wallets} на ручной кошелек {str(manual_wallet)[:8]}...")

            result = await self.transfer_sol(
                self.main_keypair,
                manual_wallet,
                amount_per_wallet
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            await asyncio.sleep(1)

        return results

        # Рассчитываем сумму на каждый кошелек
        num_wallets = len(self.multi_wallets)
        amount_per_wallet = available_balance / num_wallets

        logger.info(f"💰 Распределяем {available_balance:.4f} SOL на {num_wallets} кошельков")
        logger.info(f"💳 По {amount_per_wallet:.4f} SOL на кошелек")

        # Переводим на каждый кошелек
        for i, wallet in enumerate(self.multi_wallets):
            logger.info(f"📤 Перевод {i + 1}/{num_wallets} на {str(wallet.pubkey())[:8]}...")

            result = await self.transfer_sol(
                self.main_keypair,
                wallet.pubkey(),
                amount_per_wallet
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            # Небольшая задержка между переводами
            await asyncio.sleep(1)

        return results

    async def distribute_token(self, token_contract: str) -> List[Dict]:
        """Распределяет токены с основного кошелька по мульти-кошелькам"""
        if not self.multi_wallets:
            logger.error("❌ Мульти-кошельки не настроены!")
            return []

        results = []

        try:
            token_mint = Pubkey.from_string(token_contract)
        except Exception as e:
            logger.error(f"❌ Неверный контракт токена: {e}")
            return results

        # Получаем баланс токенов основного кошелька
        main_token_balance = await self.get_token_balance(self.main_keypair.pubkey(), token_mint)

        if main_token_balance <= 0:
            logger.warning(f"⚠️ Нет токенов для перевода на основном кошельке")
            return results

        # Рассчитываем сумму на каждый кошелек
        num_wallets = len(self.multi_wallets)
        amount_per_wallet = main_token_balance / num_wallets

        logger.info(f"💰 Распределяем {main_token_balance:.6f} токенов на {num_wallets} кошельков")
        logger.info(f"💳 По {amount_per_wallet:.6f} токенов на кошелек")

        # Переводим на каждый кошелек
        for i, wallet in enumerate(self.multi_wallets):
            logger.info(f"📤 Перевод {i + 1}/{num_wallets} на {str(wallet.pubkey())[:8]}...")

            result = await self.transfer_token(
                self.main_keypair,
                wallet.pubkey(),
                token_mint,
                amount_per_wallet
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            # Задержка между переводами токенов
            await asyncio.sleep(2)

        return results

    async def collect_sol(self) -> List[Dict]:
        """Собирает SOL с мульти-кошельков на основной кошелек"""
        if not self.multi_wallets:
            logger.error("❌ Мульти-кошельки не настроены!")
            return []

        results = []

        for i, wallet in enumerate(self.multi_wallets):
            # Получаем баланс кошелька
            balance = await self.get_sol_balance(wallet.pubkey())

            # Рассчитываем доступную сумму (минус резерв на газ)
            gas_reserve = self.multi_config.gas_reserve
            available_balance = balance - gas_reserve

            if available_balance <= 0:
                logger.info(f"⏭️ Кошелек {i + 1}: недостаточно SOL для перевода")
                continue

            logger.info(f"📥 Собираем {available_balance:.4f} SOL с кошелька {i + 1}")

            result = await self.transfer_sol(
                wallet,
                self.main_keypair.pubkey(),
                available_balance
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            await asyncio.sleep(1)

        return results

    async def collect_token(self, token_contract: str) -> List[Dict]:
        """Собирает токены с мульти-кошельков на основной кошелек"""
        if not self.multi_wallets:
            logger.error("❌ Мульти-кошельки не настроены!")
            return []

        results = []

        try:
            token_mint = Pubkey.from_string(token_contract)
        except Exception as e:
            logger.error(f"❌ Неверный контракт токена: {e}")
            return results

        for i, wallet in enumerate(self.multi_wallets):
            # Получаем баланс токенов кошелька
            token_balance = await self.get_token_balance(wallet.pubkey(), token_mint)

            if token_balance <= 0:
                logger.info(f"⏭️ Кошелек {i + 1}: нет токенов для перевода")
                continue

            logger.info(f"📥 Собираем {token_balance:.6f} токенов с кошелька {i + 1}")

            result = await self.transfer_token(
                wallet,
                self.main_keypair.pubkey(),
                token_mint,
                token_balance
            )

            results.append(result)

            if not result['success']:
                logger.error(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

            await asyncio.sleep(2)

        return results

    async def show_balances(self, token_contract: Optional[str] = None):
        """Показывает балансы всех кошельков"""
        print("\n💰 БАЛАНСЫ КОШЕЛЬКОВ")
        print("=" * 60)

        total_sol = 0.0
        total_token = 0.0

        # Основной кошелек
        main_balance = await self.get_sol_balance(self.main_keypair.pubkey())
        total_sol += main_balance

        address = str(self.main_keypair.pubkey())
        print(f"🔑 Основной: {address[:8]}...{address[-8:]} | {main_balance:.4f} SOL")

        if token_contract:
            try:
                token_mint = Pubkey.from_string(token_contract)
                token_balance = await self.get_token_balance(self.main_keypair.pubkey(), token_mint)
                total_token += token_balance
                print(f"   💎 Токенов: {token_balance:.6f}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения баланса токена: {e}")

        print("-" * 60)

        # Мульти-кошельки (снайпинг)
        if self.multi_wallets:
            print("🤖 МУЛЬТИ-КОШЕЛЬКИ (снайпинг):")
            for i, wallet in enumerate(self.multi_wallets):
                sol_balance = await self.get_sol_balance(wallet.pubkey())
                total_sol += sol_balance

                address = str(wallet.pubkey())
                print(f"💳 Кошелек {i + 1}: {address[:8]}...{address[-8:]} | {sol_balance:.4f} SOL")

                if token_contract:
                    try:
                        token_mint = Pubkey.from_string(token_contract)
                        token_balance = await self.get_token_balance(wallet.pubkey(), token_mint)
                        total_token += token_balance
                        print(f"   💎 Токенов: {token_balance:.6f}")
                    except Exception:
                        pass

        print("-" * 60)

        # Ручные кошельки
        if self.manual_wallets:
            print("✋ РУЧНЫЕ КОШЕЛЬКИ (для ручной торговли):")
            for i, wallet in enumerate(self.manual_wallets):
                sol_balance = await self.get_sol_balance(wallet)
                total_sol += sol_balance

                address = str(wallet)
                print(f"👤 Ручной {i + 1}: {address[:8]}...{address[-8:]} | {sol_balance:.4f} SOL")

                if token_contract:
                    try:
                        token_mint = Pubkey.from_string(token_contract)
                        token_balance = await self.get_token_balance(wallet, token_mint)
                        total_token += token_balance
                        print(f"   💎 Токенов: {token_balance:.6f}")
                    except Exception:
                        pass

        print("=" * 60)
        print(f"📊 ИТОГО: {total_sol:.4f} SOL")

        if token_contract:
            print(f"💎 ИТОГО токенов: {total_token:.6f}")

        # Резерв на газ
        num_all_wallets = len(self.multi_wallets) + 1 + len(self.manual_wallets)
        total_gas_reserve = self.multi_config.gas_reserve * num_all_wallets
        available_for_trading = total_sol - total_gas_reserve

        print(f"⛽ Резерв на газ: {total_gas_reserve:.4f} SOL")
        print(f"💹 Доступно для торговли: {available_for_trading:.4f} SOL")


async def main():
    """Главная функция с интерактивным меню"""
    print("🔄 MORI Transfer Manager")
    print("=" * 50)

    try:
        manager = TransferManager()
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        print("💡 Убедитесь что настроены:")
        print("   - Основной кошелек в .env (SOLANA_PRIVATE_KEY)")
        print("   - Мульти-кошельки (MULTI_WALLET_PRIVATE_KEYS)")
        return

    if len(manager.multi_wallets) == 0 and len(manager.manual_wallets) == 0:
        print("❌ Ни мульти-кошельки, ни ручные кошельки не настроены!")
        print("💡 Запустите: python utils/wallet_generator.py")
        print("💡 Добавьте в .env: MANUAL_WALLET_1=address1, MANUAL_WALLET_2=address2...")
        return

    while True:
        print("\n🎯 Выберите режим:")
        print("=" * 50)
        print("📤 РАСПРЕДЕЛЕНИЕ:")
        print("1. 📤 Распределить SOL по мульти-кошелькам")
        print("2. 📤 Распределить токены по мульти-кошелькам")
        print("3. 🎯 Распределить SOL на ручные кошельки")
        print("")
        print("📥 СБОР:")
        print("4. 📥 Собрать SOL с мульти на основной")
        print("5. 📥 Собрать токены с мульти на основной")
        print("")
        print("🚨 АВАРИЙНЫЕ (мульти → ручные):")
        print("6. 🚨 Собрать SOL и переслать на ручные кошельки")
        print("7. 🚨 Собрать токены и переслать на ручные кошельки")
        print("")
        print("💰 ИНФО:")
        print("8. 💰 Показать балансы всех кошельков")
        print("0. ❌ Выход")

        choice = input("\n👉 Ваш выбор: ").strip()

        if choice == "1":
            # Распределение SOL по мульти-кошелькам
            if not manager.multi_wallets:
                print("❌ Мульти-кошельки не настроены!")
                continue

            print("\n📤 Распределение SOL по мульти-кошелькам")
            print("=" * 50)
            print("Выберите способ распределения:")
            print("1. ⚖️ Поровну между всеми кошельками")
            print("2. 💰 Указать конкретные суммы для каждого")

            mode = input("👉 Ваш выбор: ").strip()

            if mode == "1":
                # Поровну
                print("\n📤 Распределение поровну...")
                results = await manager.distribute_sol()

            elif mode == "2":
                # Конкретные суммы
                num_wallets = len(manager.multi_wallets)
                print(f"\n💰 Укажите суммы для {num_wallets} кошельков:")

                # Показываем доступный баланс
                main_balance = await manager.get_sol_balance(manager.main_keypair.pubkey())
                available = main_balance - manager.multi_config.gas_reserve
                print(f"💳 Доступно для распределения: {available:.4f} SOL")

                custom_amounts = []
                total_requested = 0.0

                for i in range(num_wallets):
                    while True:
                        try:
                            amount_str = input(f"💳 Кошелек {i + 1} (SOL): ").strip()
                            if not amount_str:
                                amount = 0.0
                            else:
                                amount = float(amount_str)

                            if amount < 0:
                                print("❌ Сумма не может быть отрицательной!")
                                continue

                            custom_amounts.append(amount)
                            total_requested += amount
                            break
                        except ValueError:
                            print("❌ Введите корректную сумму!")

                print(f"\n📊 Всего запрошено: {total_requested:.4f} SOL")
                print(f"💳 Доступно: {available:.4f} SOL")

                if total_requested > available:
                    print("❌ Запрошенная сумма превышает доступную!")
                    continue

                # Подтверждение
                print("\n🔍 Распределение:")
                for i, amount in enumerate(custom_amounts):
                    if amount > 0:
                        print(f"💳 Кошелек {i + 1}: {amount:.4f} SOL")

                confirm = input("\n✅ Подтвердить распределение? (y/n): ").strip().lower()
                if confirm not in ['y', 'yes', 'да']:
                    print("❌ Отменено!")
                    continue

                print("\n📤 Распределение по указанным суммам...")
                results = await manager.distribute_sol(custom_amounts)
            else:
                print("❌ Неверный выбор!")
                continue

            if results is not None:
                success_count = sum(1 for r in results if r['success'])
            else:
                success_count = 0
                print("❌ Функция вернула None!")
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов")

        elif choice == "2":
            # Распределение токенов по мульти-кошелькам
            if not manager.multi_wallets:
                print("❌ Мульти-кошельки не настроены!")
                continue
            token_contract = input("\n💰 Введите контракт токена: ").strip()
            if not token_contract:
                print("❌ Контракт не введен!")
                continue

            print(f"\n📤 Распределение токенов {token_contract[:8]}... по мульти-кошелькам")
            results = await manager.distribute_token(token_contract)

            success_count = sum(1 for r in results if r['success'])
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов")

        elif choice == "3":
            # Распределение SOL на ручные кошельки
            if not manager.manual_wallets:
                print("❌ Ручные кошельки не настроены!")
                print("💡 Добавьте в .env: MANUAL_WALLET_1=address1, MANUAL_WALLET_2=address2...")
                continue
            print("\n🎯 Распределение SOL на ручные кошельки...")
            results = await manager.distribute_sol_to_manual()

            success_count = sum(1 for r in results if r['success'])
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов")
            print("💡 Теперь можете покупать руками с ручных кошельков!")

        elif choice == "4":
            # Сбор SOL с мульти на основной
            if not manager.multi_wallets:
                print("❌ Мульти-кошельки не настроены!")
                continue
            print("\n📥 Сбор SOL с мульти-кошельков на основной...")
            results = await manager.collect_sol()

            success_count = sum(1 for r in results if r['success'])
            total_collected = sum(r['amount'] for r in results if r['success'])
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов")
            print(f"💰 Собрано: {total_collected:.4f} SOL")

        elif choice == "5":
            # Сбор токенов с мульти на основной
            if not manager.multi_wallets:
                print("❌ Мульти-кошельки не настроены!")
                continue
            token_contract = input("\n💰 Введите контракт токена: ").strip()
            if not token_contract:
                print("❌ Контракт не введен!")
                continue

            print(f"\n📥 Сбор токенов {token_contract[:8]}... с мульти-кошельков")
            results = await manager.collect_token(token_contract)

            success_count = sum(1 for r in results if r['success'])
            total_collected = sum(r['amount'] for r in results if r['success'])
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов")
            print(f"💰 Собрано: {total_collected:.6f} токенов")

        elif choice == "6":
            # АВАРИЙНЫЙ: Собрать SOL и переслать на ручные кошельки
            if not manager.manual_wallets:
                print("❌ Ручные кошельки не настроены!")
                print("💡 Добавьте в .env: MANUAL_WALLET_1=address1, MANUAL_WALLET_2=address2...")
                continue
            print("\n🚨 АВАРИЙНЫЙ РЕЖИМ: Собираем SOL с мульти → переводим на ручные кошельки")
            print("💡 Это займет ~30-60 секунд...")
            results = await manager.transfer_to_manual_wallets_sol()

            success_count = sum(1 for r in results if r['success'])
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов на ручные кошельки")
            print("💡 Теперь можете покупать руками с ручных кошельков!")

        elif choice == "7":
            # АВАРИЙНЫЙ: Собрать токены и переслать на ручные кошельки
            if not manager.manual_wallets:
                print("❌ Ручные кошельки не настроены!")
                continue
            token_contract = input("\n💰 Введите контракт токена: ").strip()
            if not token_contract:
                print("❌ Контракт не введен!")
                continue

            print(f"\n🚨 АВАРИЙНЫЙ РЕЖИМ: Собираем токены {token_contract[:8]}... с мульти → переводим на ручные")
            print("💡 Это займет ~60-120 секунд...")
            results = await manager.transfer_to_manual_wallets_token(token_contract)

            success_count = sum(1 for r in results if r['success'])
            print(f"\n📊 Результат: {success_count}/{len(results)} успешных переводов на ручные кошельки")
            print("💡 Теперь можете продавать руками с ручных кошельков!")

        elif choice == "8":
            # Показать балансы
            token_contract = input("\n💰 Контракт токена (или Enter для только SOL): ").strip()
            if not token_contract:
                token_contract = None

            await manager.show_balances(token_contract)

        elif choice == "0":
            print("👋 До свидания!")
            break

        else:
            print("❌ Неверный выбор!")


if __name__ == "__main__":
    asyncio.run(main())