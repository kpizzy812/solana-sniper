import asyncio
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp
from loguru import logger

from config.settings import settings
from ai.analyzer import analyzer


@dataclass
class TwitterPost:
    """Данные твита"""
    tweet_id: str
    username: str
    content: str
    created_at: datetime
    url: str
    author_verified: bool = False
    retweet_count: int = 0
    like_count: int = 0


class HighSpeedTwitterMonitor:
    """Ультра-быстрый мониторинг Twitter/X с поиском контрактов"""

    def __init__(self, trading_callback=None):
        self.trading_callback = trading_callback
        self.session: Optional[aiohttp.ClientSession] = None

        # Отслеживание обработанных твитов
        self.processed_tweets: Set[str] = set()  # tweet_id
        self.last_tweet_ids: Dict[str, str] = {}  # username -> last_tweet_id

        # Производительность
        self.running = False
        self.check_interval = settings.monitoring.twitter_interval

        # Rate limiting для Twitter API
        self.api_calls_count = 0
        self.api_reset_time = time.time() + 900  # 15 минут

        # Статистика
        self.stats = {
            'tweets_processed': 0,
            'contracts_found': 0,
            'api_calls': 0,
            'rate_limit_hits': 0,
            'errors': 0
        }

        # Headers для Twitter API v2
        self.headers = {
            'Authorization': f'Bearer {settings.monitoring.twitter_bearer_token}',
            'User-Agent': 'v2UserTweetsPython'
        } if settings.monitoring.twitter_bearer_token else {}

    async def start(self) -> bool:
        """Запуск мониторинга Twitter"""
        if not settings.monitoring.twitter_bearer_token:
            logger.warning("⚠️ Twitter Bearer Token не настроен")
            return False

        if not settings.monitoring.twitter_usernames:
            logger.warning("⚠️ Twitter пользователи не настроены")
            return False

        try:
            # Инициализация HTTP сессии
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )

            # Тестируем доступ к API
            await self.test_twitter_api()

            # Получаем ID пользователей
            await self.get_user_ids()

            # Запускаем основной цикл мониторинга
            self.running = True
            asyncio.create_task(self.monitoring_loop())

            logger.success("✅ Twitter монитор запущен успешно")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Twitter монитора: {e}")
            return False

    async def stop(self):
        """Остановка монитора"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("🛑 Twitter монитор остановлен")

    async def test_twitter_api(self):
        """Тестирование доступа к Twitter API"""
        try:
            url = "https://api.twitter.com/2/users/me"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Twitter API доступен")
                elif response.status == 401:
                    raise Exception("Неверный Bearer Token")
                elif response.status == 429:
                    raise Exception("Превышен лимит запросов")
                else:
                    raise Exception(f"Twitter API вернул статус {response.status}")

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Twitter API: {e}")
            raise

    async def get_user_ids(self):
        """Получение ID пользователей по их именам"""
        self.user_ids = {}

        try:
            # Создаем запрос для получения ID пользователей
            usernames = [u for u in settings.monitoring.twitter_usernames if u]
            usernames_str = ','.join(usernames)

            url = f"https://api.twitter.com/2/users/by?usernames={usernames_str}"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    for user in data.get('data', []):
                        self.user_ids[user['username']] = user['id']
                        logger.info(f"📱 Twitter пользователь @{user['username']} (ID: {user['id']})")

                elif response.status == 429:
                    logger.warning("⚠️ Превышен лимит запросов при получении ID пользователей")
                else:
                    logger.error(f"❌ Ошибка получения ID пользователей: {response.status}")

        except Exception as e:
            logger.error(f"❌ Ошибка получения ID пользователей: {e}")

    async def monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info(f"🔍 Запуск мониторинга Twitter (интервал: {self.check_interval}s)")

        while self.running:
            try:
                start_time = time.time()

                # Проверяем rate limit
                if await self.check_rate_limit():
                    # Проверяем твиты всех пользователей
                    await self.check_all_users()

                # Ждем до следующей проверки
                processing_time = time.time() - start_time
                sleep_time = max(0, self.check_interval - processing_time)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"⚠️ Мониторинг Twitter превышает интервал: {processing_time:.1f}s")

            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга Twitter: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(10)  # Пауза при ошибке

    async def check_rate_limit(self) -> bool:
        """Проверка лимитов запросов"""
        current_time = time.time()

        # Сброс счетчика каждые 15 минут
        if current_time >= self.api_reset_time:
            self.api_calls_count = 0
            self.api_reset_time = current_time + 900
            logger.debug("🔄 Сброс счетчика API запросов")

        # Проверяем лимит (Twitter API v2 Free: 75 запросов за 15 минут)
        if self.api_calls_count >= 70:  # Оставляем запас
            logger.warning("⚠️ Приближение к лимиту Twitter API, пропускаем проверку")
            self.stats['rate_limit_hits'] += 1
            return False

        return True

    async def check_all_users(self):
        """Проверка твитов всех пользователей"""
        tasks = []

        for username in settings.monitoring.twitter_usernames:
            if username and username in getattr(self, 'user_ids', {}):
                task = asyncio.create_task(self.check_user_tweets(username))
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_user_tweets(self, username: str):
        """Проверка твитов конкретного пользователя"""
        try:
            user_id = getattr(self, 'user_ids', {}).get(username)
            if not user_id:
                logger.warning(f"⚠️ ID пользователя @{username} не найден")
                return

            # Параметры запроса для получения последних твитов
            params = {
                'max_results': 10,  # Последние 10 твитов
                'tweet.fields': 'created_at,public_metrics,author_id',
                'exclude': 'retweets'  # Исключаем ретвиты
            }

            # Добавляем since_id если есть последний твит
            last_tweet_id = self.last_tweet_ids.get(username)
            if last_tweet_id:
                params['since_id'] = last_tweet_id

            url = f"https://api.twitter.com/2/users/{user_id}/tweets"

            self.api_calls_count += 1
            self.stats['api_calls'] += 1

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tweets = data.get('data', [])

                    if tweets:
                        # Обновляем последний ID твита
                        self.last_tweet_ids[username] = tweets[0]['id']

                        # Обрабатываем новые твиты
                        for tweet_data in reversed(tweets):  # От старых к новым
                            await self.process_tweet(tweet_data, username)

                elif response.status == 429:
                    logger.warning(f"⚠️ Rate limit для @{username}")
                    self.stats['rate_limit_hits'] += 1
                elif response.status == 401:
                    logger.error("❌ Неавторизованный доступ к Twitter API")
                else:
                    logger.error(f"❌ Ошибка запроса твитов @{username}: {response.status}")

        except Exception as e:
            logger.error(f"❌ Ошибка проверки твитов @{username}: {e}")

    async def process_tweet(self, tweet_data: Dict, username: str):
        """Обработка одного твита"""
        try:
            tweet_id = tweet_data['id']

            # Пропускаем уже обработанные
            if tweet_id in self.processed_tweets:
                return

            # Создаем объект твита
            tweet = TwitterPost(
                tweet_id=tweet_id,
                username=username,
                content=tweet_data['text'],
                created_at=datetime.fromisoformat(tweet_data['created_at'].replace('Z', '+00:00')),
                url=f"https://twitter.com/{username}/status/{tweet_id}",
                retweet_count=tweet_data.get('public_metrics', {}).get('retweet_count', 0),
                like_count=tweet_data.get('public_metrics', {}).get('like_count', 0)
            )

            # Быстрый анализ на контракты
            analysis_result = await analyzer.analyze_post(
                content=tweet.content,
                platform="twitter",
                author=username,
                url=tweet.url
            )

            logger.info(f"🐦 Твит @{username}: контракт={analysis_result.has_contract}, "
                        f"уверенность={analysis_result.confidence:.2f}")

            # Если найден контракт с высокой уверенностью
            if analysis_result.has_contract and analysis_result.confidence > 0.6:
                logger.critical(f"🚨 КОНТРАКТ В ТВИТЕ @{username}: {analysis_result.addresses}")

                if self.trading_callback:
                    await self.trigger_trading(analysis_result, tweet)

                self.stats['contracts_found'] += 1

            # Отмечаем как обработанный
            self.processed_tweets.add(tweet_id)
            self.stats['tweets_processed'] += 1

            # Очистка старых твитов из памяти
            if len(self.processed_tweets) > 1000:
                old_tweets = list(self.processed_tweets)[:200]
                for old_tweet in old_tweets:
                    self.processed_tweets.discard(old_tweet)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки твита: {e}")

    async def trigger_trading(self, analysis_result, tweet: TwitterPost):
        """Запуск торговли"""
        try:
            trading_data = {
                'platform': 'twitter',
                'source': f'@{tweet.username}',
                'author': tweet.username,
                'url': tweet.url,
                'contracts': analysis_result.addresses,
                'confidence': analysis_result.confidence,
                'urgency': analysis_result.urgency,
                'timestamp': tweet.created_at,
                'content_preview': tweet.content,
                'engagement': {
                    'retweets': tweet.retweet_count,
                    'likes': tweet.like_count
                }
            }

            # Вызываем систему торговли
            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговли: {e}")

    async def health_check(self) -> Dict:
        """Проверка здоровья монитора"""
        try:
            if not self.session:
                return {"status": "error", "message": "Сессия не инициализирована"}

            # Проверяем доступ к API
            try:
                url = "https://api.twitter.com/2/users/me"
                async with self.session.get(url) as response:
                    api_accessible = response.status in [200, 401, 429]  # Любой валидный ответ
            except:
                api_accessible = False

            # Проверяем лимиты
            remaining_calls = max(0, 70 - self.api_calls_count)

            return {
                "status": "healthy" if api_accessible else "error",
                "api_accessible": api_accessible,
                "monitored_users": len([u for u in settings.monitoring.twitter_usernames if u]),
                "running": self.running,
                "rate_limit": {
                    "remaining_calls": remaining_calls,
                    "reset_time": self.api_reset_time
                },
                "stats": self.stats
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики мониторинга"""
        return {
            **self.stats,
            "monitored_users": len([u for u in settings.monitoring.twitter_usernames if u]),
            "processed_tweets_cache": len(self.processed_tweets),
            "user_ids_cached": len(getattr(self, 'user_ids', {})),
            "running": self.running,
            "check_interval": self.check_interval,
            "api_calls_remaining": max(0, 70 - self.api_calls_count)
        }


# Глобальный экземпляр монитора
twitter_monitor = HighSpeedTwitterMonitor()