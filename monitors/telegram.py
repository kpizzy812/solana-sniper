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
    """Telegram post data structure"""
    message_id: int
    chat_id: int
    chat_username: str
    content: str
    author: str
    timestamp: datetime
    url: str
    is_edit: bool = False
    media_urls: List[str] = None


class HighSpeedTelegramMonitor:
    """Ultra-fast Telegram monitoring with 1-second intervals"""

    def __init__(self, trading_callback=None):
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.trading_callback = trading_callback

        # Tracking
        self.monitored_chats: Set[str] = set()
        self.last_message_ids: Dict[int, int] = {}  # chat_id -> last_message_id
        self.processed_messages: Set[str] = set()  # Prevent duplicate processing

        # Performance
        self.running = False
        self.last_check_time = 0
        self.check_interval = settings.monitoring.telegram_interval

        # Statistics
        self.stats = {
            'messages_processed': 0,
            'contracts_found': 0,
            'errors': 0,
            'avg_processing_time': 0
        }

    async def start(self) -> bool:
        """Initialize and start Telegram monitoring"""
        if not settings.monitoring.telegram_bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        try:
            # Initialize bot
            self.bot = Bot(token=settings.monitoring.telegram_bot_token)
            self.app = Application.builder().token(settings.monitoring.telegram_bot_token).build()

            # Set up handlers
            self.setup_handlers()

            # Start the application
            await self.app.initialize()
            await self.app.start()

            # Verify bot connection
            me = await self.bot.get_me()
            logger.info(f"Telegram bot started: @{me.username}")

            # Join monitoring channels
            await self.setup_monitoring_channels()

            # Start monitoring loop
            self.running = True
            asyncio.create_task(self.monitoring_loop())

            logger.info("High-speed Telegram monitor started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start Telegram monitor: {e}")
            return False

    async def stop(self):
        """Stop the monitor"""
        self.running = False
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
        logger.info("Telegram monitor stopped")

    def setup_handlers(self):
        """Setup message handlers"""
        # Handle all messages (channels and groups)
        self.app.add_handler(MessageHandler(
            filters.ALL,
            self.handle_message
        ))

        # Handle edited messages
        self.app.add_handler(MessageHandler(
            filters.ALL,
            self.handle_edited_message
        ))

    async def setup_monitoring_channels(self):
        """Setup channels to monitor"""
        for channel in settings.monitoring.telegram_channels:
            try:
                # Try to get channel info
                if channel.startswith('@'):
                    chat = await self.bot.get_chat(channel)
                    self.monitored_chats.add(channel)
                    logger.info(f"Monitoring Telegram channel: {channel}")
                else:
                    # Try as chat ID
                    chat_id = int(channel)
                    chat = await self.bot.get_chat(chat_id)
                    self.monitored_chats.add(str(chat_id))
                    logger.info(f"Monitoring Telegram chat: {chat_id}")

            except Exception as e:
                logger.error(f"Failed to setup monitoring for {channel}: {e}")

    async def monitoring_loop(self):
        """Main monitoring loop - checks every second"""
        logger.info("Starting high-speed monitoring loop (1-second intervals)")

        while self.running:
            try:
                start_time = time.time()

                # Check all monitored channels for new messages
                await self.check_new_messages()

                # Update timing stats
                processing_time = time.time() - start_time
                self.stats['avg_processing_time'] = (
                        self.stats['avg_processing_time'] * 0.9 + processing_time * 0.1
                )

                # Sleep for remaining time to maintain 1-second intervals
                sleep_time = max(0, self.check_interval - processing_time)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Monitoring loop taking too long: {processing_time:.3f}s")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(1)  # Prevent rapid error loops

    async def check_new_messages(self):
        """Check for new messages in all monitored channels"""
        tasks = []

        for channel in self.monitored_chats:
            task = asyncio.create_task(self.check_channel_messages(channel))
            tasks.append(task)

        # Wait for all channel checks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_channel_messages(self, channel: str):
        """Check for new messages in a specific channel"""
        try:
            # Get recent messages from the channel
            updates = await self.bot.get_updates(
                offset=-1,  # Get only the latest update
                limit=100,
                timeout=1
            )

            for update in updates:
                if update.message or update.edited_message:
                    message = update.message or update.edited_message

                    # Check if this message is from a monitored channel
                    if self.is_monitored_chat(message.chat):
                        await self.process_message(message, update.edited_message is not None)

        except Exception as e:
            logger.debug(f"Error checking channel {channel}: {e}")

    def is_monitored_chat(self, chat) -> bool:
        """Check if a chat is being monitored"""
        chat_identifier = f"@{chat.username}" if chat.username else str(chat.id)
        return chat_identifier in self.monitored_chats

    async def handle_message(self, update: Update, context):
        """Handle new messages"""
        if update.message:
            await self.process_message(update.message, is_edit=False)

    async def handle_edited_message(self, update: Update, context):
        """Handle edited messages"""
        if update.edited_message:
            await self.process_message(update.edited_message, is_edit=True)

    async def process_message(self, message, is_edit: bool = False):
        """Process a single message at maximum speed"""
        try:
            start_time = time.time()

            # Create unique message identifier
            message_key = f"{message.chat.id}:{message.message_id}:{is_edit}"

            # Skip if already processed
            if message_key in self.processed_messages:
                return

            # Extract post data
            post = await self.extract_post_data(message, is_edit)

            # ULTRA-FAST ANALYSIS
            analysis_result = await analyzer.analyze_post(
                content=post.content,
                platform="telegram",
                author=post.author,
                url=post.url
            )

            processing_time = (time.time() - start_time) * 1000

            logger.info(f"Processed Telegram message in {processing_time:.1f}ms | "
                        f"Contract: {analysis_result.has_contract} | "
                        f"Confidence: {analysis_result.confidence:.2f}")

            # If contract detected with high confidence, trigger trading immediately
            if analysis_result.has_contract and analysis_result.confidence > 0.6:
                logger.critical(f"🚨 CONTRACT DETECTED: {analysis_result.addresses}")

                if self.trading_callback:
                    # Fire and forget - don't wait for trading to complete
                    asyncio.create_task(self.trigger_trading(analysis_result, post))

                self.stats['contracts_found'] += 1

            # Mark as processed
            self.processed_messages.add(message_key)
            self.stats['messages_processed'] += 1

            # Cleanup old processed messages (prevent memory leak)
            if len(self.processed_messages) > 10000:
                # Remove oldest 1000 entries
                old_messages = list(self.processed_messages)[:1000]
                for old_msg in old_messages:
                    self.processed_messages.discard(old_msg)

        except Exception as e:
            logger.error(f"Error processing Telegram message: {e}")
            self.stats['errors'] += 1

    async def extract_post_data(self, message, is_edit: bool) -> TelegramPost:
        """Extract structured data from Telegram message"""
        # Get message content
        content = message.text or message.caption or ""

        # Get author info
        author = "Unknown"
        if message.from_user:
            author = message.from_user.username or f"{message.from_user.first_name}"
        elif message.sender_chat:
            author = message.sender_chat.title or "Channel"

        # Generate message URL
        chat_username = message.chat.username
        url = ""
        if chat_username:
            url = f"https://t.me/{chat_username}/{message.message_id}"

        # Extract media URLs
        media_urls = []
        if message.photo:
            # Get highest resolution photo
            photo = max(message.photo, key=lambda p: p.file_size or 0)
            file = await self.bot.get_file(photo.file_id)
            media_urls.append(file.file_path)

        if message.document:
            file = await self.bot.get_file(message.document.file_id)
            media_urls.append(file.file_path)

        return TelegramPost(
            message_id=message.message_id,
            chat_id=message.chat.id,
            chat_username=chat_username or str(message.chat.id),
            content=content,
            author=author,
            timestamp=message.date,
            url=url,
            is_edit=is_edit,
            media_urls=media_urls
        )

    async def trigger_trading(self, analysis_result, post: TelegramPost):
        """Trigger trading callback immediately"""
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
                'content_preview': post.content[:200]
            }

            # Call trading system
            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"Trading callback failed: {e}")

    async def health_check(self) -> Dict:
        """Health check for the monitor"""
        try:
            if not self.bot:
                return {"status": "error", "message": "Bot not initialized"}

            # Test bot connection
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
        """Get monitoring statistics"""
        return {
            **self.stats,
            "monitored_channels": len(self.monitored_chats),
            "processed_messages_cache": len(self.processed_messages),
            "running": self.running,
            "check_interval": self.check_interval
        }


# Create global monitor instance
telegram_monitor = HighSpeedTelegramMonitor()