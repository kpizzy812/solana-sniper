import asyncio
import time
import re
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

# Улучшенная диагностика Telethon импортов
TELETHON_AVAILABLE = False
TelegramClient = None
events = None
types = None

logger.info("🔍 Проверяем доступность Telethon...")

try:
    from telethon import TelegramClient, events, types

    logger.success("✅ Основные Telethon модули импортированы")

    # Импортируем TL types
    try:
        from telethon.tl.types import Channel, Chat, User, Message

        logger.success("✅ Базовые TL types импортированы")
    except ImportError as e:
        logger.warning(f"⚠️ Базовые TL types недоступны: {e}")

    # Импортируем медиа типы
    try:
        from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

        logger.success("✅ Медиа TL types импортированы")
    except ImportError as e:
        logger.debug(f"ℹ️ Медиа TL types недоступны (не критично): {e}")
        MessageMediaDocument = None
        MessageMediaPhoto = None

    # Импортируем errors
    try:
        from telethon.errors import (
            SessionPasswordNeededError, PhoneCodeInvalidError,
            PhoneNumberInvalidError, FloodWaitError, ChannelPrivateError,
            AuthKeyUnregisteredError, UserDeactivatedError
        )

        logger.success("✅ Telethon errors импортированы")
    except ImportError as e:
        logger.warning(f"⚠️ Некоторые Telethon errors недоступны: {e}")

    TELETHON_AVAILABLE = True
    logger.critical("🎯 TELETHON ДОСТУПЕН - User Bot может работать!")

except ImportError as e:
    logger.error(f"❌ Telethon недоступен: {e}")
    logger.error("💡 Установите: pip install telethon")
    TELETHON_AVAILABLE = False

from config.settings import settings, is_admin_message
from ai.analyzer import analyzer


@dataclass
class TelegramUserPost:
    """Данные сообщения от User Bot"""
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
    has_media: bool = False
    reply_to_msg_id: Optional[int] = None
    is_topic: bool = False
    topic_id: Optional[int] = None


