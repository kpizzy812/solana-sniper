import os
from typing import List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """Настройки базы данных"""
    db_path: str = os.getenv('DB_PATH', 'data/sniper.db')
    backup_interval: int = 3600  # Бэкап каждый час
    cleanup_days: int = 30  # Хранить данные 30 дней


@dataclass
class LoggingConfig:
    """Настройки логирования"""
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    file_path: str = os.getenv('LOG_FILE', 'logs/sniper.log')
    max_size: str = '100 MB'
    retention: str = '7 days'
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"


@dataclass
class AlertConfig:
    """Настройки уведомлений"""
    telegram_alerts_chat_id: str = os.getenv('TELEGRAM_ALERTS_CHAT_ID', '')
    discord_webhook: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    email_alerts: bool = False


@dataclass
class RateLimitConfig:
    """Настройки лимитов запросов"""
    telegram_per_second: int = 30
    twitter_per_15min: int = 75
    jupiter_per_second: int = 50  # Увеличено для агрессивной торговли
    solana_rpc_per_second: int = 200  # Увеличено для быстрых сделок


def validate_critical_settings(solana_config, monitoring_config, trading_config, ai_config):
    """Валидация критических настроек всей системы"""
    errors = []

    # Проверка Solana настроек
    if not solana_config.private_key:
        errors.append("Нужен SOLANA_PRIVATE_KEY или SOLANA_SEED_PHRASE")

    # Проверяем настройки Telegram мониторинга
    telegram_configured = False

    if monitoring_config.use_user_bot:
        if monitoring_config.telegram_api_id and monitoring_config.telegram_api_hash:
            telegram_configured = True
        else:
            errors.append("Для User Bot нужны TELEGRAM_API_ID и TELEGRAM_API_HASH")

    if monitoring_config.use_bot_api:
        if monitoring_config.telegram_bot_token:
            telegram_configured = True
        else:
            errors.append("Для Bot API нужен TELEGRAM_BOT_TOKEN")

    if not telegram_configured and not monitoring_config.twitter_bearer_token and not any(
            monitoring_config.website_urls):
        errors.append("Нужен хотя бы один метод мониторинга (Telegram User Bot/Bot API, Twitter или Website)")

    if ai_config.use_ai_confirmation and not ai_config.openai_api_key:
        from loguru import logger
        logger.warning("⚠️ AI подтверждение отключено - нет OPENAI_API_KEY")
        ai_config.use_ai_confirmation = False

    if trading_config.trade_amount_sol <= 0:
        errors.append("TRADE_AMOUNT_SOL должен быть положительным")

    if trading_config.num_purchases <= 0:
        errors.append("NUM_PURCHASES должен быть положительным")

    if trading_config.trade_amount_sol > trading_config.max_trade_amount_sol:
        errors.append("TRADE_AMOUNT_SOL не может быть больше MAX_TRADE_AMOUNT_SOL")

    if errors:
        raise ValueError(f"Ошибки конфигурации:\n" + "\n".join(errors))