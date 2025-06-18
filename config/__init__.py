"""
⚙️ MORI Sniper Bot - Конфигурация
Модульная система настроек с разделением по логическим группам
"""

from .settings import (
    settings,
    is_valid_solana_address,
    extract_addresses_fast,
    has_urgent_keywords,
    is_admin_message,
    extract_jupiter_swap_addresses,
    is_wrapped_sol,
    filter_trading_targets
)

# Импорты отдельных конфигурационных классов для расширенного использования
from .base import DatabaseConfig, LoggingConfig, AlertConfig, RateLimitConfig
from .solana import SolanaConfig
from .trading import TradingConfig, JupiterConfig
from .security import SecurityConfig
from .monitoring import MonitoringConfig
from .ai import AIConfig

__all__ = [
    # Главный объект настроек
    'settings',

    # Функции для работы с адресами (совместимость)
    'is_valid_solana_address',
    'extract_addresses_fast',
    'has_urgent_keywords',
    'is_admin_message',
    'extract_jupiter_swap_addresses',
    'is_wrapped_sol',
    'filter_trading_targets',

    # Классы конфигурации (для расширенного использования)
    'DatabaseConfig',
    'LoggingConfig',
    'AlertConfig',
    'RateLimitConfig',
    'SolanaConfig',
    'TradingConfig',
    'JupiterConfig',
    'SecurityConfig',
    'MonitoringConfig',
    'AIConfig'
]