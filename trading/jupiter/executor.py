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
        """Выполнение одной сделки через Jupiter"""
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
                priority_fee_lamports=settings.trading.priority_fee
            )

            # Шаг 3: Получаем транзакцию обмена
            swap_transaction = await self.jupiter_client.get_swap_transaction(swap_request)

            if not swap_transaction:
                return self._create_failed_result("Не удалось создать транзакцию обмена",
                                                  amount_sol, trade_index, start_time)

            # Шаг 4: Подписываем и отправляем транзакцию
            signature = await self._send_transaction(swap_transaction)

            if signature:
                output_amount = quote.out_amount_tokens
                execution_time = (time.time() - start_time) * 1000

                logger.success(f"✅ Сделка {trade_index + 1} УСПЕШНА: {signature} ({execution_time:.0f}ms)")

                return TradeResult(
                    success=True,
                    signature=signature,
                    error=None,
                    input_amount=amount_sol,
                    output_amount=output_amount,
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
        """Подпись и отправка транзакции в Solana - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ SOLDERS 0.26.0"""
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

            # Отправляем с высоким приоритетом
            opts = TxOpts(
                skip_preflight=True,  # Пропускаем симуляцию для скорости
                preflight_commitment=Confirmed,
                max_retries=settings.trading.max_retries
            )

            response = await self.solana_client.send_transaction(signed_transaction, opts=opts)

            if response.value:
                signature_str = str(response.value)
                logger.debug(f"📤 Транзакция отправлена: {signature_str}")
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
        """Логирование итогов торговой сессии"""
        total_time = (time.time() - session.start_time) * 1000

        logger.critical("🎯 ИТОГИ СНАЙПЕР АТАКИ:")
        logger.info(f"  📍 Контракт: {session.token_address}")
        logger.info(f"  📱 Источник: {session.source_info.get('platform', 'unknown')} - {session.source_info.get('source', 'unknown')}")
        logger.info(f"  ✅ Успешных сделок: {session.successful_trades}/{len(session.results)}")
        logger.info(f"  💰 Потрачено SOL: {session.total_sol_spent:.4f}")
        logger.info(f"  🪙 Куплено токенов: {session.total_tokens_bought:,.0f}")
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