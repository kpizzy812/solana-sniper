import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Импорты для конвертации seed phrase
try:
    from mnemonic import Mnemonic
    from solders.keypair import Keypair
    import base58

    CRYPTO_LIBS_AVAILABLE = True
except ImportError:
    CRYPTO_LIBS_AVAILABLE = False
    logger.warning("⚠️ Библиотеки для seed phrase не установлены. Используйте: pip install mnemonic")


def convert_seed_to_private_key(seed_phrase: str) -> str:
    """Конвертирует seed phrase в base58 приватный ключ"""
    if not CRYPTO_LIBS_AVAILABLE:
        raise ImportError("Установите: pip install mnemonic solders")

    try:
        mnemo = Mnemonic("english")
        clean_phrase = seed_phrase.strip()

        if not mnemo.check(clean_phrase):
            raise ValueError("Неверная seed phrase")

        seed = mnemo.to_seed(clean_phrase)
        keypair = Keypair.from_seed(seed[:32])
        private_key = base58.b58encode(bytes(keypair)).decode('utf-8')

        logger.info(f"✅ Приватный ключ сгенерирован из seed phrase")
        logger.info(f"🏦 Адрес кошелька: {keypair.pubkey()}")

        return private_key
    except Exception as e:
        raise ValueError(f"Ошибка конвертации seed phrase: {e}")


@dataclass
class SolanaConfig:
    rpc_url: str = os.getenv('SOLANA_RPC_URL', 'https://api.devnet.solana.com')
    network: str = 'mainnet'  # devnet для тестов, mainnet-beta для продакшена
    private_key: str = ''
    commitment: str = 'confirmed'

    def __post_init__(self):
        """Автоматическая конвертация seed phrase в private key"""
        # Сначала пробуем получить готовый приватный ключ
        direct_key = os.getenv('SOLANA_PRIVATE_KEY', '')

        if direct_key:
            self.private_key = direct_key
            logger.debug("🔑 Используется готовый приватный ключ")
        else:
            # Если нет готового ключа, конвертируем из seed phrase
            seed_phrase = os.getenv('SOLANA_SEED_PHRASE', '')

            if seed_phrase:
                try:
                    self.private_key = convert_seed_to_private_key(seed_phrase)
                    logger.success("🔄 Seed phrase сконвертирована в приватный ключ")
                except Exception as e:
                    logger.error(f"❌ Ошибка конвертации seed phrase: {e}")
                    raise
            else:
                logger.error("❌ Не найден ни SOLANA_PRIVATE_KEY, ни SOLANA_SEED_PHRASE")

        # Определяем сеть из RPC URL
        if 'mainnet' in self.rpc_url:
            self.network = 'mainnet-beta'
        elif 'devnet' in self.rpc_url:
            self.network = 'devnet'


@dataclass
class TradingConfig:
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


@dataclass
class SecurityConfig:
    enable_security_checks: bool = True
    min_liquidity_sol: float = float(os.getenv('MIN_LIQUIDITY', '5'))
    max_buy_tax: int = int(os.getenv('MAX_BUY_TAX', '10'))
    max_sell_tax: int = int(os.getenv('MAX_SELL_TAX', '10'))
    max_price_impact: float = float(os.getenv('MAX_PRICE_IMPACT', '15.0'))  # Максимальное проскальзывание %
    check_honeypot: bool = True
    check_mint_authority: bool = True
    check_freeze_authority: bool = True
    min_holders: int = int(os.getenv('MIN_HOLDERS', '10'))
    security_timeout: float = 2.0  # Максимальное время для проверок безопасности
    blacklisted_tokens: List[str] = None  # Черный список токенов

    def __post_init__(self):
        if self.blacklisted_tokens is None:
            self.blacklisted_tokens = []


