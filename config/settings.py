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

    # Telegram Bot API настройки (для совместимости)
    telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_channels: List[str] = None
    telegram_groups: List[str] = None
    telegram_admin_usernames: List[str] = None  # Список админов для фильтрации

    # Telegram User Bot настройки (новые)
    telegram_api_id: str = os.getenv('TELEGRAM_API_ID', '')
    telegram_api_hash: str = os.getenv('TELEGRAM_API_HASH', '')
    telegram_session_name: str = os.getenv('TELEGRAM_SESSION_NAME', 'mori_sniper_session')
    telegram_phone_number: str = os.getenv('TELEGRAM_PHONE_NUMBER', '')

    # Режим работы Telegram
    use_user_bot: bool = os.getenv('USE_TELEGRAM_USER_BOT', 'true').lower() in ['true', '1', 'yes']
    use_bot_api: bool = os.getenv('USE_TELEGRAM_BOT_API', 'false').lower() in ['true', '1', 'yes']

    # User Bot каналы и группы
    user_bot_channels: List[str] = None  # Каналы для User Bot
    user_bot_groups: List[str] = None  # Группы для User Bot
    user_bot_admin_usernames: List[str] = None  # Админы для User Bot

    # Twitter/X настройки
    twitter_bearer_token: str = os.getenv('TWITTER_BEARER_TOKEN', '')
    twitter_usernames: List[str] = None

    # Мониторинг сайтов
    website_urls: List[str] = None
    website_selectors: List[str] = None

    def __post_init__(self):
        # Telegram Bot API каналы/группы (старые настройки)
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

        # Telegram User Bot каналы/группы (новые настройки)
        if self.user_bot_channels is None:
            self.user_bot_channels = [
                os.getenv('USER_BOT_CHANNEL_1', ''),
                os.getenv('USER_BOT_CHANNEL_2', ''),
                os.getenv('USER_BOT_CHANNEL_3', ''),
            ]

        if self.user_bot_groups is None:
            self.user_bot_groups = [
                os.getenv('USER_BOT_GROUP_1', ''),
                os.getenv('USER_BOT_GROUP_2', ''),
                os.getenv('USER_BOT_GROUP_3', ''),
            ]

        if self.user_bot_admin_usernames is None:
            self.user_bot_admin_usernames = [
                os.getenv('USER_BOT_ADMIN_1', ''),
                os.getenv('USER_BOT_ADMIN_2', ''),
                os.getenv('USER_BOT_ADMIN_3', ''),
            ]

        # Twitter настройки
        if self.twitter_usernames is None:
            self.twitter_usernames = [
                os.getenv('TWITTER_USERNAME_1', ''),
                os.getenv('TWITTER_USERNAME_2', '')
            ]

        # Website настройки
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
    # ПРАВИЛЬНЫЕ Jupiter API endpoints (январь 2025)
    # ВАЖНО: Правильная структура путей для v1 API
    lite_api_url: str = 'https://lite-api.jup.ag/swap/v1'  # Бесплатный endpoint (ПРИОРИТЕТ)
    api_url: str = 'https://api.jup.ag/swap/v1'  # Платный endpoint (требует API ключи)
    price_api_url: str = 'https://lite-api.jup.ag/price/v2'  # Price API v2 (бесплатный)
    timeout: float = 5.0  # Таймаут API
    max_concurrent_requests: int = 20  # Увеличено для параллельных сделок
    use_lite_api: bool = True  # Использовать бесплатный endpoint по умолчанию
    api_key: str = os.getenv('JUPITER_API_KEY', '')  # API ключ для платных планов


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

        # Проверяем настройки Telegram мониторинга
        telegram_configured = False

        if self.monitoring.use_user_bot:
            if self.monitoring.telegram_api_id and self.monitoring.telegram_api_hash:
                telegram_configured = True
            else:
                errors.append("Для User Bot нужны TELEGRAM_API_ID и TELEGRAM_API_HASH")

        if self.monitoring.use_bot_api:
            if self.monitoring.telegram_bot_token:
                telegram_configured = True
            else:
                errors.append("Для Bot API нужен TELEGRAM_BOT_TOKEN")

        if not telegram_configured and not self.monitoring.twitter_bearer_token and not any(
                self.monitoring.website_urls):
            errors.append("Нужен хотя бы один метод мониторинга (Telegram User Bot/Bot API, Twitter или Website)")

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


# ИСПРАВЛЕННЫЕ Быстрые функции валидации адресов
def is_valid_solana_address(address: str) -> bool:
    """Строгая валидация формата Solana адреса с base58 декодированием"""
    if not address or not isinstance(address, str):
        return False

    # Проверка длины (32-44 символа для base58)
    if len(address) < 32 or len(address) > 44:
        return False

    # Набор символов Base58 (исключает 0, O, I, l для избежания путаницы)
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_chars for c in address):
        return False

    # Исключаем очевидные ложные срабатывания
    if address == '1' * len(address):  # Все единицы
        return False
    if len(set(address)) < 8:  # Слишком мало уникальных символов
        return False

    # КРИТИЧНАЯ ПРОВЕРКА: Реальное base58 декодирование
    try:
        import base58
        decoded = base58.b58decode(address)
        # Solana адреса должны быть ровно 32 байта
        if len(decoded) != 32:
            return False
        return True
    except Exception:
        return False


