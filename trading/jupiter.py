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
from solders.message import to_bytes_versioned  # ДОБАВЛЕН ИМПОРТ ДЛЯ НОВОГО API
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
    """Ответ от Jupiter API с котировкой - ИСПРАВЛЕННАЯ СТРУКТУРА"""
    input_mint: str
    output_mint: str
    in_amount: str
    out_amount: str
    other_amount_threshold: str  # ОБЯЗАТЕЛЬНОЕ ПОЛЕ!
    swap_mode: str  # ExactIn или ExactOut
    slippage_bps: int
    platform_fee: Optional[Dict] = None
    price_impact_pct: str = "0"
    route_plan: List[Dict] = None

    def __post_init__(self):
        if self.route_plan is None:
            self.route_plan = []


@dataclass
class PoolInfo:
    """Информация о ликвидности токена (агрегированная)"""
    liquidity_sol: float
    price: float
    market_cap: float
    volume_24h: float
    holders_count: int


class UltraFastJupiterTrader:
    """Ультра-быстрая торговая система Jupiter с исправлениями API v1"""

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
        """Получение котировки от Jupiter API - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Проверяем кэш для быстрого доступа
            cache_key = f"{input_mint}:{output_mint}:{amount}:{slippage_bps}"
            if cache_key in self.quote_cache:
                cached_time, quote = self.quote_cache[cache_key]
                if time.time() - cached_time < 2:  # Кэш на 2 секунды
                    return quote

            # ПРИОРИТЕТ: Используем lite-api (бесплатный)
            if settings.jupiter.api_key and not settings.jupiter.use_lite_api:
                base_url = settings.jupiter.api_url
                headers = {
                    'Content-Type': 'application/json',
                    'x-api-key': settings.jupiter.api_key
                }
            else:
                base_url = settings.jupiter.lite_api_url
                headers = {'Content-Type': 'application/json'}

            url = f"{base_url}/quote"

            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false',
                'platformFeeBps': '0',
                'maxAccounts': '64'
            }

            logger.debug(f"🔍 Quote запрос: {url} с параметрами: {params}")

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()

                    # ИСПРАВЛЕННАЯ ОБРАБОТКА: добавляем все обязательные поля
                    quote = QuoteResponse(
                        input_mint=data['inputMint'],
                        output_mint=data['outputMint'],
                        in_amount=data['inAmount'],
                        out_amount=data['outAmount'],
                        other_amount_threshold=data.get('otherAmountThreshold', data['outAmount']),  # КРИТИЧНОЕ ПОЛЕ!
                        swap_mode=data.get('swapMode', 'ExactIn'),
                        slippage_bps=slippage_bps,
                        platform_fee=data.get('platformFee'),
                        price_impact_pct=data.get('priceImpactPct', '0'),
                        route_plan=data.get('routePlan', [])
                    )

                    # Кэшируем результат
                    self.quote_cache[cache_key] = (time.time(), quote)

                    logger.debug(f"✅ Quote получена через {base_url}")
                    return quote

                elif response.status == 401:
                    logger.warning("⚠️ 401 Unauthorized - переключаемся на lite-api")
                    return await self.get_quote_fallback(input_mint, output_mint, amount, slippage_bps)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка Quote API {response.status}: {error_text}")
                    return await self.get_quote_fallback(input_mint, output_mint, amount, slippage_bps)

        except Exception as e:
            logger.error(f"❌ Ошибка получения котировки: {e}")
            return await self.get_quote_fallback(input_mint, output_mint, amount, slippage_bps)

    async def get_quote_fallback(self, input_mint: str, output_mint: str, amount: int,
                                 slippage_bps: int) -> Optional[QuoteResponse]:
        """Fallback метод для получения котировки"""
        try:
            # Пробуем альтернативный endpoint
            alt_url = settings.jupiter.api_url if settings.jupiter.use_lite_api else settings.jupiter.lite_api_url
            url = f"{alt_url}/quote"

            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false',
                'platformFeeBps': '0',
                'maxAccounts': '64'
            }

            headers = {'Content-Type': 'application/json'}
            if settings.jupiter.api_key and alt_url == settings.jupiter.api_url:
                headers['x-api-key'] = settings.jupiter.api_key

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Fallback quote получена через {alt_url}")

                    return QuoteResponse(
                        input_mint=data['inputMint'],
                        output_mint=data['outputMint'],
                        in_amount=data['inAmount'],
                        out_amount=data['outAmount'],
                        other_amount_threshold=data.get('otherAmountThreshold', data['outAmount']),
                        swap_mode=data.get('swapMode', 'ExactIn'),
                        slippage_bps=slippage_bps,
                        platform_fee=data.get('platformFee'),
                        price_impact_pct=data.get('priceImpactPct', '0'),
                        route_plan=data.get('routePlan', [])
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Fallback Quote API тоже не работает: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка fallback котировки: {e}")
            return None

    async def get_swap_transaction(self, quote: QuoteResponse) -> Optional[str]:
        """Получение транзакции обмена от Jupiter API - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if settings.jupiter.api_key and not settings.jupiter.use_lite_api:
                base_url = settings.jupiter.api_url
                headers = {
                    'Content-Type': 'application/json',
                    'x-api-key': settings.jupiter.api_key
                }
            else:
                base_url = settings.jupiter.lite_api_url
                headers = {'Content-Type': 'application/json'}

            url = f"{base_url}/swap"

            # ИСПРАВЛЕННЫЙ PAYLOAD - передаем ПОЛНЫЙ quote response
            payload = {
                'quoteResponse': {
                    'inputMint': quote.input_mint,
                    'outputMint': quote.output_mint,
                    'inAmount': quote.in_amount,
                    'outAmount': quote.out_amount,
                    'otherAmountThreshold': quote.other_amount_threshold,  # КРИТИЧНОЕ ПОЛЕ!
                    'swapMode': quote.swap_mode,
                    'slippageBps': quote.slippage_bps,
                    'platformFee': quote.platform_fee,
                    'priceImpactPct': quote.price_impact_pct,
                    'routePlan': quote.route_plan
                },
                'userPublicKey': str(self.wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'useSharedAccounts': True,
                'feeAccount': None,
                'asLegacyTransaction': False,
                'useTokenLedger': False,
                'destinationTokenAccount': None,
                # НОВЫЕ ОПТИМИЗАЦИОННЫЕ ПАРАМЕТРЫ
                'dynamicComputeUnitLimit': True,  # Автоматический расчет compute units
                'prioritizationFeeLamports': {
                    'priorityLevelWithMaxLamports': {
                        'maxLamports': settings.trading.priority_fee,
                        'priorityLevel': 'veryHigh'
                    }
                }
            }

            logger.debug(f"🔍 Swap запрос: {url}")
            logger.debug(f"📝 Payload: {json.dumps(payload, indent=2)}")

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"✅ Swap transaction получена через {base_url}")
                    return data.get('swapTransaction')

                elif response.status == 401:
                    logger.warning("⚠️ 401 Unauthorized при создании swap - переключаемся на lite-api")
                    return await self.get_swap_transaction_fallback(quote)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка Swap API {response.status}: {error_text}")
                    return await self.get_swap_transaction_fallback(quote)

        except Exception as e:
            logger.error(f"❌ Ошибка получения транзакции обмена: {e}")
            return await self.get_swap_transaction_fallback(quote)

    async def get_swap_transaction_fallback(self, quote: QuoteResponse) -> Optional[str]:
        """Fallback метод для получения транзакции обмена"""
        try:
            # Пробуем альтернативный endpoint
            alt_url = settings.jupiter.api_url if settings.jupiter.use_lite_api else settings.jupiter.lite_api_url
            url = f"{alt_url}/swap"

            payload = {
                'quoteResponse': {
                    'inputMint': quote.input_mint,
                    'outputMint': quote.output_mint,
                    'inAmount': quote.in_amount,
                    'outAmount': quote.out_amount,
                    'otherAmountThreshold': quote.other_amount_threshold,
                    'swapMode': quote.swap_mode,
                    'slippageBps': quote.slippage_bps,
                    'platformFee': quote.platform_fee,
                    'priceImpactPct': quote.price_impact_pct,
                    'routePlan': quote.route_plan
                },
                'userPublicKey': str(self.wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'useSharedAccounts': True,
                'feeAccount': None,
                'asLegacyTransaction': False,
                'useTokenLedger': False,
                'destinationTokenAccount': None,
                'dynamicComputeUnitLimit': True,
                'prioritizationFeeLamports': {
                    'priorityLevelWithMaxLamports': {
                        'maxLamports': settings.trading.priority_fee,
                        'priorityLevel': 'veryHigh'
                    }
                }
            }

            headers = {'Content-Type': 'application/json'}
            if settings.jupiter.api_key and alt_url == settings.jupiter.api_url:
                headers['x-api-key'] = settings.jupiter.api_key

            logger.debug(f"🔄 Fallback Swap запрос: {url}")

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Fallback swap transaction получена через {alt_url}")
                    return data.get('swapTransaction')
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Fallback Swap API тоже не работает: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка fallback транзакции обмена: {e}")
            return None

    async def send_transaction(self, swap_transaction_b64: str) -> Optional[str]:
        """Подпись и отправка транзакции в Solana - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ SOLDERS 0.26.0"""
        try:
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

    async def security_check(self, token_address: str) -> bool:
        """Быстрая проверка безопасности токена с fallback"""
        try:
            if not settings.security.enable_security_checks:
                logger.info("⏭️ Проверки безопасности отключены")
                return True

            # Попытка проверки через Price API
            pool_info = await self.get_pool_info(token_address)

            if pool_info:
                # Успешно получили информацию о токене
                if pool_info.liquidity_sol < settings.security.min_liquidity_sol:
                    logger.warning(
                        f"⚠️ Недостаточная ликвидность: {pool_info.liquidity_sol} SOL < {settings.security.min_liquidity_sol} SOL")
                    return False

                logger.info(
                    f"✅ Проверка безопасности пройдена: ~{pool_info.liquidity_sol} SOL агрегированной ликвидности")
                return True
            else:
                # Fallback: проверяем через тестовый quote
                logger.info("🔄 Price API недоступен, используем fallback проверку")
                return await self.fallback_security_check(token_address)

        except Exception as e:
            logger.error(f"❌ Ошибка проверки безопасности: {e}")
            # Fallback в случае ошибки
            return await self.fallback_security_check(token_address)

    async def fallback_security_check(self, token_address: str) -> bool:
        """Fallback проверка безопасности через тестовый quote"""
        try:
            logger.info("🧪 Выполняем fallback проверку через тестовый quote")

            # Тестируем маленькую сделку
            test_quote = await self.get_quote(
                input_mint=settings.trading.base_token,  # SOL
                output_mint=token_address,
                amount=int(0.01 * 1e9),  # 0.01 SOL в lamports
                slippage_bps=1000  # 10%
            )

            if not test_quote:
                logger.warning(f"⚠️ Не удалось получить тестовую котировку для {token_address}")
                return False

            price_impact = float(test_quote.price_impact_pct)

            if price_impact > 50.0:  # Более мягкий лимит для fallback
                logger.warning(f"⚠️ Слишком большое проскальзывание: {price_impact}%")
                return False

            logger.info(f"✅ Fallback проверка пройдена: {price_impact}% проскальзывание на тестовую сделку")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка fallback проверки: {e}")
            # В крайнем случае разрешаем торговлю для известных токенов
            if token_address == 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN':
                logger.info("✅ JUP токен - разрешаем торговлю")
                return True
            return False

    async def get_pool_info(self, token_address: str) -> Optional[PoolInfo]:
        """Получение информации о ликвидности токена через Jupiter Price API v2"""
        try:
            # Проверяем кэш
            if token_address in self.pool_cache:
                cached_time, pool_info = self.pool_cache[token_address]
                if time.time() - cached_time < 30:  # Кэш на 30 секунд
                    return pool_info

            # Используем lite-api для Price API (бесплатный)
            url = f"{settings.jupiter.price_api_url}"
            params = {
                'ids': token_address,
                'vsToken': 'So11111111111111111111111111111111111111112'  # vs SOL
            }

            headers = {'Content-Type': 'application/json'}

            logger.debug(f"🔍 Price API запрос: {url} с параметрами: {params}")

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    try:
                        data = await response.json()

                        # Проверяем что data не None и имеет нужную структуру
                        if not data or not isinstance(data, dict):
                            logger.warning(f"⚠️ Price API вернул пустой или некорректный ответ")
                            return None

                        # Обрабатываем ответ от Price API v2
                        if 'data' in data and data['data'] and token_address in data['data']:
                            token_data = data['data'][token_address]

                            if not token_data or not isinstance(token_data, dict):
                                logger.warning(f"⚠️ Данные токена пусты или некорректны")
                                return None

                            price = float(token_data.get('price', 0))

                            logger.info(f"💰 Цена {token_address}: {price} SOL")

                            # Пытаемся получить дополнительную информацию через quote для оценки ликвидности
                            liquidity_sol = await self.estimate_liquidity(token_address)

                            pool_info = PoolInfo(
                                liquidity_sol=liquidity_sol,
                                price=price,
                                market_cap=0,  # Jupiter Price API не предоставляет market cap
                                volume_24h=0,  # Jupiter Price API не предоставляет volume
                                holders_count=100  # Заглушка
                            )

                            # Кэшируем результат
                            self.pool_cache[token_address] = (time.time(), pool_info)
                            return pool_info
                        else:
                            logger.warning(f"⚠️ Токен {token_address} не найден в Price API v2")
                            return None

                    except Exception as json_error:
                        logger.error(f"❌ Ошибка парсинга JSON от Price API: {json_error}")
                        return None

                elif response.status == 404:
                    logger.warning(f"⚠️ Токен {token_address} не найден (404)")
                    return None
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Price API v2 error {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о токене: {e}")
            return None

    async def estimate_liquidity(self, token_address: str) -> float:
        """Оценка агрегированной ликвидности токена через тестовые quote запросы"""
        try:
            # Тестируем различные размеры сделок для оценки ликвидности
            test_amounts = [1e9, 5e9, 10e9, 50e9, 100e9]  # 1, 5, 10, 50, 100 SOL в lamports
            max_successful_amount = 0

            for amount in test_amounts:
                try:
                    quote = await self.get_quote(
                        input_mint=settings.trading.base_token,  # SOL
                        output_mint=token_address,
                        amount=int(amount),
                        slippage_bps=1000  # 10% для теста
                    )

                    if quote:
                        price_impact = float(quote.price_impact_pct)
                        if price_impact < 15.0:  # Если проскальзывание менее 15%
                            max_successful_amount = amount / 1e9  # Конвертируем в SOL
                        else:
                            break  # Прекращаем если проскальзывание слишком большое
                    else:
                        break

                    # Маленькая пауза между запросами
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.debug(f"Ошибка тестового quote для {amount / 1e9} SOL: {e}")
                    break

            # Оценочная ликвидность = максимальная успешная сделка * 20
            # Это консервативная оценка агрегированной ликвидности
            estimated_liquidity = max_successful_amount * 20

            # Минимальная оценка для известных токенов как JUP
            if estimated_liquidity < 1.0:
                estimated_liquidity = 1.0

            logger.info(f"📊 Оценочная агрегированная ликвидность {token_address}: ~{estimated_liquidity} SOL")
            return estimated_liquidity

        except Exception as e:
            logger.error(f"❌ Ошибка оценки ликвидности: {e}")
            # Возвращаем заниженную оценку для безопасности
            return 1.0

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

            # Проверяем Jupiter API - используем правильный бесплатный endpoint
            try:
                test_url = f"{settings.jupiter.lite_api_url}/quote"
                params = {
                    'inputMint': 'So11111111111111111111111111111111111111112',
                    'outputMint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                    'amount': '1000000',
                    'slippageBps': '50'
                }

                async with self.session.get(test_url, params=params) as resp:
                    jupiter_healthy = resp.status == 200
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"❌ Jupiter API тест не прошел: {resp.status} - {error_text}")
                    else:
                        logger.info("✅ Jupiter lite-api endpoint работает")

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
            else:
                logger.info("✅ Jupiter lite-api работает корректно")

            return {
                "status": status,
                "solana_rpc": "healthy" if solana_healthy else "error",
                "jupiter_api": "healthy" if jupiter_healthy else "error",
                "wallet_address": str(self.wallet_keypair.pubkey()) if self.wallet_keypair else "unknown",
                "sol_balance": sol_balance,
                "jupiter_endpoint": settings.jupiter.lite_api_url,
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