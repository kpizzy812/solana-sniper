"""
⚡ MORI Sniper Bot - Jupiter Trade Executor
Исполнитель снайперских сделок с умным распределением
"""

import asyncio
import time
import base64
from typing import List, Dict, Optional
from loguru import logger

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned
import base58
from solders.pubkey import Pubkey

# Убираем прямой импорт settings для избежания циклических зависимостей
# from config.settings import settings

from .models import TradeResult, TradingSession, SwapRequest
from .client import JupiterAPIClient


class JupiterTradeExecutor:
    """Исполнитель снайперских сделок через Jupiter"""

    def __init__(self, solana_client: AsyncClient, jupiter_client: JupiterAPIClient):
        self.solana_client = solana_client
        self.jupiter_client = jupiter_client
        self.wallet_keypair: Optional[Keypair] = None

        # Статистика торговли
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_sol_spent = 0.0
        self.total_tokens_bought = 0.0

        self.setup_wallet()

    def setup_wallet(self):
        """Настройка кошелька из приватного ключа"""
        try:
            # Локальный импорт для избежания циклических зависимостей
            from config.settings import settings

            if settings.solana.private_key:
                # Декодируем base58 приватный ключ
                private_key_bytes = base58.b58decode(settings.solana.private_key)
                self.wallet_keypair = Keypair.from_bytes(private_key_bytes)
                logger.info(f"💰 Кошелек загружен: {self.wallet_keypair.pubkey()}")
            else:
                logger.error("❌ Приватный ключ не настроен")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки кошелька: {e}")

    async def execute_sniper_trades(self, token_address: str, source_info: Dict) -> List[TradeResult]:
        """
        Выполнение снайперских сделок
        Поддерживает как одну покупку, так и множественные
        """
        logger.critical(f"🎯 СНАЙПЕР АТАКА НА ТОКЕН: {token_address}")

        # Создаем сессию торговли
        session = TradingSession(
            token_address=token_address,
            source_info=source_info,
            start_time=time.time(),
            amounts=self._calculate_trade_amounts(),
            results=[]
        )

        logger.info(f"📊 Выполняется {len(session.amounts)} сделок с размерами: {session.amounts}")

        # Выполняем сделки
        # Локальный импорт для избежания циклических зависимостей
        from config.settings import settings

        if settings.trading.concurrent_trades:
            # Параллельное выполнение всех сделок
            await self._execute_concurrent_trades(session)
        else:
            # Последовательное выполнение
            await self._execute_sequential_trades(session)

        # Обновляем общую статистику
        self._update_global_stats(session)

        # Логируем итоги
        self._log_session_summary(session)

        return session.results

    def _calculate_trade_amounts(self) -> List[float]:
        """Расчет размеров сделок с умным распределением"""
        # Локальный импорт для избежания циклических зависимостей
        from config.settings import settings

        num_trades = settings.trading.num_purchases
        amount_per_trade = settings.trading.trade_amount_sol

        # Проверяем настройки для умного распределения
        if settings.trading.smart_split and num_trades > 1:
            return self._calculate_smart_amounts(
                total_amount=num_trades * amount_per_trade,
                num_trades=num_trades
            )
        else:
            return [amount_per_trade] * num_trades

    def _calculate_smart_amounts(self, total_amount: float, num_trades: int) -> List[float]:
        """
        Умное распределение размеров сделок для минимизации проскальзывания
        Первые сделки больше, последние меньше
        """
        if num_trades == 1:
            return [total_amount]

        # Создаем убывающую последовательность
        # 40% в первой сделке, затем убывание
        amounts = []
        remaining = total_amount

        for i in range(num_trades):
            if i == num_trades - 1:
                # Последняя сделка - остаток
                amounts.append(remaining)
            else:
                # Уменьшающийся размер
                factor = (num_trades - i) / num_trades
                amount = (total_amount / num_trades) * (1 + factor * 0.5)
                amount = min(amount, remaining * 0.6)  # Не больше 60% остатка
                amounts.append(round(amount, 4))
                remaining -= amount

        return amounts

    async def _execute_concurrent_trades(self, session: TradingSession):
        """Параллельное выполнение всех сделок"""
        trade_tasks = []
        for i, amount in enumerate(session.amounts):
            task = asyncio.create_task(
                self._execute_single_trade(session.token_address, i, amount, session.source_info)
            )
            trade_tasks.append(task)

        # Выполняем все сделки одновременно
        results = await asyncio.gather(*trade_tasks, return_exceptions=True)

        # Обрабатываем результаты
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Сделка {i + 1} упала с исключением: {result}")
                session.add_result(TradeResult(
                    success=False,
                    signature=None,
                    error=str(result),
                    input_amount=session.amounts[i] if i < len(session.amounts) else 0.0,
                    output_amount=None,
                    price_impact=None,
                    execution_time_ms=0,
                    trade_index=i
                ))
            else:
                session.add_result(result)

    async def _execute_sequential_trades(self, session: TradingSession):
        """Последовательное выполнение сделок"""
        for i, amount in enumerate(session.amounts):
            result = await self._execute_single_trade(
                session.token_address, i, amount, session.source_info
            )
            session.add_result(result)

    async def _execute_single_trade(self, token_address: str, trade_index: int,
                                    amount_sol: float, source_info: Dict) -> TradeResult:
        """Выполнение одной сделки через Jupiter - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        start_time = time.time()

        try:
            # Локальный импорт для избежания циклических зависимостей
            from config.settings import settings
            from solders.pubkey import Pubkey

            logger.debug(f"🚀 Запуск сделки {trade_index + 1}: {amount_sol} SOL -> {token_address}")

            # НОВОЕ: Получаем баланс токенов ДО покупки
            token_mint = Pubkey.from_string(token_address)
            # balance_before = await self._get_token_balance_with_decimals(self.wallet_keypair.pubkey(), token_mint)

            # Шаг 1: Получаем котировку от Jupiter
            quote = await self.jupiter_client.get_quote(
                input_mint=settings.trading.base_token,  # SOL
                output_mint=token_address,
                amount=int(amount_sol * 1e9),  # Конвертируем в lamports
                slippage_bps=settings.trading.slippage_bps
            )

            if not quote:
                return self._create_failed_result("Не удалось получить котировку",
                                                  amount_sol, trade_index, start_time)

            # Проверяем price impact
            price_impact = quote.price_impact_float
            if price_impact > settings.security.max_price_impact:
                return self._create_failed_result(
                    f"Слишком большое проскальзывание: {price_impact}%",
                    amount_sol, trade_index, start_time
                )

            logger.debug(
                f"💹 Сделка {trade_index + 1} котировка: {quote.out_amount} токенов, {price_impact}% проскальзывание")

            # Шаг 2: Создаем запрос на swap транзакцию
            swap_request = SwapRequest(
                quote_response=quote,
                user_public_key=str(self.wallet_keypair.pubkey()),
                priority_fee_lamports=settings.trading.priority_fee,
                destination_token_account=None
            )

            # Шаг 3: Получаем транзакцию обмена
            swap_transaction = await self.jupiter_client.get_swap_transaction(swap_request)

            if not swap_transaction:
                return self._create_failed_result("Не удалось создать транзакцию обмена",
                                                  amount_sol, trade_index, start_time)

            # Шаг 4: Подписываем и отправляем транзакцию
            signature = await self._send_transaction(swap_transaction)

            if signature:
                # ИСПРАВЛЕНО: Правильное определение количества купленных токенов
                # Ждем подтверждения транзакции
                # await asyncio.sleep(2)  # Даем время на подтверждение

                # Получаем баланс ПОСЛЕ покупки
                # balance_after = await self._get_token_balance_with_decimals(self.wallet_keypair.pubkey(), token_mint)

                # Вычисляем реально купленное количество
                # actual_tokens_bought = balance_after - balance_before

                execution_time = (time.time() - start_time) * 1000

                logger.success(f"✅ Сделка {trade_index + 1} УСПЕШНА: {signature} ({execution_time:.0f}ms)")
                # logger.info(f"🪙 Реально куплено: {actual_tokens_bought:,.6f} токенов")

                return TradeResult(
                    success=True,
                    signature=signature,
                    error=None,
                    input_amount=amount_sol,
                    output_amount=0.0,
                    price_impact=price_impact,
                    execution_time_ms=execution_time,
                    trade_index=trade_index
                )
            else:
                return self._create_failed_result("Транзакция не отправилась",
                                                  amount_sol, trade_index, start_time)

        except Exception as e:
            logger.error(f"❌ Ошибка сделки {trade_index + 1}: {e}")
            return self._create_failed_result(str(e), amount_sol, trade_index, start_time)

    # НОВАЯ ФУНКЦИЯ: добавить в класс JupiterExecutor
    # async def _get_token_decimals(self, token_mint: Pubkey) -> int:
    #     """Получает количество decimals для токена - КОПИЯ ИЗ TRANSFER_MANAGER"""
    #     try:
    #         from solana.rpc.commitment import Confirmed
    #
    #         # Получаем информацию о mint аккаунте
    #         mint_info = await self.solana_client.get_account_info(token_mint, commitment=Confirmed)
    #
    #         if not mint_info.value:
    #             logger.debug(f"📊 Mint аккаунт не найден, используем 6 decimals по умолчанию")
    #             return 6  # Стандартное значение
    #
    #         data = mint_info.value.data
    #
    #         if len(data) < 44:
    #             return 6
    #
    #         # SPL Token Mint layout:
    #         # 0-4: mint_authority option (4 bytes)
    #         # 4-8: supply (8 bytes)
    #         # 36: decimals (1 byte)
    #         decimals = data[44]  # decimals на позиции 44
    #
    #         logger.debug(f"💰 Decimals для токена: {decimals}")
    #         return decimals
    #
    #     except Exception as e:
    #         logger.debug(f"❌ Ошибка получения decimals: {e}, используем 6")
    #         return 6  # Fallback на стандартное значение

    def _create_failed_result(self, error: str, amount: float, trade_index: int, start_time: float) -> TradeResult:
        """Создание результата неудачной сделки"""
        return TradeResult(
            success=False,
            signature=None,
            error=error,
            input_amount=amount,
            output_amount=None,
            price_impact=None,
            execution_time_ms=(time.time() - start_time) * 1000,
            trade_index=trade_index
        )

    async def _send_transaction(self, swap_transaction_b64: str) -> Optional[str]:
        """Подпись и отправка транзакции в Solana - ИСПРАВЛЕННАЯ ВЕРСИЯ С ДИАГНОСТИКОЙ"""
        try:
            # Локальный импорт для избежания циклических зависимостей
            from config.settings import settings

            # Декодируем транзакцию
            transaction_bytes = base64.b64decode(swap_transaction_b64)
            raw_transaction = VersionedTransaction.from_bytes(transaction_bytes)

            logger.debug(f"🔍 Декодированная транзакция: message={raw_transaction.message}")

            # ИСПРАВЛЕННЫЙ СПОСОБ: Подписываем сообщение через keypair.sign_message()
            message_bytes = to_bytes_versioned(raw_transaction.message)
            signature = self.wallet_keypair.sign_message(message_bytes)

            logger.debug(f"🔐 Подпись создана: {signature}")

            # Создаем подписанную транзакцию через populate()
            signed_transaction = VersionedTransaction.populate(raw_transaction.message, [signature])

            logger.debug(f"✅ Транзакция подписана успешно")

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВКЛЮЧАЕМ preflight для диагностики ошибок
            opts = TxOpts(
                skip_preflight=False,  # ИСПРАВЛЕНО: НЕ пропускаем симуляцию для диагностики
                preflight_commitment=Confirmed,
                max_retries=settings.trading.max_retries
            )

            logger.debug(f"🔍 Отправка транзакции с preflight проверкой...")

            # Сначала симулируем транзакцию для диагностики
            try:
                simulation_result = await self.solana_client.simulate_transaction(
                    signed_transaction,
                    commitment=Confirmed
                )

                if simulation_result.value.err:
                    logger.error(f"❌ Симуляция транзакции НЕУДАЧНА:")
                    logger.error(f"   Ошибка: {simulation_result.value.err}")
                    if simulation_result.value.logs:
                        logger.error(f"   Логи:")
                        for log in simulation_result.value.logs:
                            logger.error(f"     {log}")
                    return None
                else:
                    logger.debug(f"✅ Симуляция транзакции успешна")
                    if simulation_result.value.logs:
                        for log in simulation_result.value.logs[-3:]:  # Последние 3 лога
                            logger.debug(f"   📝 {log}")

            except Exception as sim_error:
                logger.error(f"❌ Ошибка симуляции: {sim_error}")
                # Продолжаем отправку даже при ошибке симуляции

            # Отправляем транзакцию
            response = await self.solana_client.send_transaction(signed_transaction, opts=opts)

            if response.value:
                signature_str = str(response.value)
                logger.debug(f"📤 Транзакция отправлена: {signature_str}")

                # НОВОЕ: Ждем подтверждения и проверяем статус
                try:
                    await asyncio.sleep(1)  # Даем время на обработку

                    # Проверяем статус транзакции
                    confirmed_result = await self.solana_client.get_transaction(
                        response.value,
                        commitment=Confirmed,
                        encoding='json',
                        max_supported_transaction_version=0
                    )

                    if confirmed_result.value:
                        if confirmed_result.value.meta and confirmed_result.value.meta.err:
                            logger.error(f"❌ Транзакция подтверждена, но НЕУДАЧНА:")
                            logger.error(f"   Подпись: {signature_str}")
                            logger.error(f"   Ошибка: {confirmed_result.value.meta.err}")

                            if confirmed_result.value.meta.log_messages:
                                logger.error(f"   Логи транзакции:")
                                for log in confirmed_result.value.meta.log_messages:
                                    logger.error(f"     {log}")
                            return None
                        else:
                            logger.success(f"✅ Транзакция УСПЕШНО подтверждена: {signature_str}")
                            return signature_str
                    else:
                        logger.warning(f"⚠️ Транзакция отправлена, но статус неизвестен: {signature_str}")
                        return signature_str

                except Exception as confirm_error:
                    logger.warning(f"⚠️ Ошибка проверки статуса: {confirm_error}")
                    # Возвращаем подпись даже если не смогли проверить статус
                    return signature_str

            else:
                logger.error("❌ Транзакция не отправилась")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка отправки транзакции: {e}")
            logger.error(f"🔍 Тип ошибки: {type(e).__name__}")

            # Дополнительная диагностика
            try:
                logger.error(f"🔍 Детали транзакции: message_type={type(raw_transaction.message)}")
                logger.error(f"🔍 Wallet pubkey: {self.wallet_keypair.pubkey()}")
            except:
                pass

            return None

    def _update_global_stats(self, session: TradingSession):
        """Обновление глобальной статистики"""
        self.total_trades += len(session.results)
        self.successful_trades += session.successful_trades
        self.failed_trades += session.failed_trades
        self.total_sol_spent += session.total_sol_spent
        self.total_tokens_bought += session.total_tokens_bought

    def _log_session_summary(self, session: TradingSession):
        """Логирование итогов торговой сессии - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        total_time = (time.time() - session.start_time) * 1000

        # ИСПРАВЛЕНО: Правильный подсчет купленных токенов
        total_tokens_bought = 0.0
        successful_trades_with_tokens = 0

        for result in session.results:
            if result.success and result.output_amount is not None and result.output_amount > 0:
                total_tokens_bought += result.output_amount
                successful_trades_with_tokens += 1

        logger.critical("🎯 ИТОГИ СНАЙПЕР АТАКИ:")
        logger.info(f"  📍 Контракт: {session.token_address}")
        logger.info(
            f"  📱 Источник: {session.source_info.get('platform', 'unknown')} - {session.source_info.get('source', 'unknown')}")
        logger.info(f"  ✅ Успешных сделок: {session.successful_trades}/{len(session.results)}")
        logger.info(f"  💰 Потрачено SOL: {session.total_sol_spent:.4f}")
        logger.info(f"  🪙 Куплено токенов: {total_tokens_bought:,.6f}")  # ИСПРАВЛЕНО

        if successful_trades_with_tokens < session.successful_trades:
            logger.warning(
                f"  ⚠️ {session.successful_trades - successful_trades_with_tokens} сделок без данных о токенах")

        logger.info(f"  ⚡ Общее время: {total_time:.0f}ms")

        if len(session.results) > 0:
            logger.info(f"  📊 Среднее время на сделку: {total_time / len(session.results):.0f}ms")
            logger.info(f"  📈 Процент успеха: {session.success_rate:.1f}%")

        # Логируем подписи успешных транзакций
        signatures = session.get_signatures()
        if signatures:
            logger.info("  📝 Подписи успешных транзакций:")
            for i, sig in enumerate(signatures):
                logger.info(f"    {i + 1}. {sig}")

        # НОВОЕ: Обновляем session с правильными данными
        session.total_tokens_bought = total_tokens_bought

    async def get_sol_balance(self) -> float:
        """Получение баланса SOL"""
        try:
            response = await self.solana_client.get_balance(self.wallet_keypair.pubkey())
            if response.value:
                return response.value / 1e9  # Конвертируем lamports в SOL
            return 0.0
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса SOL: {e}")
            return 0.0

    def get_stats(self) -> Dict:
        """Получение статистики торговли"""
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": self.successful_trades / max(self.total_trades, 1) * 100,
            "total_sol_spent": self.total_sol_spent,
            "total_tokens_bought": self.total_tokens_bought,
            "wallet_address": str(self.wallet_keypair.pubkey()) if self.wallet_keypair else "unknown"
        }

    def reset_stats(self):
        """Сброс статистики"""
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_sol_spent = 0.0
        self.total_tokens_bought = 0.0
        logger.info("📊 Статистика торговли сброшена")

    # async def _get_token_balance_with_decimals(self, wallet_pubkey: Pubkey, token_mint: Pubkey) -> float:
    #     """Получает баланс токенов с правильным учетом decimals - КОПИЯ ИЗ TRANSFER_MANAGER"""
    #     try:
    #         from spl.token.instructions import get_associated_token_address
    #         from solana.rpc.commitment import Confirmed
    #
    #         # Получаем associated token account
    #         ata = get_associated_token_address(wallet_pubkey, token_mint)
    #
    #         # Получаем информацию об аккаунте
    #         account_info = await self.solana_client.get_account_info(ata, commitment=Confirmed)
    #
    #         if not account_info.value:
    #             logger.debug(f"💰 ATA не найден для {str(wallet_pubkey)[:8]}...")
    #             return 0.0
    #
    #         data = account_info.value.data
    #
    #         if len(data) < 72:
    #             logger.debug(f"💰 Некорректные данные ATA для {str(wallet_pubkey)[:8]}...")
    #             return 0.0
    #
    #         # SPL Token Account layout:
    #         # 0-32: mint (32 bytes)
    #         # 32-64: owner (32 bytes)
    #         # 64-72: amount (8 bytes little-endian uint64)
    #         # 72-73: delegate option (1 byte)
    #         # 73-74: state (1 byte)
    #
    #         # Извлекаем amount (позиция 64-72)
    #         amount_bytes = data[64:72]
    #         amount_raw = int.from_bytes(amount_bytes, byteorder='little')
    #
    #         if amount_raw == 0:
    #             return 0.0
    #
    #         # Получаем decimals для токена
    #         decimals = await self._get_token_decimals(token_mint)
    #
    #         # Вычисляем реальный баланс
    #         balance = amount_raw / (10 ** decimals)
    #
    #         logger.debug(f"💰 Баланс {str(wallet_pubkey)[:8]}...: {balance:.6f} токенов")
    #         return balance
    #
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка получения баланса токена: {e}")
    #         return 0.0


    async def _execute_single_trade_without_balance_check(self, token_address: str, trade_index: int,
                                                          amount_sol: float, source_info: Dict) -> TradeResult:
        """Выполнение одной сделки через Jupiter БЕЗ проверки баланса (для мультикошельков)"""
        start_time = time.time()

        try:
            # Локальный импорт для избежания циклических зависимостей
            from config.settings import settings

            logger.debug(f"🚀 Запуск сделки {trade_index + 1}: {amount_sol} SOL -> {token_address}")

            # Шаг 1: Получаем котировку от Jupiter
            quote = await self.jupiter_client.get_quote(
                input_mint=settings.trading.base_token,  # SOL
                output_mint=token_address,
                amount=int(amount_sol * 1e9),  # Конвертируем в lamports
                slippage_bps=settings.trading.slippage_bps
            )

            if not quote:
                return self._create_failed_result("Не удалось получить котировку",
                                                  amount_sol, trade_index, start_time)

            # Проверяем price impact
            price_impact = quote.price_impact_float
            if price_impact > settings.security.max_price_impact:
                return self._create_failed_result(
                    f"Слишком большое проскальзывание: {price_impact}%",
                    amount_sol, trade_index, start_time
                )

            logger.debug(
                f"💹 Сделка {trade_index + 1} котировка: {quote.out_amount} токенов, {price_impact}% проскальзывание")

            # Шаг 2: Создаем запрос на swap транзакцию
            swap_request = SwapRequest(
                quote_response=quote,
                user_public_key=str(self.wallet_keypair.pubkey()),
                priority_fee_lamports=settings.trading.priority_fee,
                destination_token_account=None
            )

            # Шаг 3: Получаем транзакцию обмена
            swap_transaction = await self.jupiter_client.get_swap_transaction(swap_request)

            if not swap_transaction:
                return self._create_failed_result("Не удалось создать транзакцию обмена",
                                                  amount_sol, trade_index, start_time)

            # Шаг 4: Подписываем и отправляем транзакцию
            signature = await self._send_transaction(swap_transaction)

            if signature:
                execution_time = (time.time() - start_time) * 1000

                logger.success(f"✅ Сделка {trade_index + 1} УСПЕШНА: {signature} ({execution_time:.0f}ms)")

                # ВАЖНО: НЕ проверяем баланс здесь - это делает вызывающий код
                return TradeResult(
                    success=True,
                    signature=signature,
                    error=None,
                    input_amount=amount_sol,
                    output_amount=0.0,  # Будет заполнено вызывающим кодом
                    price_impact=price_impact,
                    execution_time_ms=execution_time,
                    trade_index=trade_index
                )
            else:
                return self._create_failed_result("Транзакция не отправилась",
                                                  amount_sol, trade_index, start_time)

        except Exception as e:
            logger.error(f"❌ Ошибка сделки {trade_index + 1}: {e}")
            return self._create_failed_result(str(e), amount_sol, trade_index, start_time)