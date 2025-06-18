"""
🎯 MORI Sniper Bot - Jupiter Trading (Compatibility Layer)
Файл совместимости для импорта модульной системы Jupiter
"""

# Импортируем все из нового модульного Jupiter
from .jupiter import (
    UltraFastJupiterTrader,
    jupiter_trader,
    TradeResult,
    PoolInfo
)

# Дополнительные импорты для полной совместимости
from .jupiter.models import (
    QuoteResponse,
    SwapRequest,
    TradingSession
)

from .jupiter.client import JupiterAPIClient
from .jupiter.executor import JupiterTradeExecutor
from .jupiter.security import JupiterSecurityChecker

# Обратная совместимость - экспортируем главный класс под старым именем
UltraFastJupiterTrader = UltraFastJupiterTrader

# Экспорт всех важных компонентов
__all__ = [
    # Главные классы
    'UltraFastJupiterTrader',
    'jupiter_trader',

    # Модели данных
    'TradeResult',
    'PoolInfo',
    'QuoteResponse',
    'SwapRequest',
    'TradingSession',

    # Компоненты системы
    'JupiterAPIClient',
    'JupiterTradeExecutor',
    'JupiterSecurityChecker'
]

# Логирование для отладки
from loguru import logger

logger.debug("✅ Jupiter торговая система загружена через модульную архитектуру")