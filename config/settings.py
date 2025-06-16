import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SolanaConfig:
    rpc_url: str = os.getenv('SOLANA_RPC_URL', 'https://api.devnet.solana.com')
    network: str = 'devnet'  # devnet for testing, mainnet-beta for production
    private_key: str = os.getenv('SOLANA_PRIVATE_KEY', '')
    commitment: str = 'confirmed'


@dataclass
class TradingConfig:
    target_token: str = os.getenv('TARGET_TOKEN', 'YOUR_TEST_TOKEN_MINT')
    base_token: str = 'So11111111111111111111111111111111111111112'  # Wrapped SOL
    trade_amount_sol: float = float(os.getenv('TRADE_AMOUNT_SOL', '0.1'))
    num_purchases: int = int(os.getenv('NUM_PURCHASES', '10'))
    slippage_bps: int = int(os.getenv('SLIPPAGE_BPS', '500'))  # 5%
    priority_fee: int = int(os.getenv('PRIORITY_FEE', '100000'))  # microlamports
    max_retries: int = 3
    retry_delay: float = 0.5  # seconds - fast retries
    concurrent_trades: bool = True  # Execute all purchases simultaneously


@dataclass
class SecurityConfig:
    min_liquidity_sol: float = float(os.getenv('MIN_LIQUIDITY', '5'))
    max_buy_tax: int = int(os.getenv('MAX_BUY_TAX', '10'))
    max_sell_tax: int = int(os.getenv('MAX_SELL_TAX', '10'))
    check_honeypot: bool = True
    check_mint_authority: bool = True
    check_freeze_authority: bool = True
    min_holders: int = int(os.getenv('MIN_HOLDERS', '10'))
    security_timeout: float = 2.0  # Max time for security checks


@dataclass
class MonitoringConfig:
    # Check intervals in seconds
    telegram_interval: float = 1.0  # Every second
    discord_interval: float = 1.0
    twitter_interval: float = 2.0  # Twitter has stricter rate limits
    website_interval: float = 5.0

    # Telegram settings
    telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_channels: List[str] = [
        os.getenv('TELEGRAM_CHANNEL_1', '@ProfessorMoriarty'),
        os.getenv('TELEGRAM_CHANNEL_2', '@MoriForum')
    ]

    # Discord settings
    discord_bot_token: str = os.getenv('DISCORD_BOT_TOKEN', '')
    discord_guild_id: str = os.getenv('DISCORD_GUILD_ID', '')
    discord_channels: List[str] = [
        os.getenv('DISCORD_CHANNEL_1', 'announcements'),
        os.getenv('DISCORD_CHANNEL_2', 'general')
    ]

    # Twitter/X settings
    twitter_bearer_token: str = os.getenv('TWITTER_BEARER_TOKEN', '')
    twitter_usernames: List[str] = [
        os.getenv('TWITTER_USERNAME_1', 'ProfessorMoriarty'),
        os.getenv('TWITTER_USERNAME_2', 'MoriToken')
    ]

    # Website monitoring
    website_urls: List[str] = [
        os.getenv('WEBSITE_URL_1', 'https://moritoken.com'),
        os.getenv('WEBSITE_URL_2', 'https://professor-moriarty.net')
    ]
    website_selectors: List[str] = [
        '.contract-address',
        '.token-address',
        '#contract',
        '[data-contract]'
    ]


@dataclass
class AIConfig:
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    model: str = 'gpt-4'
    max_tokens: int = 100  # Reduced for speed
    temperature: float = 0.1

    # Speed optimization
    use_fast_analysis: bool = True  # Use regex first
    use_ai_confirmation: bool = True  # AI analysis in background
    ai_timeout: float = 3.0  # Max time for AI analysis
    cache_ai_results: bool = True

    # Pattern matching for speed
    solana_address_patterns: List[re.Pattern] = [
        re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'),  # Solana address
        re.compile(r'contract[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
        re.compile(r'mint[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
        re.compile(r'address[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
        re.compile(r'ca[:\s]*([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE)
    ]

    # Signal keywords for fast detection
    urgent_keywords: List[str] = [
        '$mori', 'contract', 'launch', 'live', 'now', 'urgent',
        'ca:', 'mint:', 'address:', 'buy now', 'launching'
    ]


@dataclass
class JupiterConfig:
    api_url: str = 'https://quote-api.jup.ag/v6'
    swap_api_url: str = 'https://quote-api.jup.ag/v6/swap'
    price_api_url: str = 'https://price.jup.ag/v4/price'
    timeout: float = 5.0  # API timeout
    max_concurrent_requests: int = 10


@dataclass
class DatabaseConfig:
    db_path: str = os.getenv('DB_PATH', 'data/sniper.db')
    backup_interval: int = 3600  # Backup every hour
    cleanup_days: int = 30  # Keep data for 30 days


@dataclass
class LoggingConfig:
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    file_path: str = os.getenv('LOG_FILE', 'logs/sniper.log')
    max_size: str = '100 MB'
    retention: str = '7 days'
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"


@dataclass
class AlertConfig:
    discord_webhook: str = os.getenv('DISCORD_WEBHOOK_URL', '')
    telegram_chat_id: str = os.getenv('TELEGRAM_ALERTS_CHAT_ID', '')
    email_alerts: bool = False


@dataclass
class RateLimitConfig:
    telegram_per_second: int = 30
    twitter_per_15min: int = 75
    discord_per_second: int = 50
    jupiter_per_second: int = 20
    solana_rpc_per_second: int = 100


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

        # Validate critical settings
        self.validate()

    def validate(self):
        """Validate critical configuration"""
        errors = []

        if not self.solana.private_key:
            errors.append("SOLANA_PRIVATE_KEY is required")

        if not any([
            self.monitoring.telegram_bot_token,
            self.monitoring.discord_bot_token,
            self.monitoring.twitter_bearer_token
        ]):
            errors.append("At least one social media API token is required")

        if self.ai.use_ai_confirmation and not self.ai.openai_api_key:
            errors.append("OPENAI_API_KEY is required when AI confirmation is enabled")

        if self.trading.trade_amount_sol <= 0:
            errors.append("TRADE_AMOUNT_SOL must be positive")

        if self.trading.num_purchases <= 0:
            errors.append("NUM_PURCHASES must be positive")

        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(errors))

    @property
    def is_production(self) -> bool:
        return self.solana.network == 'mainnet-beta'

    @property
    def total_investment(self) -> float:
        return self.trading.trade_amount_sol * self.trading.num_purchases


# Global settings instance
settings = Settings()


# Fast validation functions for addresses
def is_valid_solana_address(address: str) -> bool:
    """Fast validation for Solana address format"""
    if len(address) < 32 or len(address) > 44:
        return False

    # Base58 character set
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_chars for c in address):
        return False

    # Exclude obvious false positives
    if address == '1' * len(address):  # All 1s
        return False
    if address.isupper() or address.islower():  # All same case
        return False

    return True


def extract_addresses_fast(text: str) -> List[str]:
    """Ultra-fast address extraction using regex"""
    addresses = set()

    for pattern in settings.ai.solana_address_patterns:
        matches = pattern.findall(text)
        for match in matches:
            # Handle tuple results from groups
            addr = match if isinstance(match, str) else match[0] if match else ''
            if addr and is_valid_solana_address(addr):
                addresses.add(addr)

    return list(addresses)


def has_urgent_keywords(text: str) -> bool:
    """Fast keyword detection"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in settings.ai.urgent_keywords)


# Export main settings
__all__ = ['settings', 'is_valid_solana_address', 'extract_addresses_fast', 'has_urgent_keywords']