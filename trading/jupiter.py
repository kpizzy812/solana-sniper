import asyncio
import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

import aiohttp
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
import base64
import base58
from loguru import logger

from config.settings import settings


@dataclass
class TradeResult:
    """Результат отдельной сделки"""
    success: bool
    signature: Optional[str]
    error: Optional[str]
    input_amount: float
    output_amount: Optional[float]
    price_impact: Optional[float]
    execution_time_ms: float
    trade_index: int
    gas_used: Optional[int] = None


@dataclass
class QuoteResponse:
    """Ответ от Jupiter API с котировкой"""
    input_mint: str
    output_mint: str
    in_amount: str
    out_amount: str
    price_impact_pct: str
    route_plan: List[Dict]
    other_amount_threshold: Optional[str] = None
    swap_mode: Optional[str] = None


@dataclass
class PoolInfo:
    """Информация о ликвидности пула"""
    liquidity_sol: float
    price: float
    market_cap: float
    volume_24h: float
    holders_count: int


class UltraFastJupiterTrader:
    """Ультра-быстрая торговая система Jupiter"""

    def __init__(self):
        self.solana_client: Optional[AsyncClient] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.wallet_keypair: Optional[Keypair] = None

        # Статистика торговли
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_sol_spent = 0.0
        self.total_tokens_bought = 0.0

        # Кэш для быстрого доступа
        self.quote_cache = {}
        self.pool_cache = {}

        self.setup_wallet()

    def setup_wallet(self):
        """Настройка кошелька из приватного ключа"""
        try:
            if settings.solana.private_key:
                # Декодируем base58 приватный ключ
                private_key_bytes = base58.b58decode(settings.solana.private_key)
                self.wallet_keypair = Keypair.from_bytes(private_key_bytes)
                logger.info(f"💰 Кошелек загружен: {self.wallet_keypair.pubkey()}")
            else:
                logger.error("❌ Приватный ключ не настроен")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки кошелька: {e}")

    async def start(self):
        """Инициализация торговой системы"""
        try:
            # Настройка Solana RPC клиента
            self.solana_client = AsyncClient(
                endpoint=settings.solana.rpc_url,
                commitment=Confirmed
            )

            # Настройка HTTP сессии для Jupiter API
            timeout = aiohttp.ClientTimeout(total=settings.jupiter.timeout)
            connector = aiohttp.TCPConnector(
                limit=settings.jupiter.max_concurrent_requests,
                limit_per_host=settings.jupiter.max_concurrent_requests
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )

            # Тестируем соединения
            health = await self.health_check()
            if health['status'] != 'healthy':
                raise Exception(f"Проблемы с подключением: {health}")

            logger.success("✅ Jupiter трейдер инициализирован успешно")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Jupiter трейдера: {e}")
            return False

    async def stop(self):
        """Остановка и очистка ресурсов"""
        if self.session:
            await self.session.close()
        if self.solana_client:
            await self.solana_client.close()
        logger.info("🛑 Jupiter трейдер остановлен")

    async def execute_sniper_trades(self, token_address: str, source_info: Dict) -> List[TradeResult]:
        """
        Выполнение снайперских сделок
        Поддерживает как одну покупку, так и множественные
        """
        logger.critical(f"🎯 СНАЙПЕР АТАКА НА ТОКЕН: {token_address}")

        # Определяем стратегию покупки
        num_trades = settings.trading.num_purchases
        amount_per_trade = settings.trading.trade_amount_sol

        # Проверяем настройки для умного распределения
        if settings.trading.smart_split and num_trades > 1:
            # Умное распределение размеров для уменьшения проскальзывания
            amounts = self.calculate_smart_amounts(
                total_amount=num_trades * amount_per_trade,
                num_trades=num_trades
            )
        else:
            amounts = [amount_per_trade] * num_trades

        logger.info(f"📊 Выполняется {num_trades} сделок с размерами: {amounts}")

        start_time = time.time()

        # Предварительная проверка безопасности токена
        if not await self.security_check(token_address):
            logger.error("❌ Токен не прошел проверку безопасности")
            return []

        # Создаем задачи для параллельного выполнения
        if settings.trading.concurrent_trades:
            # Параллельное выполнение всех сделок
            trade_tasks = []
            for i in range(num_trades):
                task = asyncio.create_task(
                    self.execute_single_trade(token_address, i, amounts[i], source_info)
                )
                trade_tasks.append(task)

            # Выполняем все сделки одновременно
            results = await asyncio.gather(*trade_tasks, return_exceptions=True)
        else:
            # Последовательное выполнение
            results = []
            for i in range(num_trades):
                result = await self.execute_single_trade(token_address, i, amounts[i], source_info)
                results.append(result)

        # Обработка результатов
        trade_results = []
        successful_count = 0
        total_tokens_bought = 0
        total_sol_spent = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Сделка {i + 1} упала с исключением: {result}")
                trade_results.append(TradeResult(
                    success=False,
                    signature=None,
                    error=str(result),
                    input_amount=amounts[i] if i < len(amounts) else amount_per_trade,
                    output_amount=None,
                    price_impact=None,
                    execution_time_ms=0,
                    trade_index=i
                ))
            else:
                trade_results.append(result)
                if result.success:
                    successful_count += 1
                    total_sol_spent += result.input_amount
                    if result.output_amount:
                        total_tokens_bought += result.output_amount

        total_time = (time.time() - start_time) * 1000

        # Логируем итоги
        self.log_sniper_summary(
            token_address, successful_count, num_trades,
            total_sol_spent, total_tokens_bought, total_time, source_info
        )

        # Обновляем статистику
        self.total_trades += len(trade_results)
        self.successful_trades += successful_count
        self.failed_trades += (len(trade_results) - successful_count)
        self.total_sol_spent += total_sol_spent
        self.total_tokens_bought += total_tokens_bought

        return trade_results

    def calculate_smart_amounts(self, total_amount: float, num_trades: int) -> List[float]:
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

    async def execute_single_trade(self, token_address: str, trade_index: int,
                                   amount_sol: float, source_info: Dict) -> TradeResult:
        """Выполнение одной сделки через Jupiter"""
        start_time = time.time()

        try:
            logger.debug(f"🚀 Запуск сделки {trade_index + 1}: {amount_sol} SOL -> {token_address}")

            # Шаг 1: Получаем котировку от Jupiter
            quote = await self.get_quote(
                input_mint=settings.trading.base_token,  # SOL
                output_mint=token_address,
                amount=int(amount_sol * 1e9),  # Конвертируем в lamports
                slippage_bps=settings.trading.slippage_bps
            )

            if not quote:
                return self.create_failed_result("Не удалось получить котировку",
                                                 amount_sol, trade_index, start_time)

            # Проверяем price impact
            price_impact = float(quote.price_impact_pct)
            if price_impact > settings.security.max_price_impact:
                return self.create_failed_result(
                    f"Слишком большое проскальзывание: {price_impact}%",
                    amount_sol, trade_index, start_time
                )

            logger.debug(
                f"💹 Сделка {trade_index + 1} котировка: {quote.out_amount} токенов, {price_impact}% проскальзывание")

            # Шаг 2: Получаем транзакцию обмена
            swap_transaction = await self.get_swap_transaction(quote)

            if not swap_transaction:
                return self.create_failed_result("Не удалось создать транзакцию обмена",
                                                 amount_sol, trade_index, start_time)

            # Шаг 3: Подписываем и отправляем транзакцию
            signature = await self.send_transaction(swap_transaction)

            if signature:
                output_amount = float(quote.out_amount) / 1e9  # Конвертируем из lamports
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
                return self.create_failed_result("Транзакция не отправилась",
                                                 amount_sol, trade_index, start_time)

        except Exception as e:
            logger.error(f"❌ Ошибка сделки {trade_index + 1}: {e}")
            return self.create_failed_result(str(e), amount_sol, trade_index, start_time)

    def create_failed_result(self, error: str, amount: float, trade_index: int, start_time: float) -> TradeResult:
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

    async def get_quote(self, input_mint: str, output_mint: str, amount: int,
                        slippage_bps: int) -> Optional[QuoteResponse]:
        """Получение котировки от Jupiter API"""
        try:
            # Проверяем кэш для быстрого доступа
            cache_key = f"{input_mint}:{output_mint}:{amount}:{slippage_bps}"
            if cache_key in self.quote_cache:
                cached_time, quote = self.quote_cache[cache_key]
                if time.time() - cached_time < 2:  # Кэш на 2 секунды
                    return quote

            url = f"{settings.jupiter.api_url}/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': False,
                'asLegacyTransaction': False,
                'platformFeeBps': 0,
                'maxAccounts': 64
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    quote = QuoteResponse(
                        input_mint=data['inputMint'],
                        output_mint=data['outputMint'],
                        in_amount=data['inAmount'],
                        out_amount=data['outAmount'],
                        price_impact_pct=data.get('priceImpactPct', '0'),
                        route_plan=data.get('routePlan', []),
                        other_amount_threshold=data.get('otherAmountThreshold'),
                        swap_mode=data.get('swapMode')
                    )

                    # Кэшируем результат
                    self.quote_cache[cache_key] = (time.time(), quote)

                    return quote
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка Quote API {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения котировки: {e}")
            return None

    async def get_swap_transaction(self, quote: QuoteResponse) -> Optional[str]:
        """Получение транзакции обмена от Jupiter API"""
        try:
            url = f"{settings.jupiter.swap_api_url}"
            payload = {
                'quoteResponse': {
                    'inputMint': quote.input_mint,
                    'outputMint': quote.output_mint,
                    'inAmount': quote.in_amount,
                    'outAmount': quote.out_amount,
                    'priceImpactPct': quote.price_impact_pct,
                    'routePlan': quote.route_plan
                },
                'userPublicKey': str(self.wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'useSharedAccounts': True,
                'feeAccount': None,
                'prioritizationFeeLamports': settings.trading.priority_fee,
                'asLegacyTransaction': False,
                'useTokenLedger': False,
                'destinationTokenAccount': None
            }

            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('swapTransaction')
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка Swap API {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения транзакции обмена: {e}")
            return None

    async def send_transaction(self, swap_transaction_b64: str) -> Optional[str]:
        """Подпись и отправка транзакции в Solana"""
        try:
            # Декодируем транзакцию
            transaction_bytes = base64.b64decode(swap_transaction_b64)
            transaction = VersionedTransaction.from_bytes(transaction_bytes)

            # Подписываем транзакцию
            transaction.sign([self.wallet_keypair])

            # Отправляем с высоким приоритетом
            opts = TxOpts(
                skip_preflight=True,  # Пропускаем симуляцию для скорости
                preflight_commitment=Confirmed,
                max_retries=settings.trading.max_retries
            )

            response = await self.solana_client.send_raw_transaction(
                bytes(transaction), opts=opts
            )

            if response.value:
                signature = str(response.value)
                logger.debug(f"📤 Транзакция отправлена: {signature}")
                return signature
            else:
                logger.error("❌ Транзакция не отправилась")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка отправки транзакции: {e}")
            return None

    async def security_check(self, token_address: str) -> bool:
        """Быстрая проверка безопасности токена"""
        try:
            if not settings.security.enable_security_checks:
                return True

            # Проверяем ликвидность пула
            pool_info = await self.get_pool_info(token_address)
            if not pool_info:
                logger.warning(f"⚠️ Не удалось получить информацию о пуле для {token_address}")
                return False

            if pool_info.liquidity_sol < settings.security.min_liquidity_sol:
                logger.warning(
                    f"⚠️ Недостаточная ликвидность: {pool_info.liquidity_sol} SOL < {settings.security.min_liquidity_sol} SOL")
                return False

            logger.info(f"✅ Проверка безопасности пройдена: {pool_info.liquidity_sol} SOL ликвидности")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка проверки безопасности: {e}")
            return False

    async def get_pool_info(self, token_address: str) -> Optional[PoolInfo]:
        """Получение информации о ликвидности пула"""
        try:
            # Здесь должна быть логика получения информации о пуле
            # Можно использовать Jupiter API или прямые запросы к DEX

            # Заглушка - в реальности нужно реализовать
            return PoolInfo(
                liquidity_sol=10.0,  # Пример
                price=0.001,
                market_cap=1000000,
                volume_24h=50000,
                holders_count=100
            )

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о пуле: {e}")
            return None

    def log_sniper_summary(self, token_address: str, successful: int, total: int,
                           sol_spent: float, tokens_bought: float, total_time: float, source_info: Dict):
        """Логирование итогов снайперской атаки"""
        logger.critical("🎯 ИТОГИ СНАЙПЕР АТАКИ:")
        logger.info(f"  📍 Контракт: {token_address}")
        logger.info(f"  📱 Источник: {source_info.get('platform', 'unknown')} - {source_info.get('source', 'unknown')}")
        logger.info(f"  ✅ Успешных сделок: {successful}/{total}")
        logger.info(f"  💰 Потрачено SOL: {sol_spent:.4f}")
        logger.info(f"  🪙 Куплено токенов: {tokens_bought:,.0f}")
        logger.info(f"  ⚡ Общее время: {total_time:.0f}ms")

        if total > 0:
            logger.info(f"  📊 Среднее время на сделку: {total_time / total:.0f}ms")
            success_rate = (successful / total) * 100
            logger.info(f"  📈 Процент успеха: {success_rate:.1f}%")

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

    async def health_check(self) -> Dict:
        """Проверка здоровья торговой системы"""
        try:
            # Проверяем соединение с Solana (используем get_version вместо get_health)
            try:
                response = await self.solana_client.get_version()
                solana_healthy = response.value is not None
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к Solana RPC: {e}")
                solana_healthy = False

            # Проверяем Jupiter API
            try:
                async with self.session.get(
                        f"{settings.jupiter.api_url}/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000&slippageBps=50") as resp:
                    jupiter_healthy = resp.status == 200
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к Jupiter API: {e}")
                jupiter_healthy = False

            # Проверяем баланс кошелька
            try:
                sol_balance = await self.get_sol_balance()
            except Exception as e:
                logger.error(f"❌ Ошибка получения баланса: {e}")
                sol_balance = 0.0

            status = "healthy" if solana_healthy and jupiter_healthy else "degraded"

            # Логируем детали для отладки
            if not solana_healthy:
                logger.warning("⚠️ Solana RPC недоступен")
            if not jupiter_healthy:
                logger.warning("⚠️ Jupiter API недоступен")

            return {
                "status": status,
                "solana_rpc": "healthy" if solana_healthy else "error",
                "jupiter_api": "healthy" if jupiter_healthy else "error",
                "wallet_address": str(self.wallet_keypair.pubkey()) if self.wallet_keypair else "unknown",
                "sol_balance": sol_balance,
                "stats": {
                    "total_trades": self.total_trades,
                    "successful_trades": self.successful_trades,
                    "failed_trades": self.failed_trades,
                    "success_rate": self.successful_trades / max(self.total_trades, 1) * 100,
                    "total_sol_spent": self.total_sol_spent,
                    "total_tokens_bought": self.total_tokens_bought
                }
            }

        except Exception as e:
            logger.error(f"❌ Ошибка health check: {e}")
            return {"status": "error", "message": str(e)}


# Глобальный экземпляр трейдера
jupiter_trader = UltraFastJupiterTrader()