@dataclass
class MonitoringConfig:
    # Интервалы проверки в секундах
    telegram_interval: float = 1.0  # Каждую секунду
    twitter_interval: float = 2.0  # Twitter имеет более строгие лимиты
    website_interval: float = 5.0

    # Telegram настройки
    telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_channels: List[str] = None
    telegram_groups: List[str] = None
    telegram_admin_usernames: List[str] = None  # Список админов для фильтрации

    # Twitter/X настройки
    twitter_bearer_token: str = os.getenv('TWITTER_BEARER_TOKEN', '')
    twitter_usernames: List[str] = None

    # Мониторинг сайтов
    website_urls: List[str] = None
    website_selectors: List[str] = None

    def __post_init__(self):
        if self.telegram_channels is None:
            self.telegram_channels = [
                os.getenv('TELEGRAM_CHANNEL_1', ''),
                os.getenv('TELEGRAM_CHANNEL_2', '')
            ]

        if self.telegram_groups is None:
            self.telegram_groups = [
                os.getenv('TELEGRAM_GROUP_1', ''),
                os.getenv('TELEGRAM_GROUP_2', '')
            ]

        if self.telegram_admin_usernames is None:
            self.telegram_admin_usernames = [
                os.getenv('TELEGRAM_ADMIN_1', ''),
                os.getenv('TELEGRAM_ADMIN_2', '')
            ]

        if self.twitter_usernames is None:
            self.twitter_usernames = [
                os.getenv('TWITTER_USERNAME_1', ''),
                os.getenv('TWITTER_USERNAME_2', '')
            ]

        if self.website_urls is None:
            self.website_urls = [
                os.getenv('WEBSITE_URL_1', ''),
                os.getenv('WEBSITE_URL_2', '')
            ]

        if self.website_selectors is None:
            self.website_selectors = [
                '.contract-address',
                '.token-address',
                '#contract',
                '[data-contract]',
                '.address',
                '[data-address]'
            ]


