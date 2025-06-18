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


# Глобальный экземпляр настроек
settings = Settings()

# Импортируем функции для работы с адресами из utils
from ..utils.addresses import (
    is_valid_solana_address,
    extract_addresses_fast,
    extract_jupiter_swap_addresses,
    is_wrapped_sol,
    filter_trading_targets
)


# Обертки функций для совместимости со старым API
def has_urgent_keywords(text: str) -> bool:
    """Быстрое обнаружение ключевых слов"""
    return settings.ai.has_urgent_keywords(text)


def is_admin_message(username: str, user_id: int = None) -> bool:
    """Проверка, является ли сообщение от админа"""
    return settings.monitoring.is_admin_message(username, user_id)


# Обновленная функция extract_addresses_fast с передачей ai_config
def extract_addresses_fast_wrapper(text: str):
    """Обертка для extract_addresses_fast с автоматической передачей AI конфигурации"""
    from ..utils.addresses import extract_addresses_fast
    return extract_addresses_fast(text, settings.ai)


# Переопределяем функцию в глобальном пространстве для совместимости
extract_addresses_fast = extract_addresses_fast_wrapper

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