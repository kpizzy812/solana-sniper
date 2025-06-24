"""
📊 MORI Sniper Bot - Jupiter Models ИСПРАВЛЕННАЯ ВЕРСИЯ
Модели данных для работы с Jupiter DEX API
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


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

    def __str__(self):
        if self.success:
            return f"Trade {self.trade_index + 1}: ✅ {self.signature} ({self.execution_time_ms:.0f}ms)"
        else:
            return f"Trade {self.trade_index + 1}: ❌ {self.error}"


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
    route_plan: List[Dict] = field(default_factory=list)

    @property
    def price_impact_float(self) -> float:
        """Проскальзывание в виде числа"""
        try:
            return float(self.price_impact_pct)
        except (ValueError, TypeError):
            return 0.0

    @property
    def in_amount_lamports(self) -> int:
        """Входная сумма в lamports"""
        try:
            return int(self.in_amount)
        except (ValueError, TypeError):
            return 0

    @property
    def out_amount_lamports(self) -> int:
        """Выходная сумма в lamports"""
        try:
            return int(self.out_amount)
        except (ValueError, TypeError):
            return 0

    @property
    def in_amount_sol(self) -> float:
        """Входная сумма в SOL"""
        return self.in_amount_lamports / 1e9

    @property
    def out_amount_tokens(self) -> float:
        """Выходная сумма в токенах (приблизительно)"""
        return self.out_amount_lamports / 1e9  # Может потребоваться корректировка под decimals токена


@dataclass
class SwapRequest:
    """Запрос на создание swap транзакции - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ JUPITER V6/V1"""
    quote_response: QuoteResponse
    user_public_key: str
    wrap_and_unwrap_sol: bool = True
    fee_account: Optional[str] = None
    as_legacy_transaction: bool = False
    use_token_ledger: bool = False
    destination_token_account: Optional[str] = None
    dynamic_compute_unit_limit: bool = True
    priority_fee_lamports: int = 100000

    def to_dict(self) -> Dict:
        """Преобразование в словарь для API запроса - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        payload = {
            'quoteResponse': {
                'inputMint': self.quote_response.input_mint,
                'outputMint': self.quote_response.output_mint,
                'inAmount': self.quote_response.in_amount,
                'outAmount': self.quote_response.out_amount,
                'otherAmountThreshold': self.quote_response.other_amount_threshold,
                'swapMode': self.quote_response.swap_mode,
                'slippageBps': self.quote_response.slippage_bps,
                'platformFee': self.quote_response.platform_fee,
                'priceImpactPct': self.quote_response.price_impact_pct,
                'routePlan': self.quote_response.route_plan
            },
            'userPublicKey': self.user_public_key,
            'wrapAndUnwrapSol': self.wrap_and_unwrap_sol,
            'asLegacyTransaction': self.as_legacy_transaction,
            'useTokenLedger': self.use_token_ledger,
            'dynamicComputeUnitLimit': self.dynamic_compute_unit_limit,
        }

        # ИСПРАВЛЕННАЯ СТРУКТУРА prioritizationFeeLamports для Jupiter V6
        # Используем простое число как рекомендует актуальная документация
        payload['prioritizationFeeLamports'] = self.priority_fee_lamports

        # АЛЬТЕРНАТИВНО можно использовать объект (если простое число не работает):
        # payload['prioritizationFeeLamports'] = {
        #     'priorityLevelWithMaxLamports': {
        #         'maxLamports': self.priority_fee_lamports,
        #         'priorityLevel': 'veryHigh'
        #     }
        # }

        # НЕ ДОБАВЛЯЕМ destinationTokenAccount - пусть Jupiter сам создает ATA
        if self.fee_account:
            payload['feeAccount'] = self.fee_account

        return payload


@dataclass
class PoolInfo:
    """Информация о ликвидности токена (агрегированная)"""
    liquidity_sol: float
    price: float
    market_cap: float = 0.0
    volume_24h: float = 0.0
    holders_count: int = 100

    @property
    def is_liquid_enough(self) -> bool:
        """Проверка достаточности ликвидности"""
        # Импортируем локально чтобы избежать циклических импортов
        try:
            from config.settings import settings
            return self.liquidity_sol >= settings.security.min_liquidity_sol
        except ImportError:
            # Fallback значение если настройки недоступны
            return self.liquidity_sol >= 5.0

    def __str__(self):
        return f"Pool(liquidity={self.liquidity_sol:.2f} SOL, price={self.price:.8f})"


@dataclass
class TradingSession:
    """Сессия торговли для группы сделок"""
    token_address: str
    source_info: Dict
    start_time: float
    amounts: List[float]
    results: List[TradeResult] = field(default_factory=list)
    total_sol_spent: float = 0.0
    total_tokens_bought: float = 0.0

    @property
    def successful_trades(self) -> int:
        """Количество успешных сделок"""
        return sum(1 for result in self.results if result.success)

    @property
    def failed_trades(self) -> int:
        """Количество неудачных сделок"""
        return len(self.results) - self.successful_trades

    @property
    def success_rate(self) -> float:
        """Процент успешных сделок"""
        if not self.results:
            return 0.0
        return (self.successful_trades / len(self.results)) * 100

    @property
    def average_execution_time(self) -> float:
        """Среднее время исполнения успешных сделок"""
        successful = [r for r in self.results if r.success]
        if not successful:
            return 0.0
        return sum(r.execution_time_ms for r in successful) / len(successful)

    def get_signatures(self) -> List[str]:
        """Получить все подписи успешных транзакций"""
        return [r.signature for r in self.results if r.success and r.signature]

    def add_result(self, result: TradeResult):
        """Добавить результат сделки"""
        self.results.append(result)
        if result.success:
            self.total_sol_spent += result.input_amount
            if result.output_amount:
                self.total_tokens_bought += result.output_amount