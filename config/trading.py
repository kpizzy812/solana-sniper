import os
from dataclasses import dataclass
import random
from typing import List
from loguru import logger
@dataclass
class TradingConfig:
    """Настройки торговой системы"""
    target_token: str = os.getenv('TARGET_TOKEN', '')
    base_token: str = 'So11111111111111111111111111111111111111112'  # Wrapped SOL
    trade_amount_sol: float = float(os.getenv('TRADE_AMOUNT_SOL', '0.1'))
    num_purchases: int = int(os.getenv('NUM_PURCHASES', '1'))
    slippage_bps: int = int(os.getenv('SLIPPAGE_BPS', '500'))  # 5%
    priority_fee: int = int(os.getenv('PRIORITY_FEE', '100000'))  # microlamports
    max_retries: int = 3
    retry_delay: float = 0.5  # секунды - быстрые повторы
    concurrent_trades: bool = True  # Выполнять все покупки одновременно
    smart_split: bool = True  # Умное распределение размеров сделок
    max_trade_amount_sol: float = float(os.getenv('MAX_TRADE_AMOUNT_SOL', '1.0'))  # Максимум на одну сделку

    # НОВАЯ НАСТРОЙКА для трат всего баланса
    use_max_available_balance: bool = os.getenv('USE_MAX_AVAILABLE_BALANCE', 'false').lower() in ['true', '1', 'yes']

    # Списки для рандомного выбора
    priority_fee_list: List[int] = None
    slippage_bps_list: List[int] = None

    def __post_init__(self):
        """Инициализация списков для рандомизации"""
        # Читаем списки из .env
        priority_fee_str = os.getenv('PRIORITY_FEE_LIST', '')
        slippage_bps_str = os.getenv('SLIPPAGE_BPS_LIST', '')

        # Парсим priority fees
        if priority_fee_str:
            try:
                self.priority_fee_list = [int(x.strip()) for x in priority_fee_str.split(',') if x.strip()]
            except ValueError:
                logger.warning("⚠️ Ошибка парсинга PRIORITY_FEE_LIST, используем базовое значение")
                self.priority_fee_list = [self.priority_fee]
        else:
            self.priority_fee_list = [self.priority_fee]

        # Парсим slippage
        if slippage_bps_str:
            try:
                self.slippage_bps_list = [int(x.strip()) for x in slippage_bps_str.split(',') if x.strip()]
            except ValueError:
                logger.warning("⚠️ Ошибка парсинга SLIPPAGE_BPS_LIST, используем базовое значение")
                self.slippage_bps_list = [self.slippage_bps]
        else:
            self.slippage_bps_list = [self.slippage_bps]

    def get_random_priority_fee(self) -> int:
        """Случайный выбор приоритетной комиссии из списка"""
        return random.choice(self.priority_fee_list)

    def get_random_slippage(self) -> int:
        """Случайный выбор проскальзывания из списка"""
        return random.choice(self.slippage_bps_list)

    @property
    def total_investment(self) -> float:
        """Общая сумма инвестиций за один сигнал"""
        return self.trade_amount_sol * self.num_purchases


@dataclass
class JupiterConfig:
    """Настройки Jupiter DEX API"""
    # ПРАВИЛЬНЫЕ Jupiter API endpoints (январь 2025)
    # ВАЖНО: Правильная структура путей для v1 API
    lite_api_url: str = 'https://lite-api.jup.ag/swap/v1'  # Бесплатный endpoint (ПРИОРИТЕТ)
    api_url: str = 'https://api.jup.ag/swap/v1'  # Платный endpoint (требует API ключи)
    price_api_url: str = 'https://lite-api.jup.ag/price/v2'  # Price API v2 (бесплатный)
    timeout: float = 5.0  # Таймаут API
    max_concurrent_requests: int = 20  # Увеличено для параллельных сделок
    use_lite_api: bool = True  # Использовать бесплатный endpoint по умолчанию
    api_key: str = os.getenv('JUPITER_API_KEY', '')  # API ключ для платных планов