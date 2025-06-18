import asyncio
import time
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from config.multi_wallet import MultiWalletConfig, MultiWalletInfo
from trading.jupiter.models import TradeResult


@dataclass
class MultiWalletTradeResult:
    """Результат торговли с множественными кошельками"""
    token_address: str
    total_trades: int
    successful_trades: int
    failed_trades: int
    total_sol_spent: float
    total_tokens_bought: float
    execution_time_ms: float
    wallet_results: List[Tuple[str, TradeResult]]  # (wallet_address, result)
    delayed_start: bool = False

    @property
    def success_rate(self) -> float:
        """Процент успешных сделок"""
        if self.total_trades == 0:
            return 0.0
        return (self.successful_trades / self.total_trades) * 100


class MultiWalletManager:
    """Менеджер торговли с множественными кошельками"""

    def __init__(self, solana_client: AsyncClient, jupiter_trader):
        self.solana_client = solana_client
        self.jupiter_trader = jupiter_trader
        self.config = MultiWalletConfig()

        # Статистика
        self.total_sessions = 0
        self.total_successful_trades = 0
        self.total_failed_trades = 0

        logger.info(f"🎭 MultiWallet Manager: {len(self.config.wallets)} кошельков загружено")

    async def start(self) -> bool:
        """Инициализация менеджера"""
        if not self.config.is_enabled():
            logger.info("📱 Система множественных кошельков отключена - используется обычный режим")
            return True

        logger.info("🎭 Запуск системы множественных кошельков...")

        # Проверяем балансы всех кошельков
        await self.update_all_balances()

        # Проверяем готовность к торговле
        available_wallets = self.config.get_available_wallets()
        total_balance = self.config.get_total_available_balance()

        if len(available_wallets) == 0:
            logger.error("❌ Нет кошельков с достаточным балансом для торговли")
            return False

        logger.success(f"✅ Система множественных кошельков готова:")
        logger.info(f"   💰 Доступные кошельки: {len(available_wallets)}/{len(self.config.wallets)}")
        logger.info(f"   💎 Общий баланс: {total_balance:.4f} SOL")
        logger.info(f"   ⏱️ Начальная задержка: {self.config.initial_delay_seconds}s")
        logger.info(f"   🎲 Рандомизация: {self.config.randomize_amounts}")

        return True

    async def execute_multi_wallet_trades(self, token_address: str,
                                          base_trade_amount: float,
                                          num_trades: int,
                                          source_info: Dict) -> MultiWalletTradeResult:
        """
        Выполнение торговли с использованием множественных кошельков

        Args:
            token_address: Адрес токена для покупки
            base_trade_amount: Базовая сумма одной сделки
            num_trades: Количество сделок
            source_info: Информация об источнике сигнала
        """
        start_time = time.time()

        if not self.config.is_enabled():
            # Fallback к обычной торговле
            logger.warning("⚠️ Множественные кошельки отключены, используем обычный режим")
            return await self._fallback_to_single_wallet(
                token_address, base_trade_amount, num_trades, source_info
            )

        logger.critical(f"🎭 ЗАПУСК МУЛЬТИ-КОШЕЛЬКОВОГО СНАЙПИНГА!")
        logger.critical(f"🎯 Токен: {token_address}")
        logger.critical(f"💰 План: {num_trades} сделок по ~{base_trade_amount} SOL")

        # ЗАДЕРЖКА ПЕРЕД НАЧАЛОМ ТОРГОВЛИ
        if self.config.initial_delay_seconds > 0:
            logger.warning(f"⏱️ Задержка перед торговлей: {self.config.initial_delay_seconds} секунд...")
            await asyncio.sleep(self.config.initial_delay_seconds)
            logger.critical("🚀 ЗАДЕРЖКА ЗАВЕРШЕНА - НАЧИНАЕМ ТОРГОВЛЮ!")

        # Обновляем балансы перед торговлей
        await self.update_all_balances()

        # Планируем сделки по кошелькам
        trade_plan = self._create_trade_plan(base_trade_amount, num_trades)

        if not trade_plan:
            logger.error("❌ Не удалось создать план торговли - недостаточно средств")
            return self._create_empty_result(token_address, start_time)

        logger.info(f"📋 План торговли: {len(trade_plan)} сделок распределены по кошелькам")

        # Выполняем торговлю
        wallet_results = await self._execute_trade_plan(token_address, trade_plan, source_info)

        # Подсчитываем результаты
        result = self._compile_results(token_address, wallet_results, start_time, True)

        # Обновляем статистику
        self.total_sessions += 1
        self.total_successful_trades += result.successful_trades
        self.total_failed_trades += result.failed_trades

        # Логируем итоги
        self._log_multi_wallet_summary(result)

        return result

    def _create_trade_plan(self, base_amount: float, num_trades: int) -> List[Tuple[MultiWalletInfo, float]]:
        """
        Создание плана распределения сделок по кошелькам

        Returns:
            List[Tuple[MultiWalletInfo, float]]: Список (кошелек, сумма_сделки)
        """
        trade_plan = []
        used_wallets = set()

        for i in range(num_trades):
            # Рандомизируем сумму сделки
            trade_amount = self.config.randomize_trade_amount(base_amount)

            # Выбираем кошелек для сделки
            wallet = self.config.select_wallet_for_trade(trade_amount)

            if not wallet:
                logger.warning(f"⚠️ Не найден подходящий кошелек для сделки {i + 1} на {trade_amount} SOL")
                continue

            # Проверяем не превышен ли лимит для этого кошелька
            if wallet.address in used_wallets:
                wallet_usage = sum(1 for w, _ in trade_plan if w.address == wallet.address)
                if wallet_usage >= self.config.max_trades_per_wallet:
                    logger.debug(f"⏭️ Кошелек {wallet.address[:8]}... достиг лимита сделок")
                    continue

            trade_plan.append((wallet, trade_amount))
            used_wallets.add(wallet.address)

            logger.debug(f"📝 Сделка {i + 1}: {trade_amount} SOL через {wallet.address[:8]}...")

        return trade_plan

    async def _execute_trade_plan(self, token_address: str,
                                  trade_plan: List[Tuple[MultiWalletInfo, float]],
                                  source_info: Dict) -> List[Tuple[str, TradeResult]]:
        """Выполнение плана торговли"""
        wallet_results = []

        for i, (wallet, amount) in enumerate(trade_plan):
            try:
                logger.info(f"🔄 Сделка {i + 1}/{len(trade_plan)}: {amount} SOL через {wallet.address[:8]}...")

                # Временно заменяем кошелек в Jupiter trader
                original_keypair = self.jupiter_trader.executor.wallet_keypair
                self.jupiter_trader.executor.wallet_keypair = wallet.keypair

                # Выполняем одну сделку
                results = await self.jupiter_trader.executor._execute_single_trade(
                    token_address=token_address,
                    trade_index=i,
                    amount_sol=amount,
                    source_info=source_info
                )

                # Восстанавливаем оригинальный кошелек
                self.jupiter_trader.executor.wallet_keypair = original_keypair

                # Обновляем информацию о кошельке
                if results.success:
                    wallet.mark_used(amount)

                wallet_results.append((wallet.address, results))

                # Задержка между сделками (кроме последней)
                if i < len(trade_plan) - 1:
                    delay = self.config.get_inter_trade_delay()
                    logger.debug(f"⏱️ Задержка перед следующей сделкой: {delay:.1f}s")
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"❌ Ошибка сделки {i + 1} через {wallet.address[:8]}...: {e}")

                # Создаем результат ошибки
                error_result = TradeResult(
                    success=False,
                    signature=None,
                    error=str(e),
                    input_amount=amount,
                    output_amount=None,
                    price_impact=None,
                    execution_time_ms=0,
                    trade_index=i
                )

                wallet_results.append((wallet.address, error_result))

        return wallet_results

    async def _fallback_to_single_wallet(self, token_address: str, base_amount: float,
                                         num_trades: int, source_info: Dict) -> MultiWalletTradeResult:
        """Fallback к обычной торговле одним кошельком"""
        start_time = time.time()

        # Используем стандартную торговлю Jupiter
        results = await self.jupiter_trader.execute_sniper_trades(token_address, source_info)

        # Конвертируем в формат MultiWalletTradeResult
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_sol = sum(r.input_amount for r in results if r.success)
        total_tokens = sum(r.output_amount or 0 for r in results if r.success)

        wallet_results = [(str(self.jupiter_trader.executor.wallet_keypair.pubkey()), r) for r in results]

        return MultiWalletTradeResult(
            token_address=token_address,
            total_trades=len(results),
            successful_trades=successful,
            failed_trades=failed,
            total_sol_spent=total_sol,
            total_tokens_bought=total_tokens,
            execution_time_ms=(time.time() - start_time) * 1000,
            wallet_results=wallet_results,
            delayed_start=False
        )

    def _compile_results(self, token_address: str, wallet_results: List[Tuple[str, TradeResult]],
                         start_time: float, delayed_start: bool) -> MultiWalletTradeResult:
        """Компиляция результатов торговли"""
        successful = sum(1 for _, r in wallet_results if r.success)
        failed = len(wallet_results) - successful

        total_sol = sum(r.input_amount for _, r in wallet_results if r.success)
        total_tokens = sum(r.output_amount or 0 for _, r in wallet_results if r.success)

        return MultiWalletTradeResult(
            token_address=token_address,
            total_trades=len(wallet_results),
            successful_trades=successful,
            failed_trades=failed,
            total_sol_spent=total_sol,
            total_tokens_bought=total_tokens,
            execution_time_ms=(time.time() - start_time) * 1000,
            wallet_results=wallet_results,
            delayed_start=delayed_start
        )

    def _create_empty_result(self, token_address: str, start_time: float) -> MultiWalletTradeResult:
        """Создание пустого результата при ошибке"""
        return MultiWalletTradeResult(
            token_address=token_address,
            total_trades=0,
            successful_trades=0,
            failed_trades=0,
            total_sol_spent=0.0,
            total_tokens_bought=0.0,
            execution_time_ms=(time.time() - start_time) * 1000,
            wallet_results=[],
            delayed_start=False
        )

    def _log_multi_wallet_summary(self, result: MultiWalletTradeResult):
        """Логирование итогов мульти-кошелькового снайпинга"""
        logger.critical("🎭 ИТОГИ МУЛЬТИ-КОШЕЛЬКОВОГО СНАЙПИНГА:")
        logger.info(f"  🎯 Контракт: {result.token_address}")
        logger.info(f"  ✅ Успешных сделок: {result.successful_trades}/{result.total_trades}")
        logger.info(f"  💰 Потрачено SOL: {result.total_sol_spent:.4f}")
        logger.info(f"  🪙 Куплено токенов: {result.total_tokens_bought:,.0f}")
        logger.info(f"  ⚡ Общее время: {result.execution_time_ms:.0f}ms")
        logger.info(f"  📈 Процент успеха: {result.success_rate:.1f}%")

        if result.delayed_start:
            logger.info(f"  ⏱️ Включена задержка: {self.config.initial_delay_seconds}s")

        # Логируем кошельки участвовавшие в торговле
        unique_wallets = set(addr for addr, _ in result.wallet_results)
        logger.info(f"  🎭 Использовано кошельков: {len(unique_wallets)}")

        # Подписи успешных транзакций
        signatures = [r.signature for _, r in result.wallet_results if r.success and r.signature]
        if signatures:
            logger.info("  📝 Подписи успешных транзакций:")
            for i, sig in enumerate(signatures):
                logger.info(f"    {i + 1}. {sig}")

    async def update_all_balances(self):
        """Обновление балансов всех кошельков"""
        if not self.config.wallets:
            return

        logger.debug("🔄 Обновление балансов множественных кошельков...")

        # Получаем балансы параллельно
        balance_tasks = []
        for wallet in self.config.wallets:
            task = asyncio.create_task(self._get_wallet_balance(wallet))
            balance_tasks.append(task)

        results = await asyncio.gather(*balance_tasks, return_exceptions=True)

        # Обновляем балансы
        for wallet, result in zip(self.config.wallets, results):
            if isinstance(result, Exception):
                logger.warning(f"⚠️ Ошибка получения баланса {wallet.address[:8]}...: {result}")
            else:
                wallet.update_balance(result)

        total_balance = sum(w.balance_sol for w in self.config.wallets)
        available_balance = sum(w.available_balance for w in self.config.wallets)

        logger.debug(f"💰 Обновлены балансы: {total_balance:.4f} SOL общий, {available_balance:.4f} SOL доступно")

    async def _get_wallet_balance(self, wallet: MultiWalletInfo) -> float:
        """Получение баланса конкретного кошелька"""
        try:
            response = await self.solana_client.get_balance(wallet.keypair.pubkey())
            if response.value:
                return response.value / 1e9  # Конвертируем lamports в SOL
            return 0.0
        except Exception as e:
            logger.debug(f"Ошибка получения баланса {wallet.address[:8]}...: {e}")
            return 0.0

    def get_stats(self) -> Dict:
        """Получение статистики менеджера"""
        base_stats = {
            "multi_wallet_enabled": self.config.is_enabled(),
            "total_sessions": self.total_sessions,
            "total_successful_trades": self.total_successful_trades,
            "total_failed_trades": self.total_failed_trades
        }

        if self.config.is_enabled():
            base_stats.update(self.config.get_stats())

        return base_stats

    async def health_check(self) -> Dict:
        """Проверка здоровья системы множественных кошельков"""
        if not self.config.is_enabled():
            return {"status": "disabled", "message": "Множественные кошельки отключены"}

        try:
            # Обновляем балансы
            await self.update_all_balances()

            # Проверяем доступность кошельков
            available_wallets = self.config.get_available_wallets()
            total_balance = self.config.get_total_available_balance()

            status = "healthy" if len(available_wallets) > 0 else "degraded"

            return {
                "status": status,
                "total_wallets": len(self.config.wallets),
                "available_wallets": len(available_wallets),
                "total_balance_sol": total_balance,
                "min_balance_threshold": self.config.min_balance,
                "ready_for_trading": len(available_wallets) > 0
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}