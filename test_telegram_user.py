#!/usr/bin/env python3
"""
🧪 Тест Telegram User Bot
Проверяет подключение и настройку User Bot перед основным запуском
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PATH
sys.path.append(str(Path(__file__).parent))

from loguru import logger
from config.settings import settings

# Проверяем доступность Telethon
try:
    from telethon import TelegramClient
    from monitors.telegram_user import telegram_user_monitor, TELETHON_AVAILABLE

    IMPORTS_OK = True
except ImportError as e:
    logger.error(f"❌ Ошибка импорта: {e}")
    IMPORTS_OK = False


class TelegramUserBotTester:
    """Тестер Telegram User Bot"""

    def __init__(self):
        self.test_results = {}

    async def run_all_tests(self):
        """Запуск всех тестов"""
        logger.info("🧪 Тестирование Telegram User Bot")
        logger.info("=" * 50)

        # Тест библиотек
        await self.test_dependencies()

        # Тест конфигурации
        await self.test_configuration()

        # Тест подключения
        if self.test_results.get('dependencies', False) and self.test_results.get('configuration', False):
            await self.test_connection()

        # Тест мониторинга
        if self.test_results.get('connection', False):
            await self.test_monitoring()

        # Итоговый отчет
        self.print_summary()

    async def test_dependencies(self):
        """Тест зависимостей"""
        logger.info("📦 Тестирование зависимостей...")

        try:
            if not IMPORTS_OK:
                logger.error("❌ Не удалось импортировать зависимости")
                logger.info("💡 Установите: pip install telethon")
                self.test_results['dependencies'] = False
                return

            if not TELETHON_AVAILABLE:
                logger.error("❌ Telethon недоступен")
                self.test_results['dependencies'] = False
                return

            # Проверяем версию Telethon
            import telethon
            logger.info(f"✅ Telethon версия: {telethon.__version__}")

            self.test_results['dependencies'] = True

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования зависимостей: {e}")
            self.test_results['dependencies'] = False

    async def test_configuration(self):
        """Тест конфигурации"""
        logger.info("⚙️ Тестирование конфигурации...")

        try:
            errors = []

            # Проверяем обязательные параметры
            if not settings.monitoring.telegram_api_id:
                errors.append("TELEGRAM_API_ID не установлен")

            if not settings.monitoring.telegram_api_hash:
                errors.append("TELEGRAM_API_HASH не установлен")

            if not settings.monitoring.telegram_phone_number:
                errors.append("TELEGRAM_PHONE_NUMBER не установлен")

            # Проверяем каналы/группы для мониторинга
            channels = [ch for ch in settings.monitoring.user_bot_channels if ch]
            groups = [gr for gr in settings.monitoring.user_bot_groups if gr]

            if not channels and not groups:
                errors.append("Нужен хотя бы один канал или группа для мониторинга")

            if errors:
                logger.error(f"❌ Ошибки конфигурации:")
                for error in errors:
                    logger.error(f"  - {error}")
                self.test_results['configuration'] = False
            else:
                logger.success("✅ Конфигурация корректна")
                logger.info(f"📺 Каналов для мониторинга: {len(channels)}")
                logger.info(f"👥 Групп для мониторинга: {len(groups)}")
                self.test_results['configuration'] = True

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования конфигурации: {e}")
            self.test_results['configuration'] = False

    async def test_connection(self):
        """Тест подключения к Telegram"""
        logger.info("🔗 Тестирование подключения...")

        try:
            if not telegram_user_monitor:
                logger.error("❌ User Bot монитор недоступен")
                self.test_results['connection'] = False
                return

            # Пробуем подключиться
            logger.info("📱 Подключение к Telegram...")
            success = await telegram_user_monitor.start()

            if success:
                logger.success("✅ Подключение успешно!")

                # Получаем информацию о подключении
                health = await telegram_user_monitor.health_check()
                logger.info(f"👤 Пользователь: @{health.get('username', 'Unknown')}")
                logger.info(f"📊 Мониторимых чатов: {health.get('monitored_chats', 0)}")

                self.test_results['connection'] = True

                # Останавливаем для тестов
                await telegram_user_monitor.stop()

            else:
                logger.error("❌ Не удалось подключиться")
                self.test_results['connection'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования подключения: {e}")
            logger.info("💡 Возможные причины:")
            logger.info("  - Неверные API_ID/API_HASH")
            logger.info("  - Неверный номер телефона")
            logger.info("  - Требуется код подтверждения")
            logger.info("  - Требуется двухфакторная аутентификация")
            self.test_results['connection'] = False

    async def test_monitoring(self):
        """Тест функций мониторинга"""
        logger.info("👁️ Тестирование мониторинга...")

        try:
            if not telegram_user_monitor:
                self.test_results['monitoring'] = False
                return

            # Запускаем монитор на короткое время
            success = await telegram_user_monitor.start()

            if success:
                logger.info("⏱️ Мониторинг активен (тест 5 секунд)...")

                # Ждем 5 секунд для получения статистики
                await asyncio.sleep(5)

                # Получаем статистику
                stats = telegram_user_monitor.get_stats()
                logger.info(f"📊 Статистика за 5 секунд:")
                logger.info(f"  - Обработано сообщений: {stats.get('messages_processed', 0)}")
                logger.info(f"  - Найдено контрактов: {stats.get('contracts_found', 0)}")
                logger.info(f"  - Ошибок: {stats.get('errors', 0)}")

                self.test_results['monitoring'] = True

                # Останавливаем
                await telegram_user_monitor.stop()

            else:
                logger.error("❌ Не удалось запустить мониторинг")
                self.test_results['monitoring'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования мониторинга: {e}")
            self.test_results['monitoring'] = False

    def print_summary(self):
        """Печать итогового отчета"""
        logger.info("\n" + "=" * 50)
        logger.info("📊 ИТОГИ ТЕСТИРОВАНИЯ TELEGRAM USER BOT")
        logger.info("=" * 50)

        total_tests = 0
        passed_tests = 0

        for test_name, result in self.test_results.items():
            if result is None:
                status = "⏭️ ПРОПУЩЕН"
            elif result:
                status = "✅ ПРОЙДЕН"
                passed_tests += 1
                total_tests += 1
            else:
                status = "❌ ПРОВАЛЕН"
                total_tests += 1

            logger.info(f"{test_name.replace('_', ' ').title():<20} {status}")

        logger.info("=" * 50)

        if total_tests == 0:
            logger.warning("⚠️ Все тесты пропущены")
        elif passed_tests == total_tests:
            logger.success(f"🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({passed_tests}/{total_tests})")
            logger.success("🚀 Telegram User Bot готов к работе!")
            logger.info("")
            logger.info("🔥 Рекомендации для продакшена:")
            logger.info("  1. Проверьте, что у вас есть доступ ко всем каналам/группам")
            logger.info("  2. Настройте админов для фильтрации сообщений в группах")
            logger.info("  3. Запустите полный бот: python main.py")
        else:
            logger.warning(f"⚠️ Тесты пройдены частично ({passed_tests}/{total_tests})")
            logger.info("🔧 Исправьте ошибки перед запуском")

        logger.info("\n💡 Первый запуск User Bot может потребовать:")
        logger.info("  - Ввод кода подтверждения из SMS")
        logger.info("  - Ввод пароля двухфакторной аутентификации")
        logger.info("  - Подтверждение входа с нового устройства")


async def main():
    """Главная функция"""
    print("🧪 Тест Telegram User Bot для MORI Sniper")
    print("=" * 50)

    tester = TelegramUserBotTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Запуск тестов
    asyncio.run(main())