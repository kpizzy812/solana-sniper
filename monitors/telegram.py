import asyncio
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters
from loguru import logger
import aiohttp

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
    """Ультра-быстрый мониторинг Telegram с интервалом 1 секунда"""

    def __init__(self, trading_callback=None):
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.trading_callback = trading_callback

        # Отслеживание
        self.monitored_chats: Set[str] = set()
        self.last_message_ids: Dict[int, int] = {}  # chat_id -> last_message_id
        self.processed_messages: Set[str] = set()  # Предотвращение дублирования

        # Производительность
        self.running = False
        self.last_check_time = 0
        self.check_interval = settings.monitoring.telegram_interval

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
            # Инициализация бота
            self.bot = Bot(token=settings.monitoring.telegram_bot_token)
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

            # Запуск цикла мониторинга
            self.running = True
            asyncio.create_task(self.monitoring_loop())

            logger.success("✅ Высокоскоростной Telegram монитор запущен")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram монитора: {e}")
            return False

    async def stop(self):
        """Остановка монитора"""
        self.running = False
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
        logger.info("🛑 Telegram монитор остановлен")

    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        # Обработка всех сообщений (каналы и группы)
        self.app.add_handler(MessageHandler(
            filters.ALL,
            self.handle_message
        ))

        # Обработка отредактированных сообщений
        self.app.add_handler(MessageHandler(
            filters.ALL,
            self.handle_edited_message
        ))

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

        # Настройка групп (включая топики)
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

    async def monitoring_loop(self):
        """Основной цикл мониторинга - проверка каждую секунду"""
        logger.info("🔍 Запуск высокоскоростного цикла мониторинга (интервал 1 секунда)")

        while self.running:
            try:
                start_time = time.time()

                # Проверяем новые сообщения во всех отслеживаемых чатах
                await self.check_new_messages()

                # Обновляем статистику времени
                processing_time = time.time() - start_time
                self.stats['avg_processing_time'] = (
                        self.stats['avg_processing_time'] * 0.9 + processing_time * 0.1
                )

                # Ждем оставшееся время для поддержания интервала в 1 секунду
                sleep_time = max(0, self.check_interval - processing_time)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"⚠️ Цикл мониторинга превышает время: {processing_time:.3f}s")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(1)  # Предотвращение быстрого повтора ошибок

    async def check_new_messages(self):
        """Проверка новых сообщений во всех отслеживаемых чатах"""
        tasks = []

        for channel in self.monitored_chats:
            task = asyncio.create_task(self.check_channel_messages(channel))
            tasks.append(task)

        # Ждем завершения проверки всех каналов
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_channel_messages(self, channel: str):
        """Проверка новых сообщений в конкретном канале"""
        try:
            # Получаем последние обновления из канала
            updates = await self.bot.get_updates(
                offset=-1,  # Получаем только последнее обновление
                limit=100,
                timeout=1
            )

            for update in updates:
                if update.message or update.edited_message:
                    message = update.message or update.edited_message

                    # Проверяем, относится ли это сообщение к отслеживаемому чату
                    if self.is_monitored_chat(message.chat):
                        await self.process_message(message, update.edited_message is not None)

        except Exception as e:
            logger.debug(f"Ошибка проверки канала {channel}: {e}")

    def is_monitored_chat(self, chat) -> bool:
        """Проверка, отслеживается ли чат"""
        chat_identifier = f"@{chat.username}" if chat.username else str(chat.id)
        return chat_identifier in self.monitored_chats

    async def handle_message(self, update: Update, context):
        """Обработка новых сообщений"""
        if update.message:
            await self.process_message(update.message, is_edit=False)

    async def handle_edited_message(self, update: Update, context):
        """Обработка отредактированных сообщений"""
        if update.edited_message:
            await self.process_message(update.edited_message, is_edit=True)

    async def process_message(self, message, is_edit: bool = False):
        """Обработка одного сообщения с максимальной скоростью"""
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

            # Проверяем топики (если поддерживаются)
            thread_id = None
            if hasattr(message, 'message_thread_id') and message.message_thread_id:
                thread_id = message.message_thread_id
                logger.info(f"📍 Сообщение в топике {thread_id}")

            # Извлекаем данные поста
            post = await self.extract_post_data(message, is_edit, is_admin_msg, thread_id)

            # УЛЬТРА-БЫСТРЫЙ АНАЛИЗ
            analysis_result = await analyzer.analyze_post(
                content=post.content,
                platform="telegram",
                author=post.author,
                url=post.url
            )

            processing_time = (time.time() - start_time) * 1000

            logger.info(f"📱 Обработано Telegram сообщение за {processing_time:.1f}ms | "
                        f"Контракт: {analysis_result.has_contract} | "
                        f"Уверенность: {analysis_result.confidence:.2f} | "
                        f"Админ: {is_admin_msg}")

            # Если обнаружен контракт с высокой уверенностью, запускаем торговлю немедленно
            if analysis_result.has_contract and analysis_result.confidence > 0.6:
                logger.critical(f"🚨 КОНТРАКТ ОБНАРУЖЕН: {analysis_result.addresses}")

                if self.trading_callback:
                    # Fire and forget - не ждем завершения торговли
                    asyncio.create_task(self.trigger_trading(analysis_result, post))

                self.stats['contracts_found'] += 1

            # Отмечаем как обработанное
            self.processed_messages.add(message_key)
            self.stats['messages_processed'] += 1

            # Очистка старых обработанных сообщений (предотвращение утечки памяти)
            if len(self.processed_messages) > 10000:
                # Удаляем 1000 самых старых записей
                old_messages = list(self.processed_messages)[:1000]
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

                # Проверяем статус в чате
                try:
                    member = await self.bot.get_chat_member(message.chat.id, message.from_user.id)
                    if member.status in ['creator', 'administrator']:
                        logger.info(f"✅ Админ сообщение от @{username or 'unknown'} ({member.status})")
                        return True
                except:
                    # Если не удалось получить статус, проверяем по списку админов
                    pass

            return False

        except Exception as e:
            logger.debug(f"Ошибка проверки админа: {e}")
            return False  # По умолчанию не админ

    async def extract_post_data(self, message, is_edit: bool, is_admin: bool, thread_id: Optional[int]) -> TelegramPost:
        """Извлечение структурированных данных из сообщения Telegram"""
        # Получаем содержимое сообщения
        content = message.text or message.caption or ""

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

        # Извлекаем URL медиа
        media_urls = []
        if message.photo:
            # Получаем фото самого высокого разрешения
            photo = max(message.photo, key=lambda p: p.file_size or 0)
            try:
                file = await self.bot.get_file(photo.file_id)
                media_urls.append(file.file_path)
            except:
                pass

        if message.document:
            try:
                file = await self.bot.get_file(message.document.file_id)
                media_urls.append(file.file_path)
            except:
                pass

        return TelegramPost(
            message_id=message.message_id,
            chat_id=message.chat.id,
            chat_username=chat_username or str(message.chat.id),
            content=content,
            author=author,
            timestamp=message.date,
            url=url,
            is_edit=is_edit,
            media_urls=media_urls,
            is_admin=is_admin,
            thread_id=thread_id
        )

    async def trigger_trading(self, analysis_result, post: TelegramPost):
        """Запуск торговой системы немедленно"""
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

            # Вызываем торговую систему
            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"❌ Ошибка торгового обратного вызова: {e}")

    async def health_check(self) -> Dict:
        """Проверка здоровья монитора"""
        try:
            if not self.bot:
                return {"status": "error", "message": "Бот не инициализирован"}

            # Тестируем подключение бота
            me = await self.bot.get_me()

            return {
                "status": "healthy",
                "bot_username": me.username,
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
            "running": self.running,
            "check_interval": self.check_interval
        }


# Создание глобального экземпляра монитора
telegram_monitor = HighSpeedTelegramMonitor()