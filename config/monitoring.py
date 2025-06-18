import os
from typing import List
from dataclasses import dataclass


@dataclass
class MonitoringConfig:
    """Настройки мониторинга социальных сетей и сайтов"""

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

    def is_admin_message(self, username: str, user_id: int = None) -> bool:
        """Проверка, является ли сообщение от админа"""
        if not username:
            return False

        # Проверяем по имени пользователя для User Bot
        user_bot_admins = [admin.lower() for admin in self.user_bot_admin_usernames if admin]
        if username.lower() in user_bot_admins:
            return True

        # Проверяем по имени пользователя для Bot API
        bot_api_admins = [admin.lower() for admin in self.telegram_admin_usernames if admin]
        return username.lower() in bot_api_admins

    def get_all_telegram_channels(self) -> List[str]:
        """Получить все настроенные Telegram каналы"""
        all_channels = []

        # Bot API каналы
        all_channels.extend([ch for ch in self.telegram_channels if ch])

        # User Bot каналы
        all_channels.extend([ch for ch in self.user_bot_channels if ch])

        return list(set(all_channels))  # Убираем дубликаты

    def get_all_telegram_groups(self) -> List[str]:
        """Получить все настроенные Telegram группы"""
        all_groups = []

        # Bot API группы
        all_groups.extend([gr for gr in self.telegram_groups if gr])

        # User Bot группы
        all_groups.extend([gr for gr in self.user_bot_groups if gr])

        return list(set(all_groups))  # Убираем дубликаты