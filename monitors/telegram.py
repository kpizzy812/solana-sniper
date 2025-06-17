import asyncio
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

# Python Telegram Bot импорты
try:
    from telegram import Bot, Update
    from telegram.ext import Application, MessageHandler, filters, CallbackContext
    from telegram.error import TelegramError, Forbidden, BadRequest

    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False

from loguru import logger

from config.settings import settings, is_admin_message
from ai.analyzer import analyzer


@dataclass
class TelegramBotPost:
    """Данные сообщения от Bot API"""
    message_id: int
    chat_id: int
    chat_title: str
    chat_username: str
    author_id: int
    author_username: str
    author_first_name: str
    content: str
    timestamp: datetime
    url: str
    message_type: str  # 'channel', 'group', 'private'
    is_admin: bool = False


class TelegramBotAPIMonitor:
    """Мониторинг Telegram через Bot API (резервная система)"""

    def __init__(self, trading_callback=None):
        self.trading_callback = trading_callback
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None

        # Проверяем доступность библиотеки
        if not TELEGRAM_BOT_AVAILABLE:
            logger.error("❌ python-telegram-bot не установлен! Установите: pip install python-telegram-bot")
            return

        # Отслеживание обработанных сообщений
        self.processed_messages: Set[str] = set()  # chat_id:message_id
        self.last_message_time = {}  # chat_id -> timestamp

        # Производительность
        self.running = False
        self.polling_task_handle = None  # Для отслеживания polling задачи

        # Статистика
        self.stats = {
            'messages_processed': 0,
            'contracts_found': 0,
            'channels_monitored': 0,
            'groups_monitored': 0,
            'errors': 0
        }

    async def start(self) -> bool:
        """Запуск мониторинга Telegram Bot API"""
        if not TELEGRAM_BOT_AVAILABLE:
            logger.error("❌ Telegram Bot API библиотека недоступна")
            return False

        if not settings.monitoring.telegram_bot_token:
            logger.warning("⚠️ Telegram Bot Token не настроен")
            return False

        try:
            # Инициализация Bot API
            logger.info("🤖 Инициализация Telegram Bot API...")

            self.application = Application.builder().token(settings.monitoring.telegram_bot_token).build()
            self.bot = self.application.bot

            # Проверяем токен
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Bot подключен: @{bot_info.username}")

            # Настраиваем обработчики
            self.setup_handlers()

            # Запускаем приложение
            await self.application.initialize()
            await self.application.start()

            # Начинаем polling в фоновом режиме
            self.running = True
            self.polling_task_handle = asyncio.create_task(self.polling_task())

            logger.success("✅ Telegram Bot API запущен")
            logger.warning("⚠️ ВНИМАНИЕ: Bot API получает только сообщения где бот упомянут или добавлен в группы")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram Bot API: {e}")
            return False

    async def stop(self):
        """Остановка монитора"""
        self.running = False

        # Отменяем polling задачу
        if self.polling_task_handle and not self.polling_task_handle.done():
            logger.debug("Отменяем polling задачу...")
            self.polling_task_handle.cancel()
            try:
                await self.polling_task_handle
            except asyncio.CancelledError:
                logger.debug("Polling задача отменена")

        if self.application:
            try:
                # Останавливаем updater если он запущен
                if (hasattr(self.application, 'updater') and
                        self.application.updater and
                        hasattr(self.application.updater, 'running') and
                        self.application.updater.running):
                    logger.debug("Останавливаем Telegram updater...")
                    await self.application.updater.stop()

                # Останавливаем приложение
                logger.debug("Останавливаем Telegram application...")
                await self.application.stop()
                await self.application.shutdown()

            except RuntimeError as e:
                if "not running" in str(e).lower():
                    logger.debug(f"Updater уже остановлен: {e}")
                else:
                    logger.warning(f"RuntimeError при остановке: {e}")
            except Exception as e:
                logger.warning(f"Ошибка остановки Telegram Bot API: {e}")

        logger.info("🛑 Telegram Bot API остановлен")

    def setup_handlers(self):
        """Настройка обработчиков сообщений"""

        async def message_handler(update: Update, context: CallbackContext):
            """Обработчик всех сообщений"""
            try:
                if update.message:
                    await self.process_message(update.message)
            except Exception as e:
                logger.error(f"❌ Ошибка обработки сообщения: {e}")
                self.stats['errors'] += 1

        # Добавляем обработчик для всех текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT, message_handler))

    async def polling_task(self):
        """Задача polling в фоновом режиме"""
        try:
            # Запускаем polling без блокировки
            await self.application.updater.start_polling()

            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}")
        finally:
            # НЕ останавливаем updater здесь - это сделает метод stop()
            logger.debug("Polling задача завершена")

    async def process_message(self, message):
        """Обработка одного сообщения"""
        try:
            # Пропускаем уже обработанные
            message_key = f"{message.chat_id}:{message.message_id}"
            if message_key in self.processed_messages:
                return

            # Rate limiting
            now = time.time()
            last_time = self.last_message_time.get(message.chat_id, 0)
            if now - last_time < 1.0:  # Не чаще 1 сообщения в секунду на чат
                return
            self.last_message_time[message.chat_id] = now

            # Получаем информацию о чате
            chat = message.chat
            user = message.from_user

            if not user:
                return

            # Формируем данные поста
            post = TelegramBotPost(
                message_id=message.message_id,
                chat_id=message.chat_id,
                chat_title=chat.title or 'Private',
                chat_username=chat.username or '',
                author_id=user.id,
                author_username=user.username or '',
                author_first_name=user.first_name or '',
                content=message.text or '',
                timestamp=message.date,
                url=f"https://t.me/{chat.username}/{message.message_id}" if chat.username else f"https://t.me/c/{abs(message.chat_id)}/{message.message_id}",
                message_type='channel' if chat.type == 'channel' else 'group' if chat.type in ['group',
                                                                                               'supergroup'] else 'private',
                is_admin=is_admin_message(user.username, user.id)
            )

            # Логируем получение сообщения
            logger.debug(f"💬 Bot API сообщение в {post.chat_title}: @{post.author_username} - {post.content[:50]}...")

            # Фильтрация по админам в группах
            if post.message_type == 'group' and not post.is_admin:
                logger.debug(f"⏭️ Пропускаем сообщение от не-админа @{post.author_username}")
                return

            # Быстрый анализ на контракты
            analysis_result = await analyzer.analyze_post(
                content=post.content,
                platform="telegram_bot",
                author=post.author_username,
                url=post.url
            )

            logger.info(f"🤖 Telegram Bot @{post.author_username} в {post.chat_title}: "
                        f"контракт={analysis_result.has_contract}, уверенность={analysis_result.confidence:.2f}")

            # Если найден контракт с высокой уверенностью
            if analysis_result.has_contract and analysis_result.confidence > 0.6:
                logger.critical(f"🚨 КОНТРАКТ В TELEGRAM BOT API!")
                logger.critical(f"📍 Автор: @{post.author_username} в {post.chat_title}")
                logger.critical(f"🎯 Контракты: {analysis_result.addresses}")

                if self.trading_callback:
                    await self.trigger_trading(analysis_result, post)

                self.stats['contracts_found'] += 1

            # Отмечаем как обработанный
            self.processed_messages.add(message_key)
            self.stats['messages_processed'] += 1

            # Очистка старых сообщений из памяти
            if len(self.processed_messages) > 1000:
                old_messages = list(self.processed_messages)[:200]
                for old_msg in old_messages:
                    self.processed_messages.discard(old_msg)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения Bot API: {e}")
            self.stats['errors'] += 1

    async def trigger_trading(self, analysis_result, post: TelegramBotPost):
        """Запуск торговли"""
        try:
            trading_data = {
                'platform': 'telegram_bot',
                'source': f"{post.chat_title} (@{post.chat_username})",
                'author': post.author_username,
                'author_id': post.author_id,
                'chat_id': post.chat_id,
                'message_id': post.message_id,
                'url': post.url,
                'contracts': analysis_result.addresses,
                'confidence': analysis_result.confidence,
                'urgency': analysis_result.urgency,
                'timestamp': post.timestamp,
                'content_preview': post.content[:200],
                'message_type': post.message_type,
                'is_admin': post.is_admin
            }

            # Вызываем систему торговли
            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговли: {e}")

    async def health_check(self) -> Dict:
        """Проверка здоровья монитора"""
        try:
            if not TELEGRAM_BOT_AVAILABLE:
                return {"status": "error", "message": "python-telegram-bot не установлен"}

            if not self.bot:
                return {"status": "error", "message": "Bot не инициализирован"}

            # Проверяем токен
            try:
                bot_info = await self.bot.get_me()
                bot_username = bot_info.username
                bot_accessible = True
            except Exception as e:
                bot_username = "Unknown"
                bot_accessible = False

            return {
                "status": "healthy" if bot_accessible else "error",
                "bot_accessible": bot_accessible,
                "bot_username": bot_username,
                "running": self.running,
                "stats": self.stats,
                "limitation": "Bot API получает только сообщения где бот упомянут"
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики мониторинга"""
        return {
            **self.stats,
            "processed_messages_cache": len(self.processed_messages),
            "running": self.running,
            "api_type": "bot_api"
        }


# Глобальный экземпляр Bot API монитора
telegram_monitor = TelegramBotAPIMonitor() if TELEGRAM_BOT_AVAILABLE else None