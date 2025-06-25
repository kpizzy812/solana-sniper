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

    # ✅ ИСПРАВЛЕНО: Читаем из .env
    concurrent_trades: bool = os.getenv('CONCURRENT_TRADES', 'true').lower() in ['true', '1', 'yes']

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

        logger.debug(f"🎲 Priority fees: {self.priority_fee_list}")
        logger.debug(f"🎲 Slippage values: {self.slippage_bps_list}")

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
    lite_api_url: str = 'https://lite-api.jup.ag/swap/v1'  # Бесплатный endpoint
    api_url: str = 'https://api.jup.ag/swap/v1'  # Платный endpoint (требует API ключи)
    price_api_url: str = 'https://lite-api.jup.ag/price/v2'  # Price API v2 (бесплатный)
    timeout: float = 5.0  # Таймаут API

    # ✅ УВЕЛИЧЕНО для 59 кошельков с платным API:
    max_concurrent_requests: int = int(os.getenv('JUPITER_MAX_CONCURRENT_REQUESTS', '100'))

    # ✅ ИСПРАВЛЕНО: Читаем из .env
    use_lite_api: bool = os.getenv('JUPITER_USE_LITE_API', 'true').lower() in ['true', '1', 'yes']

    api_key: str = os.getenv('JUPITER_API_KEY', '')  # API ключ для платных планов

    def __post_init__(self):
        """Логирование конфигурации Jupiter API"""
        if self.api_key and not self.use_lite_api:
            logger.info(f"🚀 Jupiter API: платный режим (api.jup.ag)")
        else:
            logger.info(f"🌐 Jupiter API: бесплатный режим (lite-api.jup.ag)")

        logger.debug(f"⚡ Max concurrent requests: {self.max_concurrent_requests}")


@dataclass
class SolanaConfig:
    """Настройки Solana RPC с оптимизацией для множественных кошельков"""

    # ✅ НОВЫЕ НАСТРОЙКИ для платного RPC:
    max_rpc_requests_per_second: int = int(os.getenv('SOLANA_RPC_MAX_REQUESTS_PER_SEC', '45'))

    # Батчинг для множественных кошельков:
    wallet_batch_size: int = int(os.getenv('WALLET_BATCH_SIZE', '15'))  # Обрабатывать по 15 кошельков за раз
    batch_delay_ms: int = int(os.getenv('WALLET_BATCH_DELAY_MS', '50'))  # 50ms между батчами

    # Таймауты и ретраи:
    rpc_timeout_seconds: float = float(os.getenv('SOLANA_RPC_TIMEOUT', '1.0'))
    max_retries: int = int(os.getenv('SOLANA_RPC_MAX_RETRIES', '2'))
    retry_delay_seconds: float = float(os.getenv('SOLANA_RPC_RETRY_DELAY', '0.1'))

    def __post_init__(self):
        """Логирование конфигурации Solana RPC"""
        logger.info(f"🌐 Solana RPC: {self.max_rpc_requests_per_second} req/s max")
        logger.debug(f"📦 Wallet batching: {self.wallet_batch_size} кошельков, {self.batch_delay_ms}ms задержка")


@dataclass
class PerformanceConfig:
    """Настройки производительности для снайпер бота"""

    # Параллельность
    max_concurrent_monitors: int = int(os.getenv('MAX_CONCURRENT_MONITORS', '10'))
    max_concurrent_trades: int = int(os.getenv('MAX_CONCURRENT_TRADES', '5'))

    # Оптимизация памяти
    enable_cache_cleanup: bool = os.getenv('ENABLE_CACHE_CLEANUP', 'true').lower() in ['true', '1', 'yes']
    cache_cleanup_interval: int = int(os.getenv('CACHE_CLEANUP_INTERVAL_SEC', '300'))  # 5 минут

    # Мониторинг производительности
    enable_performance_logging: bool = os.getenv('ENABLE_PERFORMANCE_LOGGING', 'false').lower() in ['true', '1', 'yes']
    performance_log_interval: int = int(os.getenv('PERFORMANCE_LOG_INTERVAL_SEC', '60'))  # 1 минута

    def __post_init__(self):
        """Логирование настроек производительности"""
        if self.enable_performance_logging:
            logger.info(f"📊 Performance monitoring: каждые {self.performance_log_interval}s")

        logger.debug(f"⚡ Max concurrent trades: {self.max_concurrent_trades}")
        logger.debug(f"🖥️ Cache cleanup: {'включен' if self.enable_cache_cleanup else 'отключен'}")


# Функции для валидации конфигурации
def validate_trading_config(config: TradingConfig) -> List[str]:
    """Валидация настроек торговли"""
    errors = []

    if config.trade_amount_sol <= 0:
        errors.append("TRADE_AMOUNT_SOL должен быть положительным")

    if config.num_purchases <= 0:
        errors.append("NUM_PURCHASES должен быть положительным")

    if config.trade_amount_sol > config.max_trade_amount_sol:
        errors.append("TRADE_AMOUNT_SOL не может быть больше MAX_TRADE_AMOUNT_SOL")

    if not config.priority_fee_list or all(fee <= 0 for fee in config.priority_fee_list):
        errors.append("Все значения в PRIORITY_FEE_LIST должны быть положительными")

    if not config.slippage_bps_list or all(slippage <= 0 for slippage in config.slippage_bps_list):
        errors.append("Все значения в SLIPPAGE_BPS_LIST должны быть положительными")

    return errors


def validate_jupiter_config(config: JupiterConfig) -> List[str]:
    """Валидация настроек Jupiter API"""
    errors = []

    if config.max_concurrent_requests <= 0:
        errors.append("JUPITER_MAX_CONCURRENT_REQUESTS должен быть положительным")

    if config.timeout <= 0:
        errors.append("Таймаут Jupiter API должен быть положительным")

    # Предупреждение о лимитах при использовании бесплатного API
    if (not config.api_key or config.use_lite_api) and config.max_concurrent_requests > 10:
        logger.warning("⚠️ Высокий concurrent_requests с бесплатным Jupiter API может вызвать 429 ошибки")

    return errors


def validate_solana_config(config: SolanaConfig) -> List[str]:
    """Валидация настроек Solana RPC"""
    errors = []

    if config.max_rpc_requests_per_second <= 0:
        errors.append("SOLANA_RPC_MAX_REQUESTS_PER_SEC должен быть положительным")

    if config.wallet_batch_size <= 0:
        errors.append("WALLET_BATCH_SIZE должен быть положительным")

    if config.batch_delay_ms < 0:
        errors.append("WALLET_BATCH_DELAY_MS не может быть отрицательным")

    if config.rpc_timeout_seconds <= 0:
        errors.append("SOLANA_RPC_TIMEOUT должен быть положительным")

    return errors


def validate_all_configs(trading: TradingConfig, jupiter: JupiterConfig, solana: SolanaConfig) -> None:
    """Валидация всех конфигураций и вывод ошибок"""
    all_errors = []

    all_errors.extend(validate_trading_config(trading))
    all_errors.extend(validate_jupiter_config(jupiter))
    all_errors.extend(validate_solana_config(solana))

    if all_errors:
        error_msg = "❌ Ошибки конфигурации торговли:\n" + "\n".join(f"  • {error}" for error in all_errors)
        logger.error(error_msg)
        raise ValueError(error_msg)
    else:
        logger.success("✅ Все настройки торговли валидны")