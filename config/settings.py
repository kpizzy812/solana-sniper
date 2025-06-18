"""
🎯 MORI Sniper Bot - Главный файл настроек
Объединяет все конфигурационные модули в единую систему настроек
"""

from .base import DatabaseConfig, LoggingConfig, AlertConfig, RateLimitConfig, validate_critical_settings
from .solana import SolanaConfig
from .trading import TradingConfig, JupiterConfig
from .security import SecurityConfig
from .monitoring import MonitoringConfig
from .ai import AIConfig
from .multi_wallet import MultiWalletConfig


class Settings:
    """Главный класс настроек, объединяющий все конфигурации"""

    def __init__(self):
        # Инициализируем все конфигурации
        self.solana = SolanaConfig()
        self.trading = TradingConfig()
        self.security = SecurityConfig()
        self.monitoring = MonitoringConfig()
        self.ai = AIConfig()
        self.jupiter = JupiterConfig()
        self.database = DatabaseConfig()
        self.logging = LoggingConfig()
        self.alerts = AlertConfig()
        self.rate_limits = RateLimitConfig()
        self.multi_wallet = MultiWalletConfig()

        # Валидация критических настроек
        self.validate()

    def validate(self):
        """Валидация критической конфигурации"""
        validate_critical_settings(
            self.solana,
            self.monitoring,
            self.trading,
            self.ai
        )

    @property
    def is_production(self) -> bool:
        """Проверка, что работаем в production (mainnet)"""
        return self.solana.is_production

    @property
    def total_investment(self) -> float:
        """Общая сумма инвестиций за один торговый сигнал"""
        return self.trading.total_investment

    def get_summary(self) -> dict:
        """Получить краткую сводку настроек для логирования"""
        return {
            'network': self.solana.network,
            'rpc_url': self.solana.rpc_url,
            'trade_amount': self.trading.trade_amount_sol,
            'num_purchases': self.trading.num_purchases,
            'total_investment': self.total_investment,
            'telegram_user_bot': self.monitoring.use_user_bot,
            'telegram_bot_api': self.monitoring.use_bot_api,
            'twitter_enabled': bool(self.monitoring.twitter_bearer_token),
            'ai_enabled': self.ai.use_ai_confirmation,
            'security_checks': self.security.enable_security_checks,
            'min_liquidity': self.security.min_liquidity_sol,
            'max_price_impact': self.security.max_price_impact,
        }


# ИСПРАВЛЕННЫЕ ИМПОРТЫ - используем абсолютные пути и заглушки для избежания циклических зависимостей
try:
    from utils.addresses import (
        is_valid_solana_address,
        extract_addresses_fast as utils_extract_addresses_fast,
        extract_jupiter_swap_addresses,
        is_wrapped_sol,
        filter_trading_targets
    )
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False
    from loguru import logger
    logger.warning("⚠️ utils.addresses недоступен, используем заглушки")

    # Заглушки для функций
    def is_valid_solana_address(address: str) -> bool:
        """Заглушка для проверки адреса"""
        if not address or not isinstance(address, str):
            return False
        return len(address) >= 32 and len(address) <= 44

    def utils_extract_addresses_fast(text: str, ai_config=None):
        """Заглушка для извлечения адресов"""
        import re
        # Простой regex для Solana адресов
        pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
        addresses = re.findall(pattern, text)
        return [addr for addr in addresses if is_valid_solana_address(addr)]

    def extract_jupiter_swap_addresses(text: str):
        """Заглушка для Jupiter адресов"""
        import re
        if 'jup.ag/swap/' not in text.lower():
            return []
        # Простой поиск адресов в Jupiter ссылках
        pattern = r'jup\.ag/swap/[^-\s]*-([1-9A-HJ-NP-Za-km-z]{32,44})'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return [addr for addr in matches if is_valid_solana_address(addr)]

    def is_wrapped_sol(address: str) -> bool:
        """Заглушка для Wrapped SOL"""
        return address == 'So11111111111111111111111111111111111111112'

    def filter_trading_targets(addresses):
        """Заглушка для фильтрации"""
        base_tokens = {
            'So11111111111111111111111111111111111111112',  # Wrapped SOL
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
        }
        return [addr for addr in addresses if addr not in base_tokens]


# Глобальный экземпляр настроек - создаем ПОСЛЕ импортов
settings = Settings()


# Обертки функций для совместимости со старым API
def has_urgent_keywords(text: str) -> bool:
    """Быстрое обнаружение ключевых слов"""
    return settings.ai.has_urgent_keywords(text)


def is_admin_message(username: str, user_id: int = None) -> bool:
    """Проверка, является ли сообщение от админа"""
    return settings.monitoring.is_admin_message(username, user_id)


# Обновленная функция extract_addresses_fast с передачей ai_config
def extract_addresses_fast(text: str):
    """Обертка для extract_addresses_fast с автоматической передачей AI конфигурации"""
    if UTILS_AVAILABLE:
        return utils_extract_addresses_fast(text, settings.ai)
    else:
        return utils_extract_addresses_fast(text)


# Экспорт основных настроек и функций для совместимости
__all__ = [
    'settings',
    'is_valid_solana_address',
    'extract_addresses_fast',
    'has_urgent_keywords',
    'is_admin_message',
    'extract_jupiter_swap_addresses',
    'is_wrapped_sol',
    'filter_trading_targets'
]