def extract_jupiter_swap_addresses(text: str) -> List[str]:
    """Улучшенный парсер для Jupiter swap ссылок с строгой валидацией"""
    addresses = []

    # Поиск Jupiter ссылок в тексте
    if 'jup.ag/swap/' not in text.lower():
        return addresses

    logger.debug(f"🔍 Обнаружена Jupiter ссылка в тексте: {text}")

    # Используем более точный regex для Jupiter URLs
    jupiter_patterns = [
        # Основной паттерн: jup.ag/swap/TOKEN1-TOKEN2
        r'jup\.ag/swap/([A-HJ-NP-Za-km-z1-9]{32,44})-([A-HJ-NP-Za-km-z1-9]{32,44})',
        # Альтернативный: jup.ag/swap?inputMint=TOKEN1&outputMint=TOKEN2
        r'jup\.ag/swap\?.*?(?:inputMint|outputMint)=([A-HJ-NP-Za-km-z1-9]{32,44})',
        # Простой поиск токенов после jup.ag/
        r'jup\.ag/[^?\s]*?([A-HJ-NP-Za-km-z1-9]{32,44})'
    ]

    for pattern in jupiter_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Извлекаем все группы из матча
            for group in match.groups():
                if group and is_valid_solana_address(group):
                    # Дополнительная фильтрация: пропускаем Wrapped SOL
                    if not is_wrapped_sol(group):
                        logger.info(f"✅ Jupiter токен найден: {group}")
                        addresses.append(group)
                    else:
                        logger.debug(f"⏭️ Пропускаем Wrapped SOL: {group}")

    # Если основные паттерны не сработали, пробуем ручной парсинг
    if not addresses:
        addresses.extend(manual_jupiter_parsing(text))

    return addresses


