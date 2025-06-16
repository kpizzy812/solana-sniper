import asyncio
import time
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import settings
from ai.analyzer import analyzer


@dataclass
class WebsitePost:
    """Данные поста с сайта"""
    url: str
    content: str
    title: str
    timestamp: datetime
    hash: str
    selectors_found: List[str]


class HighSpeedWebsiteMonitor:
    """Ультра-быстрый мониторинг сайтов с поиском контрактов"""

    def __init__(self, trading_callback=None):
        self.trading_callback = trading_callback
        self.session: Optional[aiohttp.ClientSession] = None

        # Отслеживание изменений
        self.content_hashes: Dict[str, str] = {}  # url -> hash последнего контента
        self.processed_contracts: Set[str] = set()  # Обработанные контракты

        # Производительность
        self.running = False
        self.check_interval = settings.monitoring.website_interval

        # Статистика
        self.stats = {
            'pages_checked': 0,
            'content_changes': 0,
            'contracts_found': 0,
            'errors': 0,
            'avg_response_time': 0
        }

    async def start(self) -> bool:
        """Запуск мониторинга сайтов"""
        if not settings.monitoring.website_urls:
            logger.warning("⚠️ URLs сайтов не настроены")
            return False

        try:
            # Инициализация HTTP сессии
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )

            # Проверяем доступность сайтов
            await self.test_websites()

            # Запускаем основной цикл мониторинга
            self.running = True
            asyncio.create_task(self.monitoring_loop())

            logger.success("✅ Монитор сайтов запущен успешно")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска монитора сайтов: {e}")
            return False

    async def stop(self):
        """Остановка монитора"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("🛑 Монитор сайтов остановлен")

    async def test_websites(self):
        """Тестирование доступности сайтов"""
        logger.info("🔍 Тестирование доступности сайтов...")

        for url in settings.monitoring.website_urls:
            if not url:
                continue

            try:
                start_time = time.time()
                async with self.session.get(url) as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status == 200:
                        logger.info(f"✅ {url} доступен ({response_time:.0f}ms)")

                        # Инициализируем hash для отслеживания изменений
                        content = await response.text()
                        content_hash = hashlib.md5(content.encode()).hexdigest()
                        self.content_hashes[url] = content_hash

                    else:
                        logger.warning(f"⚠️ {url} вернул статус {response.status}")

            except Exception as e:
                logger.error(f"❌ Ошибка тестирования {url}: {e}")

    async def monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info(f"🔍 Запуск мониторинга сайтов (интервал: {self.check_interval}s)")

        while self.running:
            try:
                start_time = time.time()

                # Проверяем все сайты параллельно
                await self.check_all_websites()

                # Обновляем статистику времени
                processing_time = time.time() - start_time
                self.stats['avg_response_time'] = (
                        self.stats['avg_response_time'] * 0.9 + processing_time * 0.1
                )

                # Ждем до следующей проверки
                sleep_time = max(0, self.check_interval - processing_time)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"⚠️ Мониторинг сайтов превышает интервал: {processing_time:.1f}s")

            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга сайтов: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(5)  # Пауза при ошибке

    async def check_all_websites(self):
        """Проверка всех сайтов параллельно"""
        tasks = []

        for url in settings.monitoring.website_urls:
            if url:
                task = asyncio.create_task(self.check_website(url))
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_website(self, url: str):
        """Проверка одного сайта на изменения"""
        try:
            start_time = time.time()

            async with self.session.get(url) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status != 200:
                    logger.debug(f"⚠️ {url} статус {response.status}")
                    return

                content = await response.text()
                content_hash = hashlib.md5(content.encode()).hexdigest()

                self.stats['pages_checked'] += 1

                # Проверяем, изменился ли контент
                old_hash = self.content_hashes.get(url)
                if old_hash and old_hash == content_hash:
                    # Контент не изменился
                    logger.debug(f"📄 {url} без изменений ({response_time:.0f}ms)")
                    return

                # Контент изменился или это первая проверка
                self.content_hashes[url] = content_hash

                if old_hash:  # Не первая проверка
                    self.stats['content_changes'] += 1
                    logger.info(f"🔄 Изменения на {url} ({response_time:.0f}ms)")

                # Анализируем контент на наличие контрактов
                await self.analyze_website_content(url, content, response_time)

        except Exception as e:
            logger.error(f"❌ Ошибка проверки {url}: {e}")
            self.stats['errors'] += 1

    async def analyze_website_content(self, url: str, content: str, response_time: float):
        """Анализ контента сайта на наличие контрактов"""
        try:
            # Парсим HTML
            soup = BeautifulSoup(content, 'html.parser')

            # Извлекаем текст со страницы
            page_text = soup.get_text()

            # Ищем контракты по селекторам
            contracts_from_selectors = self.extract_contracts_by_selectors(soup)

            # Быстрый анализ всего текста
            analysis_result = await analyzer.analyze_post(
                content=page_text[:2000],  # Первые 2000 символов для скорости
                platform="website",
                author=url,
                url=url
            )

            # Объединяем найденные контракты
            all_contracts = list(set(analysis_result.addresses + contracts_from_selectors))

            if all_contracts:
                logger.critical(f"🚨 КОНТРАКТЫ НАЙДЕНЫ НА САЙТЕ {url}")
                logger.info(f"📍 Контракты: {all_contracts}")

                # Фильтруем уже обработанные контракты
                new_contracts = [c for c in all_contracts if c not in self.processed_contracts]

                if new_contracts:
                    # Создаем пост данные
                    post = WebsitePost(
                        url=url,
                        content=page_text[:500],  # Превью контента
                        title=soup.title.string if soup.title else "Без заголовка",
                        timestamp=datetime.now(),
                        hash=hashlib.md5(content.encode()).hexdigest(),
                        selectors_found=contracts_from_selectors
                    )

                    # Запускаем торговлю
                    if self.trading_callback:
                        await self.trigger_trading(new_contracts, post, analysis_result)

                    # Отмечаем контракты как обработанные
                    self.processed_contracts.update(new_contracts)
                    self.stats['contracts_found'] += len(new_contracts)

            else:
                logger.debug(f"📄 {url} - контракты не найдены")

        except Exception as e:
            logger.error(f"❌ Ошибка анализа контента {url}: {e}")

    def extract_contracts_by_selectors(self, soup: BeautifulSoup) -> List[str]:
        """Извлечение контрактов по CSS селекторам"""
        contracts = []

        for selector in settings.monitoring.website_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Получаем текст элемента
                    text = element.get_text().strip()

                    # Извлекаем адреса из текста
                    from config.settings import extract_addresses_fast, is_valid_solana_address
                    addresses = extract_addresses_fast(text)

                    # Проверяем атрибуты элемента
                    for attr in ['data-contract', 'data-address', 'data-token']:
                        value = element.get(attr, '').strip()
                        if value and is_valid_solana_address(value):
                            addresses.append(value)

                    contracts.extend(addresses)

            except Exception as e:
                logger.debug(f"Ошибка селектора {selector}: {e}")

        return list(set(contracts))  # Убираем дубликаты

    async def trigger_trading(self, contracts: List[str], post: WebsitePost, analysis_result):
        """Запуск торговли"""
        try:
            trading_data = {
                'platform': 'website',
                'source': post.url,
                'author': 'website',
                'url': post.url,
                'contracts': contracts,
                'confidence': analysis_result.confidence,
                'urgency': analysis_result.urgency,
                'timestamp': post.timestamp,
                'content_preview': post.content,
                'title': post.title,
                'selectors_found': post.selectors_found
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

            # Тестируем доступность одного сайта
            test_url = next((url for url in settings.monitoring.website_urls if url), None)

            if test_url:
                try:
                    async with self.session.get(test_url) as response:
                        website_accessible = response.status == 200
                except:
                    website_accessible = False
            else:
                website_accessible = True  # Нет сайтов для проверки

            return {
                "status": "healthy" if website_accessible else "degraded",
                "monitored_websites": len([url for url in settings.monitoring.website_urls if url]),
                "running": self.running,
                "website_accessible": website_accessible,
                "stats": self.stats
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики мониторинга"""
        return {
            **self.stats,
            "monitored_websites": len([url for url in settings.monitoring.website_urls if url]),
            "content_hashes_cached": len(self.content_hashes),
            "processed_contracts": len(self.processed_contracts),
            "running": self.running,
            "check_interval": self.check_interval
        }


# Глобальный экземпляр монитора
website_monitor = HighSpeedWebsiteMonitor()