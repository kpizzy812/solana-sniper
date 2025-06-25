#!/usr/bin/env python3
"""
🤖 Автоопределение администраторов Telegram групп/каналов
Сканирует админов и автоматически добавляет их в .env
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings

try:
    from telethon import TelegramClient
    from telethon.tl.types import ChannelParticipantsAdmins

    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.error("❌ Telethon не установлен! Установите: pip install telethon")


class AdminDetector:
    """Детектор администраторов в Telegram"""

    def __init__(self):
        self.client = None
        self.detected_admins = set()

    async def start(self):
        """Запуск клиента"""
        if not TELETHON_AVAILABLE:
            logger.error("❌ Telethon недоступен")
            return False

        if not settings.monitoring.telegram_api_id or not settings.monitoring.telegram_api_hash:
            logger.error("❌ Не настроены TELEGRAM_API_ID и TELEGRAM_API_HASH")
            return False

        try:
            # Создаем клиент
            session_file = f"{settings.monitoring.telegram_session_name}.session"
            self.client = TelegramClient(
                session_file,
                int(settings.monitoring.telegram_api_id),
                settings.monitoring.telegram_api_hash
            )

            # Подключаемся
            await self.client.start(phone=settings.monitoring.telegram_phone_number)

            if await self.client.is_user_authorized():
                me = await self.client.get_me()
                logger.success(f"✅ Подключен как: @{me.username} ({me.first_name})")
                return True
            else:
                logger.error("❌ Не удалось авторизоваться")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка запуска клиента: {e}")
            return False

    async def get_chat_admins(self, chat_identifier: str):
        """Получение админов конкретного чата"""
        try:
            logger.info(f"🔍 Сканируем админов: {chat_identifier}")

            # Получаем объект чата
            entity = await self.client.get_entity(chat_identifier)

            logger.info(f"📋 Чат найден: {entity.title}")

            # Получаем админов
            admins = []
            async for participant in self.client.iter_participants(entity, filter=ChannelParticipantsAdmins):
                # Пропускаем удаленные аккаунты и без username
                if participant.deleted or not hasattr(participant, 'username') or not participant.username:
                    continue

                admin_info = {
                    'username': participant.username,
                    'first_name': getattr(participant, 'first_name', ''),
                    'last_name': getattr(participant, 'last_name', ''),
                    'id': participant.id
                }

                admins.append(admin_info)
                self.detected_admins.add(participant.username.lower())

                logger.success(
                    f"👑 Админ найден: @{participant.username} ({admin_info['first_name']} {admin_info['last_name']})")

            logger.info(f"✅ Найдено {len(admins)} админов в {entity.title}")
            return admins

        except Exception as e:
            logger.error(f"❌ Ошибка получения админов {chat_identifier}: {e}")
            return []

    async def scan_all_chats(self):
        """Сканирование всех настроенных чатов"""
        logger.info("🎯 АВТООПРЕДЕЛЕНИЕ АДМИНОВ")
        logger.info("=" * 40)

        all_admins = {}

        # Сканируем каналы
        channels = settings.monitoring.user_bot_channels
        if channels:
            logger.info("📺 Сканирование каналов...")
            for channel in channels:
                if channel and channel.strip():
                    admins = await self.get_chat_admins(channel.strip())
                    if admins:
                        all_admins[channel] = admins

        # Сканируем группы
        groups = settings.monitoring.user_bot_groups
        if groups:
            logger.info("👥 Сканирование групп...")
            for group in groups:
                if group and group.strip():
                    admins = await self.get_chat_admins(group.strip())
                    if admins:
                        all_admins[group] = admins

        return all_admins

    def update_env_file(self):
        """Обновление .env файла с найденными админами"""
        if not self.detected_admins:
            logger.warning("⚠️ Не найдено админов для добавления")
            return

        env_file = Path('.env')

        if not env_file.exists():
            logger.error("❌ Файл .env не найден")
            return

        # Читаем текущий .env
        lines = []
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

        # Удаляем существующие USER_BOT_ADMIN строки
        lines = [line for line in lines if not line.startswith('USER_BOT_ADMIN_')]

        # Добавляем новых админов
        admin_list = list(self.detected_admins)
        admin_lines = []

        for i, admin in enumerate(admin_list[:10], 1):  # Максимум 10 админов
            admin_lines.append(f"USER_BOT_ADMIN_{i}={admin}\n")

        # Записываем обновленный .env
        try:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                f.write("\n# Автоопределенные админы\n")
                f.writelines(admin_lines)

            logger.success(f"✅ Добавлено {len(admin_list)} админов в .env:")
            for i, admin in enumerate(admin_list, 1):
                logger.success(f"   USER_BOT_ADMIN_{i}={admin}")

        except Exception as e:
            logger.error(f"❌ Ошибка записи .env: {e}")

    async def stop(self):
        """Остановка клиента"""
        if self.client:
            await self.client.disconnect()

    async def run(self):
        """Главный метод"""
        try:
            # Запуск
            if not await self.start():
                return False

            # Сканирование
            all_admins = await self.scan_all_chats()

            if not all_admins:
                logger.warning("⚠️ Не найдено чатов для сканирования")
                return False

            # Отчет
            logger.info("\n" + "=" * 50)
            logger.info("📊 ИТОГОВЫЙ ОТЧЕТ")
            logger.info("=" * 50)

            total_admins = 0
            for chat, admins in all_admins.items():
                logger.info(f"📍 {chat}:")
                for admin in admins:
                    logger.info(f"  👑 @{admin['username']} - {admin['first_name']} {admin['last_name']}")
                    total_admins += 1

            logger.success(f"\n🎉 ВСЕГО НАЙДЕНО: {total_admins} админов")
            logger.success(f"🔧 УНИКАЛЬНЫХ: {len(self.detected_admins)} username")

            # Обновляем .env
            if self.detected_admins:
                logger.info("\n💾 Обновляем .env файл...")
                self.update_env_file()

            return True

        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            return False

        finally:
            await self.stop()


async def main():
    """Главная функция"""
    detector = AdminDetector()
    success = await detector.run()

    if success:
        logger.info("\n🚀 Готово! Теперь перезапустите бота для применения новых админов.")
    else:
        logger.error("\n❌ Не удалось определить админов")


if __name__ == "__main__":
    asyncio.run(main())