import asyncio
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
from loguru import logger

from config.settings import settings
from ai.analyzer import analyzer


@dataclass
class TelegramPost:
    """Структура данных поста Telegram"""
    message_id: int
    chat_id: int
    chat_username: str
    content: str
    author: str
    timestamp: datetime
    url: str
    is_edit: bool = False
    media_urls: List[str] = None
    is_admin: bool = False
    thread_id: Optional[int] = None


class HighSpeedTelegramMonitor:
    """Простой и надежный мониторинг Telegram"""

    def __init__(self, trading_callback=None):
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.trading_callback = trading_callback

        # Отслеживание
        self.monitored_chats: Set[str] = set()
        self.processed_messages: Set[str] = set()

        # Производительность
        self.running = False

        # Статистика
        self.stats = {
            'messages_processed': 0,
            'contracts_found': 0,
            'admin_messages': 0,
            'regular_messages': 0,
            'errors': 0,
            'avg_processing_time': 0
        }

    async def start(self) -> bool:
        """Инициализация и запуск мониторинга Telegram"""
        if not settings.monitoring.telegram_bot_token:
            logger.warning("⚠️ Telegram bot token не настроен")
            return False

        try:
            # Простая инициализация бота
            self.bot = Bot(token=settings.monitoring.telegram_bot_token)

            # Простое создание приложения
            self.app = Application.builder().token(settings.monitoring.telegram_bot_token).build()

            # Настройка обработчиков
            self.setup_handlers()

            # Запуск приложения
            await self.app.initialize()
            await self.app.start()

            # Проверка подключения бота
            me = await self.bot.get_me()
            logger.info(f"📱 Telegram бот запущен: @{me.username}")

            # Подключение к каналам мониторинга
            await self.setup_monitoring_channels()

            # Запуск мониторинга
            self.running = True
            asyncio.create_task(self.run_bot())

            logger.success("✅ Telegram монитор запущен")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram монитора: {e}")
            return False

    async def stop(self):
        """Остановка монитора"""
        self.running = False
        if self.app:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.debug(f"Ошибка остановки app: {e}")
        logger.info("🛑 Telegram монитор остановлен")

    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        # Обработка всех сообщений
        message_handler = MessageHandler(filters.ALL, self.handle_message)
        self.app.add_handler(message_handler)

    async def setup_monitoring_channels(self):
        """Настройка каналов и групп для мониторинга"""
        # Настройка каналов
        for channel in settings.monitoring.telegram_channels:
            if not channel:
                continue
            try:
                if channel.startswith('@'):
                    chat = await self.bot.get_chat(channel)
                    self.monitored_chats.add(channel)
                    logger.info(f"📺 Мониторинг Telegram канала: {channel}")
                else:
                    # Пробуем как chat ID
                    chat_id = int(channel)
                    chat = await self.bot.get_chat(chat_id)
                    self.monitored_chats.add(str(chat_id))
                    logger.info(f"📺 Мониторинг Telegram чата: {chat_id}")

            except Exception as e:
                logger.error(f"❌ Ошибка настройки мониторинга {channel}: {e}")

        # Настройка групп
        for group in settings.monitoring.telegram_groups:
            if not group:
                continue
            try:
                if group.startswith('@'):
                    chat = await self.bot.get_chat(group)
                    self.monitored_chats.add(group)
                    logger.info(f"👥 Мониторинг Telegram группы: {group}")

                    # Проверяем поддержку топиков
                    if hasattr(chat, 'is_forum') and chat.is_forum:
                        logger.info(f"📍 Группа {group} поддерживает топики")
                else:
                    # Пробуем как chat ID
                    chat_id = int(group)
                    chat = await self.bot.get_chat(chat_id)
                    self.monitored_chats.add(str(chat_id))
                    logger.info(f"👥 Мониторинг Telegram группы: {chat_id}")

            except Exception as e:
                logger.error(f"❌ Ошибка настройки мониторинга группы {group}: {e}")

        logger.info(f"✅ Настроено мониторинга для {len(self.monitored_chats)} чатов")

    async def run_bot(self):
        """Запуск бота с polling"""
        logger.info("🔍 Запуск Telegram polling...")

        try:
            # Запускаем polling
            await self.app.updater.start_polling(
                poll_interval=2.0,  # Каждые 2 секунды
                timeout=20,
                bootstrap_retries=-1
            )

            # Ждем пока бот работает
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}")
            # Fallback на manual polling если не работает
            await self.manual_polling()
        finally:
            try:
                await self.app.updater.stop()
            except:
                pass

    async def manual_polling(self):
        """Ручной polling если автоматический не работает"""
        logger.info("🔄 Переключение на ручной polling...")

        last_update_id = 0

        while self.running:
            try:
                # Получаем обновления
                updates = await self.bot.get_updates(
                    offset=last_update_id + 1,
                    timeout=10,
                    limit=100
                )

                for update in updates:
                    last_update_id = update.update_id

                    # Обрабатываем сообщения
                    if update.message:
                        await self.handle_message_direct(update.message, is_edit=False)
                    elif update.edited_message:
                        await self.handle_message_direct(update.edited_message, is_edit=True)

                # Небольшая пауза между запросами
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"❌ Ошибка manual polling: {e}")
                await asyncio.sleep(5)

    def is_monitored_chat(self, chat) -> bool:
        """Проверка, отслеживается ли чат"""
        chat_identifier = f"@{chat.username}" if chat.username else str(chat.id)
        return chat_identifier in self.monitored_chats

    async def handle_message(self, update: Update, context: CallbackContext):
        """Обработка новых сообщений через handler"""
        if update.message and self.is_monitored_chat(update.message.chat):
            await self.handle_message_direct(update.message, is_edit=False)
        elif update.edited_message and self.is_monitored_chat(update.edited_message.chat):
            await self.handle_message_direct(update.edited_message, is_edit=True)

    async def handle_message_direct(self, message, is_edit: bool = False):
        """Прямая обработка сообщения"""
        try:
            start_time = time.time()

            # Создаем уникальный идентификатор сообщения
            message_key = f"{message.chat.id}:{message.message_id}:{is_edit}"

            # Пропускаем уже обработанные
            if message_key in self.processed_messages:
                return

            # Проверяем, является ли отправитель админом (только для групп)
            is_admin_msg = False
            if message.chat.type in ['group', 'supergroup']:
                is_admin_msg = await self.check_if_admin_message(message)
                if not is_admin_msg:
                    logger.debug(f"📱 Пропускаем сообщение не от админа в {message.chat.title or message.chat.id}")
                    self.stats['regular_messages'] += 1
                    return
                else:
                    self.stats['admin_messages'] += 1

            # Проверяем топики
            thread_id = None
            if hasattr(message, 'message_thread_id') and message.message_thread_id:
                thread_id = message.message_thread_id
                logger.info(f"📍 Сообщение в топике {thread_id}")

            # Извлекаем данные поста
            post = await self.extract_post_data(message, is_edit, is_admin_msg, thread_id)

            # Быстрый анализ
            analysis_result = await analyzer.analyze_post(
                content=post.content,
                platform="telegram",
                author=post.author,
                url=post.url
            )

            processing_time = (time.time() - start_time) * 1000

            logger.info(f"📱 Telegram сообщение ({processing_time:.1f}ms): "
                        f"контракт={analysis_result.has_contract} | "
                        f"уверенность={analysis_result.confidence:.2f}")

            # Если обнаружен контракт с высокой уверенностью
            if analysis_result.has_contract and analysis_result.confidence > 0.6:
                logger.critical(f"🚨 КОНТРАКТ ОБНАРУЖЕН: {analysis_result.addresses}")

                if self.trading_callback:
                    asyncio.create_task(self.trigger_trading(analysis_result, post))

                self.stats['contracts_found'] += 1

            # Отмечаем как обработанное
            self.processed_messages.add(message_key)
            self.stats['messages_processed'] += 1

            # Очистка памяти
            if len(self.processed_messages) > 1000:
                old_messages = list(self.processed_messages)[:200]
                for old_msg in old_messages:
                    self.processed_messages.discard(old_msg)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки Telegram сообщения: {e}")
            self.stats['errors'] += 1

    async def check_if_admin_message(self, message) -> bool:
        """Проверка, является ли сообщение от админа"""
        try:
            # Для каналов - все сообщения считаем админскими
            if message.chat.type == 'channel':
                return True

            # Для групп - проверяем статус отправителя
            if message.from_user:
                # Проверяем по username
                username = message.from_user.username
                if username:
                    from config.settings import is_admin_message
                    if is_admin_message(username, message.from_user.id):
                        return True

                # Проверяем статус в чате (с защитой от ошибок)
                try:
                    member = await self.bot.get_chat_member(message.chat.id, message.from_user.id)
                    if member.status in ['creator', 'administrator']:
                        logger.info(f"✅ Админ сообщение от @{username or 'unknown'} ({member.status})")
                        return True
                except Exception as e:
                    logger.debug(f"Не удалось проверить статус в чате: {e}")

            return False

        except Exception as e:
            logger.debug(f"Ошибка проверки админа: {e}")
            return False

    async def extract_post_data(self, message, is_edit: bool, is_admin: bool, thread_id: Optional[int]) -> TelegramPost:
        """Извлечение данных из сообщения Telegram"""
        # Получаем основное содержимое сообщения
        content = message.text or message.caption or ""

        # ВАЖНО: Извлекаем URL из entities (гиперссылки)
        full_content = content

        if message.entities:
            for entity in message.entities:
                if entity.type in ['url', 'text_link']:
                    if entity.type == 'url':
                        # Прямая ссылка в тексте
                        url_text = content[entity.offset:entity.offset + entity.length]
                        full_content += f" {url_text}"
                        logger.debug(f"📎 Найдена URL в тексте: {url_text}")
                    elif entity.type == 'text_link':
                        # Гиперссылка с текстом
                        url_text = entity.url
                        full_content += f" {url_text}"
                        logger.debug(f"📎 Найдена гиперссылка: {url_text}")

        # Также проверяем caption entities для медиа
        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type in ['url', 'text_link']:
                    if entity.type == 'url':
                        url_text = (message.caption or "")[entity.offset:entity.offset + entity.length]
                        full_content += f" {url_text}"
                        logger.debug(f"📎 Найдена URL в caption: {url_text}")
                    elif entity.type == 'text_link':
                        url_text = entity.url
                        full_content += f" {url_text}"
                        logger.debug(f"📎 Найдена гиперссылка в caption: {url_text}")

        # Логируем полный контент для отладки
        logger.debug(f"📝 Полный контент сообщения: {full_content}")

        # Получаем информацию об авторе
        author = "Unknown"
        if message.from_user:
            author = message.from_user.username or f"{message.from_user.first_name}"
        elif message.sender_chat:
            author = message.sender_chat.title or "Channel"

        # Генерируем URL сообщения
        chat_username = message.chat.username
        url = ""
        if chat_username:
            url = f"https://t.me/{chat_username}/{message.message_id}"

        # Извлекаем URL медиа (с защитой от ошибок)
        media_urls = []
        try:
            if message.photo:
                photo = max(message.photo, key=lambda p: p.file_size or 0)
                file = await self.bot.get_file(photo.file_id)
                media_urls.append(file.file_path)
        except Exception as e:
            logger.debug(f"Ошибка получения фото: {e}")

        try:
            if message.document:
                file = await self.bot.get_file(message.document.file_id)
                media_urls.append(file.file_path)
        except Exception as e:
            logger.debug(f"Ошибка получения документа: {e}")

        return TelegramPost(
            message_id=message.message_id,
            chat_id=message.chat.id,
            chat_username=chat_username or str(message.chat.id),
            content=full_content,  # Используем полный контент с URL
            author=author,
            timestamp=message.date,
            url=url,
            is_edit=is_edit,
            media_urls=media_urls,
            is_admin=is_admin,
            thread_id=thread_id
        )

    async def trigger_trading(self, analysis_result, post: TelegramPost):
        """Запуск торговой системы"""
        try:
            trading_data = {
                'platform': 'telegram',
                'source': post.chat_username,
                'author': post.author,
                'url': post.url,
                'contracts': analysis_result.addresses,
                'confidence': analysis_result.confidence,
                'urgency': analysis_result.urgency,
                'timestamp': post.timestamp,
                'content_preview': post.content[:200],
                'is_admin': post.is_admin,
                'thread_id': post.thread_id
            }

            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"❌ Ошибка торгового вызова: {e}")

    async def health_check(self) -> Dict:
        """Проверка здоровья монитора"""
        try:
            if not self.bot:
                return {"status": "error", "message": "Бот не инициализирован"}

            try:
                me = await asyncio.wait_for(self.bot.get_me(), timeout=5.0)
                bot_healthy = True
            except:
                bot_healthy = False

            return {
                "status": "healthy" if bot_healthy else "degraded",
                "bot_username": me.username if bot_healthy else "unknown",
                "monitored_channels": len(self.monitored_chats),
                "running": self.running,
                "stats": self.stats
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики мониторинга"""
        return {
            **self.stats,
            "monitored_channels": len(self.monitored_chats),
            "processed_messages_cache": len(self.processed_messages),
            "running": self.running
        }


# Создание глобального экземпляра монитора
telegram_monitor = HighSpeedTelegramMonitor()