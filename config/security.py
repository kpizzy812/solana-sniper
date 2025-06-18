import os
from typing import List
from dataclasses import dataclass


@dataclass
class SecurityConfig:
    """Настройки безопасности и риск-менеджмента"""
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

        # Загружаем черный список из переменной окружения
        blacklist_env = os.getenv('BLACKLISTED_TOKENS', '')
        if blacklist_env:
            self.blacklisted_tokens.extend([token.strip() for token in blacklist_env.split(',') if token.strip()])

    def is_token_blacklisted(self, token_address: str) -> bool:
        """Проверка, находится ли токен в черном списке"""
        return token_address in self.blacklisted_tokens

    def add_to_blacklist(self, token_address: str):
        """Добавление токена в черный список"""
        if token_address not in self.blacklisted_tokens:
            self.blacklisted_tokens.append(token_address)

    def is_wrapped_sol(self, address: str) -> bool:
        """Проверка является ли адрес Wrapped SOL"""
        return address == 'So11111111111111111111111111111111111111112'