class UltraFastTelegramUserMonitor:
    """Ультра-быстрый мониторинг Telegram через User Bot API"""

    def __init__(self, trading_callback=None):
        self.trading_callback = trading_callback
        self.client: Optional[TelegramClient] = None

        # Детальная диагностика настроек
        logger.info("🔧 Проверяем настройки User Bot...")
        logger.info(f"📱 USE_TELEGRAM_USER_BOT: {settings.monitoring.use_user_bot}")
        logger.info(f"🤖 USE_TELEGRAM_BOT_API: {settings.monitoring.use_bot_api}")
        logger.info(f"🆔 TELEGRAM_API_ID: {'✅ Есть' if settings.monitoring.telegram_api_id else '❌ Нет'}")
        logger.info(f"🔑 TELEGRAM_API_HASH: {'✅ Есть' if settings.monitoring.telegram_api_hash else '❌ Нет'}")
        logger.info(f"📞 TELEGRAM_PHONE_NUMBER: {'✅ Есть' if settings.monitoring.telegram_phone_number else '❌ Нет'}")

        # Проверяем доступность библиотеки
        if not TELETHON_AVAILABLE:
            logger.error("❌ Telethon не установлен! User Bot недоступен!")
            logger.error("💡 Установите: pip install telethon")
            return

        # Отслеживание обработанных сообщений
        self.processed_messages: Set[int] = set()  # message_id
        self.chat_entities: Dict[str, Union[Channel, Chat]] = {}  # username -> entity
        self.chat_entities_by_id: Dict[int, Union[Channel, Chat]] = {}  # chat_id -> entity
        self.chat_id_mapping: Dict[int, str] = {}  # chat_id -> username для логирования
        self.user_entities: Dict[int, User] = {}  # user_id -> User

        # Производительность
        self.running = False
        self.session_file = f"{settings.monitoring.telegram_session_name}.session"

        # Статистика
        self.stats = {
            'messages_processed': 0,
            'contracts_found': 0,
            'channels_monitored': 0,
            'groups_monitored': 0,
            'connections': 0,
            'errors': 0,
            'auth_attempts': 0
        }

        # Rate limiting
        self.last_message_time = {}  # chat_id -> timestamp для избежания спама

        logger.info(f"🎯 User Bot инициализирован (Telethon: {TELETHON_AVAILABLE})")

    @staticmethod
    def normalize_chat_ids(original_id: int) -> List[int]:
        """Возвращает все возможные варианты ID чата"""
        ids = [original_id]

        # Если ID положительный, добавляем версию с префиксом -100
        if original_id > 0:
            prefixed_id = int(f"-100{original_id}")
            ids.append(prefixed_id)

        # Если ID отрицательный с префиксом -100, добавляем версию без префикса
        elif str(original_id).startswith("-100"):
            clean_id = int(str(original_id)[4:])  # убираем -100
            ids.append(clean_id)

        return ids

    def test_chat_id_matching(self, test_id: int) -> bool:
        """Тестирование соответствия ID чата (для диагностики)"""
        logger.debug(f"🧪 Тестируем ID: {test_id}")

        # Прямое соответствие
        if test_id in self.chat_entities_by_id:
            logger.debug(f"✅ Прямое соответствие найдено для {test_id}")
            return True

        # Поиск среди всех нормализованных вариантов
        all_normalized = self.normalize_chat_ids(test_id)
        logger.debug(f"🔄 Нормализованные варианты: {all_normalized}")

        for normalized_id in all_normalized:
            if normalized_id in self.chat_entities_by_id:
                logger.debug(f"✅ Соответствие найдено для нормализованного ID {normalized_id}")
                return True

        logger.debug(f"❌ Соответствия не найдены для {test_id}")
        logger.debug(f"📋 Доступные ID: {sorted(self.chat_entities_by_id.keys())}")
        return False

    def is_available(self) -> bool:
        """Проверка доступности User Bot"""
        return TELETHON_AVAILABLE

    async def start(self) -> bool:
        """Запуск мониторинга Telegram User Bot"""
        logger.critical("🚀 ЗАПУСК TELEGRAM USER BOT!")

        if not TELETHON_AVAILABLE:
            logger.error("❌ Telethon недоступен - User Bot не может работать")
            return False

        if not settings.monitoring.telegram_api_id or not settings.monitoring.telegram_api_hash:
            logger.error("❌ Telegram API ID/Hash не настроены")
            logger.error("💡 Проверьте TELEGRAM_API_ID и TELEGRAM_API_HASH в .env")
            return False

        if not settings.monitoring.telegram_phone_number:
            logger.error("❌ TELEGRAM_PHONE_NUMBER не настроен")
            return False

        try:
            # Детальная диагностика перед запуском
            logger.info("🔧 Диагностика User Bot:")
            logger.info(f"   📁 Session file: {self.session_file}")
            logger.info(f"   🆔 API ID: {settings.monitoring.telegram_api_id}")
            logger.info(f"   📞 Phone: {settings.monitoring.telegram_phone_number}")
            logger.info(f"   📺 Каналы: {[ch for ch in settings.monitoring.user_bot_channels if ch]}")
            logger.info(f"   👥 Группы: {[gr for gr in settings.monitoring.user_bot_groups if gr]}")

            # Инициализация клиента Telethon
            logger.info("⚡ Создаем Telegram клиент...")

            self.client = TelegramClient(
                session=self.session_file,
                api_id=int(settings.monitoring.telegram_api_id),
                api_hash=settings.monitoring.telegram_api_hash,
                device_model="MORI Sniper Bot",
                system_version="1.0",
                app_version="1.0",
                lang_code="en",
                system_lang_code="en"
            )

            # Подключение к Telegram
            logger.info("🔌 Подключаемся к Telegram...")
            await self.client.start(phone=settings.monitoring.telegram_phone_number)

            # Проверяем авторизацию
            if not await self.client.is_user_authorized():
                logger.error("❌ Не удалось авторизоваться в Telegram")
                logger.error("💡 Возможно нужно заново пройти авторизацию")
                return False

            # Получаем информацию о пользователе
            me = await self.client.get_me()
            logger.success(f"✅ Авторизован как: @{me.username} ({me.first_name} {me.last_name or ''})")
            logger.success(f"🆔 User ID: {me.id}")

            # Получаем entities каналов и групп
            await self.get_chat_entities()

            if len(self.chat_entities) == 0:
                logger.warning("⚠️ Нет доступных чатов для мониторинга!")
                logger.warning("💡 Проверьте что бот добавлен в каналы/группы")

            # Настраиваем обработчики событий
            self.setup_event_handlers()

            # Запускаем мониторинг
            self.running = True

            logger.critical("🔥 TELEGRAM USER BOT АКТИВЕН!")
            logger.critical(
                f"📍 Мониторим {self.stats['channels_monitored']} каналов и {self.stats['groups_monitored']} групп")
            logger.critical("🎯 Ожидаем новые сообщения...")

            return True

        except SessionPasswordNeededError:
            logger.error("❌ Требуется двухфакторная аутентификация")
            logger.error("💡 Введите пароль от Telegram аккаунта")
            return False
        except PhoneNumberInvalidError:
            logger.error("❌ Неверный номер телефона")
            return False
        except AuthKeyUnregisteredError:
            logger.error("❌ Сессия устарела, нужна повторная авторизация")
            logger.error("💡 Удалите .session файл и перезапустите")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram User Bot: {e}")
            logger.error(f"🔍 Тип ошибки: {type(e).__name__}")
            return False

    async def stop(self):
        """Остановка монитора"""
        self.running = False
        if self.client:
            try:
                await self.client.disconnect()
                logger.info("🛑 Telegram User Bot отключен")
            except Exception as e:
                logger.warning(f"Ошибка отключения User Bot: {e}")

    async def get_chat_entities(self):
        """Получение entities каналов и групп для мониторинга"""
        logger.info("📡 Получение информации о каналах и группах...")

        # Обрабатываем каналы
        channels_to_monitor = [ch for ch in settings.monitoring.user_bot_channels if ch]
        logger.info(f"📺 Проверяем каналы: {channels_to_monitor}")

        for channel in channels_to_monitor:
            try:
                logger.debug(f"🔍 Получаем канал: {channel}")
                entity = await self.client.get_entity(channel)

                # Сохраняем entity по username И по ВСЕМ возможным вариантам ID
                self.chat_entities[channel] = entity

                # Получаем все возможные варианты ID
                all_ids = self.normalize_chat_ids(entity.id)
                for chat_id in all_ids:
                    self.chat_entities_by_id[chat_id] = entity
                    self.chat_id_mapping[chat_id] = channel

                self.stats['channels_monitored'] += 1

                all_ids = self.normalize_chat_ids(entity.id)
                ids_str = " / ".join(map(str, all_ids))
                logger.success(
                    f"✅ Канал: {entity.title} (@{getattr(entity, 'username', 'N/A')}) - ID: {ids_str} - {getattr(entity, 'participants_count', 'N/A')} участников")

            except ChannelPrivateError:
                logger.warning(f"⚠️ Приватный канал {channel} - нет доступа")
            except ValueError as e:
                logger.error(f"❌ Неверный канал {channel}: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения канала {channel}: {e}")

        # Обрабатываем группы
        groups_to_monitor = [gr for gr in settings.monitoring.user_bot_groups if gr]
        logger.info(f"👥 Проверяем группы: {groups_to_monitor}")

        for group in groups_to_monitor:
            try:
                logger.debug(f"🔍 Получаем группу: {group}")
                entity = await self.client.get_entity(group)

                # Сохраняем entity по username И по ВСЕМ возможным вариантам ID
                self.chat_entities[group] = entity

                # Получаем все возможные варианты ID
                all_ids = self.normalize_chat_ids(entity.id)
                for chat_id in all_ids:
                    self.chat_entities_by_id[chat_id] = entity
                    self.chat_id_mapping[chat_id] = group

                self.stats['groups_monitored'] += 1

                logger.success(
                    f"✅ Группа: {getattr(entity, 'title', 'N/A')} (@{getattr(entity, 'username', 'private')}) - ID: {entity.id} - {getattr(entity, 'participants_count', 'N/A')} участников")

            except ChannelPrivateError:
                logger.warning(f"⚠️ Приватная группа {group} - нет доступа")
            except ValueError as e:
                logger.error(f"❌ Неверная группа {group}: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения группы {group}: {e}")

        logger.success(f"🎯 Получено {len(self.chat_entities)} чатов для мониторинга")

        # НОВОЕ: Обрабатываем ЛС для мониторинга
        if settings.monitoring.monitor_private_messages:
            dm_usernames = [dm for dm in settings.monitoring.user_bot_dm_usernames if dm]
            logger.info(f"💬 Проверяем ЛС с: {dm_usernames}")

            for dm_username in dm_usernames:
                try:
                    logger.debug(f"🔍 Получаем ЛС с: {dm_username}")

                    # Очищаем username от @
                    clean_username = dm_username.replace('@', '')

                    # Для ЛС используем username напрямую
                    entity = await self.client.get_entity(clean_username)

                    # Сохраняем entity
                    self.chat_entities[dm_username] = entity

                    # Получаем все возможные варианты ID для ЛС
                    all_ids = self.normalize_chat_ids(entity.id)
                    for chat_id in all_ids:
                        self.chat_entities_by_id[chat_id] = entity
                        self.chat_id_mapping[chat_id] = dm_username

                    logger.success(
                        f"✅ ЛС: {getattr(entity, 'first_name', 'Unknown')} (@{getattr(entity, 'username', dm_username)}) - ID: {entity.id}")

                except Exception as e:
                    logger.error(f"❌ Ошибка получения ЛС с {dm_username}: {e}")

        # Детальная информация о мониторинге
        logger.critical("📍 МОНИТОРИМЫЕ ЧАТЫ:")
        for identifier, entity in self.chat_entities.items():
            all_ids = self.normalize_chat_ids(entity.id)
            ids_str = " / ".join(map(str, all_ids))
            logger.critical(f"   🎯 {identifier} -> {getattr(entity, 'title', 'N/A')} (ID: {ids_str})")

        logger.critical("🆔 ВСЕ МАППИНГИ ID -> USERNAME:")
        for chat_id, username in sorted(self.chat_id_mapping.items()):
            logger.critical(f"   🔗 {chat_id} -> {username}")

        logger.critical(f"📊 ВСЕГО МАППИНГОВ: {len(self.chat_id_mapping)}")

        if len(self.chat_entities_by_id) == 0:
            logger.error("❌ НЕТ ДОСТУПНЫХ ЧАТОВ! Проверьте:")
            logger.error("   1. Что User Bot добавлен в каналы/группы")
            logger.error("   2. Что каналы/группы публичные или бот имеет доступ")

    def setup_event_handlers(self):
        """Настройка обработчиков событий Telethon"""
        logger.info("⚡ Настраиваем обработчики событий...")

        @self.client.on(events.NewMessage())
        async def handle_new_message(event):
            """Обработчик новых сообщений"""
            try:
                # Логируем ВСЕ входящие сообщения для диагностики
                chat_id = event.chat_id
                message_id = event.message.id
                logger.debug(f"📥 Получено сообщение: chat_id={chat_id}, message_id={message_id}")

                # Ищем entity по ID чата (ИСПРАВЛЕНО!)
                target_entity = self.chat_entities_by_id.get(chat_id)
                chat_identifier = self.chat_id_mapping.get(chat_id, f"ID:{chat_id}")

                if not target_entity:
                    # Детальная диагностика для НЕ мониторимых чатов
                    logger.debug(f"⏭️ Сообщение НЕ из мониторимого чата: {chat_id}")
                    logger.debug(f"   📋 Мониторимые ID: {sorted(self.chat_entities_by_id.keys())}")
                    logger.debug(f"   🔍 Попробуем найти похожие ID...")

                    # Попробуем найти похожие ID для диагностики
                    for stored_id in self.chat_entities_by_id.keys():
                        if abs(stored_id) == abs(chat_id) or str(stored_id) in str(chat_id) or str(chat_id) in str(
                                stored_id):
                            logger.debug(f"   🔎 Похожий ID найден: {stored_id}")

                    return

                logger.critical(f"🎯 СООБЩЕНИЕ ИЗ МОНИТОРИМОГО ЧАТА!")
                logger.critical(f"   📍 Chat ID: {chat_id}")
                logger.critical(f"   🏷️ Identifier: {chat_identifier}")
                logger.critical(f"   📝 Message ID: {message_id}")

                # Обрабатываем сообщение
                await self.process_message(event, target_entity, chat_identifier)

            except Exception as e:
                logger.error(f"❌ Ошибка обработки сообщения: {e}")
                self.stats['errors'] += 1

        logger.success("✅ Обработчики событий настроены")

    async def process_message(self, event, chat_entity, chat_identifier: str):
        """Обработка одного сообщения"""
        try:
            message = event.message

            logger.debug(f"🔍 Обрабатываем сообщение {message.id} из {chat_identifier}")

            # Пропускаем уже обработанные
            message_unique_id = hash(f"{message.chat_id}:{message.id}:{message.date}")
            if message_unique_id in self.processed_messages:
                logger.debug(f"⏭️ Сообщение {message.id} уже обработано")
                return

            # Получаем информацию об авторе
            sender = await event.get_sender()
            if not sender:
                logger.debug(f"⏭️ Не удалось получить отправителя для {message.id}")
                return

            # Проверяем rate limiting для чата
            now = time.time()
            last_time = self.last_message_time.get(message.chat_id, 0)
            if now - last_time < 0.1:  # Не чаще 10 сообщений в секунду на чат
                logger.debug(f"⏭️ Rate limiting для чата {message.chat_id}")
                return
            self.last_message_time[message.chat_id] = now

            # Определяем тип чата
            message_type = 'group'  # по умолчанию
            try:
                if hasattr(chat_entity, 'broadcast') and chat_entity.broadcast:
                    message_type = 'channel'
                elif hasattr(chat_entity, 'megagroup'):
                    message_type = 'group'
                else:
                    # Проверяем если это приватный чат (ЛС)
                    if not hasattr(chat_entity, 'title'):  # У приватных чатов нет title
                        message_type = 'private'
            except Exception as e:
                logger.debug(f"Не удалось определить тип чата: {e}")

            # Формируем данные поста
            post = TelegramUserPost(
                message_id=message.id,
                chat_id=message.chat_id,
                chat_title=getattr(chat_entity, 'title', 'Unknown'),
                chat_username=getattr(chat_entity, 'username', ''),
                author_id=sender.id,
                author_username=getattr(sender, 'username', ''),
                author_first_name=getattr(sender, 'first_name', ''),
                content=message.text or '',
                timestamp=message.date,
                url=f"https://t.me/{getattr(chat_entity, 'username', 'c')}/{message.id}",
                message_type=message_type,
                is_admin=is_admin_message(getattr(sender, 'username', ''), sender.id),
                has_media=message.media is not None,
                reply_to_msg_id=getattr(message, 'reply_to_msg_id', None),
                is_topic=hasattr(message, 'reply_to') and hasattr(message.reply_to, 'forum_topic'),
                topic_id=getattr(getattr(message, 'reply_to', None), 'reply_to_top_id', None)
            )

            # Логируем получение сообщения
            logger.info(f"💬 НОВОЕ СООБЩЕНИЕ в {post.chat_title}: @{post.author_username} - {post.content[:100]}...")

            # Фильтрация сообщений
            if post.message_type == 'group' and not post.is_admin:
                logger.debug(f"⏭️ Пропускаем сообщение от не-админа @{post.author_username}")
                return
            elif post.message_type == 'private':
                # Проверяем, нужно ли мониторить ЛС с этим пользователем
                from config.settings import settings
                if not settings.monitoring.is_monitored_dm(post.author_username):
                    logger.debug(f"⏭️ Пропускаем ЛС от не мониторимого пользователя @{post.author_username}")
                    return
                else:
                    logger.critical(f"💬 ЛС ОТ МОНИТОРИМОГО БОТА: @{post.author_username}")

            # Извлекаем данные из медиа, кнопок и гиперссылок
            inline_urls = []
            hyperlink_urls = []
            media_text = ""

            if post.has_media:
                media_text = await self.extract_media_text(message)
                if media_text:
                    post.content += f" {media_text}"

            # Извлекаем URL из инлайн кнопок
            if hasattr(message, 'reply_markup') and message.reply_markup:
                inline_urls = self.extract_inline_button_urls(message.reply_markup)

            # Извлекаем гиперссылки из entities
            if hasattr(message, 'entities') and message.entities:
                hyperlink_urls = self.extract_hyperlink_urls(message)

            # НОВАЯ ЛОГИКА: Комплексный анализ всех источников контрактов
            logger.debug(f"🧠 Комплексный анализ контрактов...")
            from utils.addresses import extract_addresses_from_message_data
            from config.settings import settings

            # Извлекаем адреса из всех источников
            found_addresses = extract_addresses_from_message_data(
                message_text=post.content,
                inline_urls=inline_urls,
                hyperlink_urls=hyperlink_urls,
                ai_config=settings.ai
            )

            # Создаем фиктивный analysis_result для совместимости
            class MockAnalysisResult:
                def __init__(self, addresses):
                    self.has_contract = len(addresses) > 0
                    self.addresses = addresses
                    self.confidence = 0.9 if addresses else 0.0  # Высокая уверенность если нашли адреса
                    self.urgency = 'high' if addresses else 'low'

            analysis_result = MockAnalysisResult(found_addresses)

            logger.critical(f"📱 TELEGRAM USER: @{post.author_username} в {post.chat_title}")
            logger.critical(
                f"🎯 Контракт: {analysis_result.has_contract}, уверенность: {analysis_result.confidence:.2f}")
            logger.critical(f"📝 Текст: {post.content}")

            # Если найден контракт с высокой уверенностью
            if analysis_result.has_contract and analysis_result.confidence > 0.6:
                logger.critical(f"🚨 КОНТРАКТ НАЙДЕН В TELEGRAM USER BOT!")
                logger.critical(f"📍 Автор: @{post.author_username} в {post.chat_title}")
                logger.critical(f"🎯 Контракты: {analysis_result.addresses}")

                if self.trading_callback:
                    await self.trigger_trading(analysis_result, post)

                self.stats['contracts_found'] += 1

            # Отмечаем как обработанный
            self.processed_messages.add(message_unique_id)
            self.stats['messages_processed'] += 1

            # Очистка старых сообщений из памяти
            if len(self.processed_messages) > 2000:
                old_messages = list(self.processed_messages)[:500]
                for old_msg in old_messages:
                    self.processed_messages.discard(old_msg)

        except FloodWaitError as e:
            logger.warning(f"⚠️ Flood wait {e.seconds}s для {chat_identifier}")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения из {chat_identifier}: {e}")
            self.stats['errors'] += 1

    async def extract_media_text(self, message) -> Optional[str]:
        """Извлечение текста из медиа И инлайн кнопок"""
        try:
            extracted_text = ""

            # Основной текст сообщения
            if message.message:
                extracted_text += message.message + " "

            # Извлекаем URL из инлайн кнопок
            if hasattr(message, 'reply_markup') and message.reply_markup:
                button_urls = self.extract_inline_button_urls(message.reply_markup)
                if button_urls:
                    logger.info(f"🔘 Найдены инлайн кнопки с URL: {button_urls}")
                    extracted_text += " ".join(button_urls) + " "

            # Извлекаем гиперссылки из entities
            if hasattr(message, 'entities') and message.entities:
                hyperlink_urls = self.extract_hyperlink_urls(message)
                if hyperlink_urls:
                    logger.info(f"🔗 Найдены гиперссылки: {hyperlink_urls}")
                    extracted_text += " ".join(hyperlink_urls) + " "

            return extracted_text.strip() if extracted_text.strip() else None

        except Exception as e:
            logger.debug(f"Ошибка извлечения медиа/кнопок: {e}")
            return None

    def extract_inline_button_urls(self, reply_markup) -> List[str]:
        """Извлечение URL из инлайн кнопок"""
        urls = []
        try:
            if hasattr(reply_markup, 'rows'):
                for row in reply_markup.rows:
                    if hasattr(row, 'buttons'):
                        for button in row.buttons:
                            if hasattr(button, 'url') and button.url:
                                urls.append(button.url)
                                logger.debug(f"🔘 Кнопка URL: {button.url}")
        except Exception as e:
            logger.debug(f"Ошибка извлечения кнопок: {e}")

        return urls

    def extract_hyperlink_urls(self, message) -> List[str]:
        """Извлечение URL из гиперссылок в тексте"""
        urls = []
        try:
            for entity in message.entities:
                if hasattr(entity, 'url') and entity.url:
                    urls.append(entity.url)
                    logger.debug(f"🔗 Гиперссылка: {entity.url}")
        except Exception as e:
            logger.debug(f"Ошибка извлечения гиперссылок: {e}")

        return urls

    async def trigger_trading(self, analysis_result, post: TelegramUserPost):
        """Запуск торговли"""
        try:
            trading_data = {
                'platform': 'telegram_user',
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
                'is_admin': post.is_admin,
                'has_media': post.has_media,
                'topic_id': post.topic_id
            }

            # Вызываем систему торговли
            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговли: {e}")

    async def health_check(self) -> Dict:
        """Проверка здоровья монитора"""
        try:
            if not TELETHON_AVAILABLE:
                return {"status": "error", "message": "Telethon не установлен"}

            if not self.client:
                return {"status": "error", "message": "Клиент не инициализирован"}

            # Проверяем подключение
            try:
                is_connected = self.client.is_connected()
                is_authorized = await self.client.is_user_authorized()

                if not is_connected:
                    await self.client.connect()

            except Exception as e:
                return {"status": "error", "message": f"Ошибка подключения: {e}"}

            # Получаем информацию о пользователе
            try:
                me = await self.client.get_me()
                username = getattr(me, 'username', 'Unknown')
            except:
                username = 'Unknown'

            return {
                "status": "healthy" if is_connected and is_authorized else "degraded",
                "connected": is_connected,
                "authorized": is_authorized,
                "username": username,
                "monitored_chats": len(self.chat_entities_by_id),
                "monitored_chat_ids": list(self.chat_entities_by_id.keys()),
                "monitored_usernames": list(self.chat_entities.keys()),
                "channels": self.stats['channels_monitored'],
                "groups": self.stats['groups_monitored'],
                "running": self.running,
                "stats": self.stats
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики мониторинга"""
        return {
            **self.stats,
            "processed_messages_cache": len(self.processed_messages),
            "chat_entities_cached": len(self.chat_entities),
            "chat_entities_by_id_cached": len(self.chat_entities_by_id),
            "chat_id_mappings": len(self.chat_id_mapping),
            "user_entities_cached": len(self.user_entities),
            "running": self.running,
            "session_file": self.session_file,
            "telethon_available": TELETHON_AVAILABLE,
            "monitored_chat_ids": list(self.chat_entities_by_id.keys()),
            "monitored_usernames": list(self.chat_entities.keys())
        }

    async def send_message(self, chat_id: int, message: str) -> bool:
        """Отправка сообщения в чат (для уведомлений)"""
        try:
            if not self.client or not self.running:
                return False

            await self.client.send_message(chat_id, message)
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return False

    async def debug_chat_info(self):
        """Отладочная информация о чатах (вызывать вручную для диагностики)"""
        if not self.client:
            logger.error("❌ Клиент не инициализирован")
            return

        logger.critical("🔍 ОТЛАДОЧНАЯ ИНФОРМАЦИЯ О ЧАТАХ:")

        try:
            # Получаем информацию о всех диалогах
            async for dialog in self.client.iter_dialogs():
                if hasattr(dialog.entity, 'username') and dialog.entity.username:
                    username = f"@{dialog.entity.username}"
                    all_ids = self.normalize_chat_ids(dialog.entity.id)
                    ids_str = " / ".join(map(str, all_ids))

                    logger.critical(f"   📍 {username} -> {dialog.title} (ID: {ids_str})")

                    # Проверяем, находится ли этот чат в мониторинге
                    if username in [ch for ch in settings.monitoring.user_bot_channels if ch] + [gr for gr in
                                                                                                 settings.monitoring.user_bot_groups
                                                                                                 if gr]:
                        logger.critical(f"      ✅ НАСТРОЕН ДЛЯ МОНИТОРИНГА")
                    else:
                        logger.critical(f"      ⏭️ Не в мониторинге")

        except Exception as e:
            logger.error(f"❌ Ошибка получения диалогов: {e}")

    async def get_chat_history(self, chat_identifier: str, limit: int = 10) -> List[Dict]:
        """Получение истории чата (для анализа прошлых сообщений)"""
        try:
            if not self.client:
                return []

            entity = await self.client.get_entity(chat_identifier)
            messages = []

            async for message in self.client.iter_messages(entity, limit=limit):
                sender = await message.get_sender()

                messages.append({
                    'id': message.id,
                    'date': message.date,
                    'text': message.text or '',
                    'sender': {
                        'id': sender.id if sender else None,
                        'username': getattr(sender, 'username', ''),
                        'first_name': getattr(sender, 'first_name', '')
                    }
                })

            return messages

        except Exception as e:
            logger.error(f"❌ Ошибка получения истории {chat_identifier}: {e}")
            return []


# Глобальный экземпляр User Bot монитора
telegram_user_monitor = UltraFastTelegramUserMonitor() if TELETHON_AVAILABLE else None