@dataclass
class AIConfig:
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    model: str = 'gpt-4o-mini'  # Более быстрая модель
    max_tokens: int = 100  # Уменьшено для скорости
    temperature: float = 0.1

    # Оптимизация скорости
    use_fast_analysis: bool = True  # Использовать regex в первую очередь
    use_ai_confirmation: bool = False  # AI анализ отключен по умолчанию
    ai_timeout: float = 3.0  # Максимальное время для AI анализа
    cache_ai_results: bool = True

    # Компилированные regex паттерны для скорости
    _solana_address_patterns = None
    urgent_keywords: List[str] = None

    def __post_init__(self):
        # Автоматически включаем AI если есть ключ
        if self.openai_api_key and not self.use_ai_confirmation:
            self.use_ai_confirmation = True
            logger.info("✅ AI анализ включен автоматически (найден OpenAI ключ)")

        if self._solana_address_patterns is None:
            self._solana_address_patterns = [
                re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'),  # Solana адрес
                re.compile(r'contract[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'mint[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'address[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'ca[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'токен[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'контракт[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                # Специальные паттерны для URL (Jupiter, DEX ссылки)
                re.compile(r'jup\.ag/swap/[^-]*-([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'raydium\.io/.*?([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'dexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'birdeye\.so/token/([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                # Общие паттерны для URL параметров
                re.compile(r'[?&]token=([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'[?&]mint=([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                re.compile(r'[?&]address=([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
                # Паттерн для разделенных через дефис адресов (как в Jupiter)
                re.compile(r'[/-]([1-9A-HJ-NP-Za-km-z]{32,44})(?:[?&#/]|$)', re.IGNORECASE)
            ]

        if self.urgent_keywords is None:
            self.urgent_keywords = [
                '$mori', 'contract', 'launch', 'live', 'now', 'urgent',
                'ca:', 'mint:', 'address:', 'buy now', 'launching',
                'контракт', 'запуск', 'токен', 'адрес', 'покупай'
            ]

    @property
    def solana_address_patterns(self):
        return self._solana_address_patterns


@dataclass
class JupiterConfig:
    api_url: str = 'https://quote-api.jup.ag/v6'
    swap_api_url: str = 'https://quote-api.jup.ag/v6/swap'
    price_api_url: str = 'https://price.jup.ag/v4/price'
    timeout: float = 5.0  # Таймаут API
    max_concurrent_requests: int = 20  # Увеличено для параллельных сделок


@dataclass
class DatabaseConfig:
    db_path: str = os.getenv('DB_PATH', 'data/sniper.db')
    backup_interval: int = 3600  # Бэкап каждый час
    cleanup_days: int = 30  # Хранить данные 30 дней


@dataclass
class LoggingConfig:
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    file_path: str = os.getenv('LOG_FILE', 'logs/sniper.log')
    max_size: str = '100 MB'
    retention: str = '7 days'
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"


@dataclass
class AlertConfig:
    telegram_alerts_chat_id: str = os.getenv('TELEGRAM_ALERTS_CHAT_ID', '')
    discord_webhook: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    email_alerts: bool = False


@dataclass
class RateLimitConfig:
    telegram_per_second: int = 30
    twitter_per_15min: int = 75
    jupiter_per_second: int = 50  # Увеличено для агрессивной торговли
    solana_rpc_per_second: int = 200  # Увеличено для быстрых сделок


class Settings:
    def __init__(self):
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
        errors = []

        if not self.solana.private_key:
            errors.append("Нужен SOLANA_PRIVATE_KEY или SOLANA_SEED_PHRASE")

        if not any([
            self.monitoring.telegram_bot_token,
            self.monitoring.twitter_bearer_token,
            any(self.monitoring.website_urls)
        ]):
            errors.append("Нужен хотя бы один токен API соцсетей или URL сайта")

        if self.ai.use_ai_confirmation and not self.ai.openai_api_key:
            logger.warning("⚠️ AI подтверждение отключено - нет OPENAI_API_KEY")
            self.ai.use_ai_confirmation = False

        if self.trading.trade_amount_sol <= 0:
            errors.append("TRADE_AMOUNT_SOL должен быть положительным")

        if self.trading.num_purchases <= 0:
            errors.append("NUM_PURCHASES должен быть положительным")

        if self.trading.trade_amount_sol > self.trading.max_trade_amount_sol:
            errors.append("TRADE_AMOUNT_SOL не может быть больше MAX_TRADE_AMOUNT_SOL")

        if errors:
            raise ValueError(f"Ошибки конфигурации:\n" + "\n".join(errors))

    @property
    def is_production(self) -> bool:
        return self.solana.network == 'mainnet-beta'

    @property
    def total_investment(self) -> float:
        return self.trading.trade_amount_sol * self.trading.num_purchases


# Глобальный экземпляр настроек
settings = Settings()


# Быстрые функции валидации адресов
def is_valid_solana_address(address: str) -> bool:
    """Быстрая валидация формата Solana адреса"""
    if len(address) < 32 or len(address) > 44:
        return False

    # Набор символов Base58
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_chars for c in address):
        return False

    # Исключаем очевидные ложные срабатывания
    if address == '1' * len(address):  # Все единицы
        return False
    if address.isupper() or address.islower():  # Все в одном регистре
        return False

    return True


def extract_addresses_fast(text: str) -> List[str]:
    """Ультра-быстрое извлечение адресов через regex"""
    addresses = set()

    for pattern in settings.ai.solana_address_patterns:
        matches = pattern.findall(text)
        for match in matches:
            # Обрабатываем результаты tuple из групп
            addr = match if isinstance(match, str) else match[0] if match else ''
            if addr and is_valid_solana_address(addr):
                addresses.add(addr)

    return list(addresses)


def has_urgent_keywords(text: str) -> bool:
    """Быстрое обнаружение ключевых слов"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in settings.ai.urgent_keywords)


def is_admin_message(username: str, user_id: int = None) -> bool:
    """Проверка, является ли сообщение от админа"""
    if not username:
        return False

    # Проверяем по имени пользователя
    admin_usernames = [admin.lower() for admin in settings.monitoring.telegram_admin_usernames if admin]
    return username.lower() in admin_usernames


# Экспорт основных настроек
__all__ = [
    'settings', 'is_valid_solana_address', 'extract_addresses_fast',
    'has_urgent_keywords', 'is_admin_message'
]