def manual_jupiter_parsing(text: str) -> List[str]:
    """Ручной парсинг Jupiter ссылок для сложных случаев"""
    addresses = []

    try:
        # Ищем части URL после jup.ag/swap/
        parts = text.lower().split('jup.ag/swap/')
        if len(parts) < 2:
            return addresses

        # Берем часть после jup.ag/swap/
        url_part = parts[1].split()[0].split('?')[0].split('#')[0]
        logger.debug(f"🔍 Извлеченная часть URL: {url_part}")

        # Разделяем по дефису для формата TOKEN1-TOKEN2
        if '-' in url_part:
            tokens = url_part.split('-')
            for token in tokens:
                # Очищаем от лишних символов
                clean_token = ''.join(
                    c for c in token if c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')

                logger.debug(f"🧹 Проверяем очищенный токен: {clean_token}")

                if is_valid_solana_address(clean_token):
                    if not is_wrapped_sol(clean_token):
                        logger.info(f"✅ Найден валидный токен: {clean_token}")
                        addresses.append(clean_token)
                    else:
                        logger.debug(f"⏭️ Пропускаем Wrapped SOL: {clean_token}")
                else:
                    logger.debug(f"❌ Невалидный токен: {clean_token}")

        # Дополнительный поиск отдельных токенов в URL
        all_potential_tokens = re.findall(r'[A-HJ-NP-Za-km-z1-9]{32,44}', url_part)
        for token in all_potential_tokens:
            if is_valid_solana_address(token) and not is_wrapped_sol(token):
                if token not in addresses:
                    logger.info(f"✅ Дополнительный токен найден: {token}")
                    addresses.append(token)

    except Exception as e:
        logger.error(f"❌ Ошибка ручного парсинга Jupiter: {e}")

    return addresses


def is_wrapped_sol(address: str) -> bool:
    """Проверка является ли адрес Wrapped SOL"""
    return address == 'So11111111111111111111111111111111111111112'


def filter_trading_targets(addresses: List[str]) -> List[str]:
    """Фильтрация адресов для торговли (исключаем SOL и известные базовые токены)"""
    filtered = []

    # Известные базовые токены которые НЕ покупаем
    base_tokens = {
        'So11111111111111111111111111111111111111112',  # Wrapped SOL
        'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
        'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
        '11111111111111111111111111111112',  # System Program
    }

    for addr in addresses:
        if addr not in base_tokens:
            logger.info(f"✅ Целевой токен для торговли: {addr}")
            filtered.append(addr)
        else:
            logger.debug(f"⏭️ Пропускаем базовый токен: {addr}")

    return filtered


def extract_addresses_fast(text: str) -> List[str]:
    """Ультра-быстрое извлечение адресов с улучшенной валидацией"""
    addresses = set()

    # ОТЛАДКА: Логируем входной текст
    logger.debug(f"🔍 Анализируем текст: {text[:200]}...")

    # СПЕЦИАЛЬНАЯ ОБРАБОТКА JUPITER ССЫЛОК (ПРИОРИТЕТ!)
    jupiter_addresses = extract_jupiter_swap_addresses(text)
    if jupiter_addresses:
        logger.critical(f"🎯 JUPITER SWAP НАЙДЕН: {jupiter_addresses}")
        addresses.update(jupiter_addresses)

    # Получаем паттерны
    try:
        patterns = settings.ai.solana_address_patterns
        if not patterns:
            logger.warning("⚠️ Паттерны адресов не инициализированы")
            return list(addresses)
    except AttributeError:
        logger.error("❌ Ошибка доступа к паттернам адресов")
        return list(addresses)

    for i, pattern in enumerate(patterns):
        try:
            matches = pattern.findall(text)
            if matches:
                logger.debug(f"✅ Паттерн {i} нашел совпадения: {matches}")

            for match in matches:
                # Обрабатываем результаты tuple из групп
                addr = match if isinstance(match, str) else match[0] if match else ''

                if addr:
                    logger.debug(f"🔍 Проверяем адрес из паттерна {i}: {addr}")

                    # СТРОГАЯ ВАЛИДАЦИЯ
                    if is_valid_solana_address(addr):
                        # ФИЛЬТРУЕМ WRAPPED SOL
                        if is_wrapped_sol(addr):
                            logger.debug(f"⏭️ Пропускаем Wrapped SOL: {addr}")
                            continue

                        logger.info(f"✅ ВАЛИДНЫЙ АДРЕС НАЙДЕН: {addr}")
                        addresses.add(addr)
                    else:
                        logger.debug(f"❌ Невалидный адрес: {addr}")
        except Exception as e:
            logger.error(f"❌ Ошибка в паттерне {i}: {e}")

    # Фильтруем адреса для торговли
    result = filter_trading_targets(list(addresses))
    logger.info(f"🎯 ИТОГО НАЙДЕНО ЦЕЛЕВЫХ ТОКЕНОВ: {len(result)} | {result}")
    return result


def has_urgent_keywords(text: str) -> bool:
    """Быстрое обнаружение ключевых слов"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in settings.ai.urgent_keywords)


def is_admin_message(username: str, user_id: int = None) -> bool:
    """Проверка, является ли сообщение от админа"""
    if not username:
        return False

    # Проверяем по имени пользователя для User Bot
    user_bot_admins = [admin.lower() for admin in settings.monitoring.user_bot_admin_usernames if admin]
    if username.lower() in user_bot_admins:
        return True

    # Проверяем по имени пользователя для Bot API
    bot_api_admins = [admin.lower() for admin in settings.monitoring.telegram_admin_usernames if admin]
    return username.lower() in bot_api_admins


# Обновленные regex паттерны с более строгой валидацией
def ensure_patterns_initialized():
    """Принудительная инициализация улучшенных паттернов"""
    if not hasattr(settings.ai, '_solana_address_patterns') or not settings.ai._solana_address_patterns:
        logger.info("🔧 Инициализируем улучшенные паттерны адресов...")

        settings.ai._solana_address_patterns = [
            # Основной паттерн Solana адресов (32-44 символа, строго base58)
            re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'),

            # Паттерны с ключевыми словами (более строгие границы)
            re.compile(r'\bcontract[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bmint[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\baddress[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bca[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bтокен[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bконтракт[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),

            # Jupiter паттерны (улучшенные с границами слов)
            re.compile(r'\bjup\.ag/swap/[^-\s]*-([1-9A-HJ-NP-Za-km-z]{32,44})[\s?&#]', re.IGNORECASE),
            re.compile(r'\bjup\.ag[^\s]*?([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),

            # Другие DEX паттерны
            re.compile(r'\braydium\.io[^\s]*?([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
            re.compile(r'\bdexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
            re.compile(r'\bbirdeye\.so/token/([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),

            # URL параметры с границами
            re.compile(r'[?&]token=([1-9A-HJ-NP-Za-km-z]{32,44})(?:[&#]|$)', re.IGNORECASE),
            re.compile(r'[?&]mint=([1-9A-HJ-NP-Za-km-z]{32,44})(?:[&#]|$)', re.IGNORECASE),
            re.compile(r'[?&]address=([1-9A-HJ-NP-Za-km-z]{32,44})(?:[&#]|$)', re.IGNORECASE),

            # Специальный паттерн для точного извлечения из Jupiter ссылок
            re.compile(
                r'So11111111111111111111111111111111111111112-([1-9A-HJ-NP-Za-km-z]{32,44})(?:[^A-HJ-NP-Za-km-z1-9]|$)',
                re.IGNORECASE),

            # Паттерн для адресов в кавычках или скобках
            re.compile(r'["\'`\(\[]([1-9A-HJ-NP-Za-km-z]{32,44})["\'`\)\]]'),
        ]

        logger.success(f"✅ Инициализировано {len(settings.ai._solana_address_patterns)} улучшенных паттернов")


# Вызываем инициализацию при импорте
ensure_patterns_initialized()

# Экспорт основных настроек
__all__ = [
    'settings', 'is_valid_solana_address', 'extract_addresses_fast',
    'has_urgent_keywords', 'is_admin_message', 'extract_jupiter_swap_addresses',
    'is_wrapped_sol', 'filter_trading_targets'
]