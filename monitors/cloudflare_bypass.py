"""
🛡️ MORI Sniper Bot - Cloudflare Bypass
Система обхода Cloudflare защиты для мониторинга сайтов
"""

import asyncio
import time
import random
from typing import Optional, Dict
from loguru import logger

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    UNDETECTED_AVAILABLE = True
    logger.debug("✅ undetected-chromedriver доступен")
except ImportError:
    UNDETECTED_AVAILABLE = False
    logger.debug("⚠️ undetected-chromedriver недоступен")

# Проверяем доступность библиотек для обхода Cloudflare
CLOUDSCRAPER_AVAILABLE = False
PLAYWRIGHT_AVAILABLE = False

try:
    import cloudscraper

    CLOUDSCRAPER_AVAILABLE = True
    logger.debug("✅ cloudscraper доступен")
except ImportError:
    logger.debug("⚠️ cloudscraper недоступен")

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
    logger.debug("✅ playwright доступен")
except ImportError:
    logger.debug("⚠️ playwright недоступен")

import aiohttp
from bs4 import BeautifulSoup


class CloudflareBypass:
    """Система обхода Cloudflare защиты"""

    def __init__(self):
        self.scraper = None
        self.playwright = None
        self.browser = None
        self.method = "none"  # none, cloudscraper, playwright, basic

    async def start(self):
        """Инициализация системы обхода"""
        logger.info("🛡️ Инициализация Cloudflare bypass...")

        # Приоритет: Playwright > CloudScraper > Basic
        if PLAYWRIGHT_AVAILABLE:
            try:
                await self._init_playwright()
                self.method = "playwright"
                logger.success("✅ Cloudflare bypass: Playwright")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Playwright не удалось запустить: {e}")

        if CLOUDSCRAPER_AVAILABLE:
            try:
                self._init_cloudscraper()
                self.method = "cloudscraper"
                logger.success("✅ Cloudflare bypass: CloudScraper")
                return True
            except Exception as e:
                logger.warning(f"⚠️ CloudScraper не удалось запустить: {e}")

        # Fallback к базовым методам
        self.method = "basic"
        logger.warning("⚠️ Cloudflare bypass: Basic (может не работать)")
        return True

    async def _init_playwright(self):
        """Инициализация Playwright"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920x1080'
            ]
        )

    def _init_cloudscraper(self):
        """Инициализация CloudScraper"""
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    async def stop(self):
        """Остановка системы обхода"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_page_content(self, url: str, wait_for_changes: bool = False) -> Optional[str]:
        """
        Получение контента страницы с обходом Cloudflare

        Args:
            url: URL страницы
            wait_for_changes: Ждать изменений на странице (для мониторинга)

        Returns:
            str: HTML контент или None
        """
        try:
            # Пробуем все методы по порядку
            methods = []

            if self.method == "playwright":
                methods = ["undetected", "flaresolverr", "playwright", "proxies", "stealth", "cloudscraper", "basic"]
            elif self.method == "cloudscraper":
                methods = ["undetected", "flaresolverr", "cloudscraper", "proxies", "stealth", "basic"]
            else:
                methods = ["undetected", "flaresolverr", "proxies", "stealth", "basic"]


            for method in methods:
                try:
                    logger.debug(f"🔄 Пробуем метод: {method}")

                    if method == "undetected" and UNDETECTED_AVAILABLE:
                        content = await self._get_content_undetected(url)
                    elif method == "flaresolverr":
                        content = await self._get_content_flaresolverr(url)
                    elif method == "proxies":
                        content = await self._get_content_with_proxies(url)
                    elif method == "cloudscraper" and CLOUDSCRAPER_AVAILABLE:
                        content = await self._get_content_cloudscraper(url)
                    elif method == "stealth":
                        content = await self._get_content_stealth(url)
                    elif method == "basic":
                        content = await self._get_content_basic(url)
                    else:
                        continue

                    if content and len(content) > 1000:
                        # Проверяем что это не Cloudflare блок
                        if not ('just a moment' in content.lower() or 'checking your browser' in content.lower()):
                            logger.debug(f"✅ Успех с методом: {method}")
                            return content
                        else:
                            logger.debug(f"⚠️ Cloudflare блок с методом: {method}")

                except Exception as e:
                    logger.debug(f"Ошибка метода {method}: {e}")
                    continue

            logger.warning("⚠️ Все методы обхода не сработали")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения контента {url}: {e}")
            return None

    async def _get_content_undetected(self, url: str) -> Optional[str]:
        """Обход через undetected-chromedriver"""
        try:
            logger.debug(f"🤖 Undetected Chrome загрузка {url}...")

            # Настройки для максимального обхода
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')  # Быстрее загрузка
            options.add_argument('--disable-javascript')  # Отключаем JS детекцию
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            driver = uc.Chrome(options=options, version_main=120)

            try:
                # Человекоподобная загрузка
                driver.get(url)

                # Ждем загрузки страницы
                await asyncio.sleep(5)

                # Проверяем что Cloudflare пройден
                for i in range(10):  # Максимум 10 попыток
                    page_source = driver.page_source

                    if 'just a moment' not in page_source.lower() and 'checking your browser' not in page_source.lower():
                        logger.debug(f"✅ Cloudflare обойден на попытке {i + 1}")
                        return page_source

                    logger.debug(f"⏱️ Попытка {i + 1}: ждем прохождения Cloudflare...")
                    await asyncio.sleep(2)

                # Если не прошли за 20 секунд, возвращаем что есть
                logger.warning("⚠️ Cloudflare не пройден, возвращаем текущий контент")
                return driver.page_source

            finally:
                driver.quit()

        except Exception as e:
            logger.error(f"❌ Ошибка undetected-chromedriver: {e}")
            return None

    async def _get_content_flaresolverr(self, url: str) -> Optional[str]:
        """Обход через FlareSolverr сервис"""
        try:
            logger.debug(f"🔥 FlareSolverr загрузка {url}...")

            # FlareSolverr API endpoint (если запущен локально)
            flaresolverr_url = "http://localhost:8191/v1"

            payload = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": 60000
            }

            timeout = aiohttp.ClientTimeout(total=70)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(flaresolverr_url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'ok':
                            content = data['solution']['response']
                            logger.debug(f"✅ FlareSolverr успех: {len(content)} символов")
                            return content

            return None

        except Exception as e:
            logger.debug(f"FlareSolverr недоступен: {e}")
            return None

    async def _get_content_with_proxies(self, url: str) -> Optional[str]:
        """Обход с ротацией прокси"""
        try:
            # Список бесплатных прокси (можно расширить)
            proxies = [
                None,  # Без прокси
                "http://proxy1.com:8080",
                "http://proxy2.com:3128",
                # Добавь свои прокси
            ]

            for i, proxy in enumerate(proxies):
                try:
                    logger.debug(f"🌐 Попытка {i + 1} с прокси: {proxy or 'direct'}")

                    connector = aiohttp.ProxyConnector.from_url(proxy) if proxy else None
                    timeout = aiohttp.ClientTimeout(total=30)

                    headers = {
                        'User-Agent': f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.{i}.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                    }

                    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
                        await asyncio.sleep(random.uniform(5, 15))  # Большая задержка

                        async with session.get(url) as response:
                            content = await response.text()

                            if response.status == 200 and len(content) > 5000:
                                if not (
                                        'just a moment' in content.lower() or 'checking your browser' in content.lower()):
                                    logger.debug(f"✅ Успех с прокси {i + 1}")
                                    return content

                except Exception as e:
                    logger.debug(f"Ошибка прокси {i + 1}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка прокси ротации: {e}")
            return None

    async def _get_content_playwright(self, url: str, wait_for_changes: bool = False) -> Optional[str]:
        """Получение контента через Playwright"""
        try:
            # Более агрессивный контекст
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                }
            )

            page = await context.new_page()

            # Загружаем страницу
            logger.debug(f"🌐 Загрузка {url} через Playwright...")
            response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            logger.debug(f"📊 Response status: {response.status}")

            # Ждем прохождения Cloudflare (увеличил время)
            try:
                await page.wait_for_function(
                    "!document.title.includes('Just a moment') && !document.body.textContent.includes('Checking your browser') && !document.body.textContent.includes('Please wait')",
                    timeout=20000  # 20 секунд
                )
                logger.debug("✅ Cloudflare проверка пройдена")
            except:
                logger.debug("⚠️ Возможно Cloudflare проверка все еще активна")

            # Дополнительная задержка
            await page.wait_for_timeout(3000)

            # Если нужно ждать изменений (для мониторинга кнопки)
            if wait_for_changes:
                await self._wait_for_button_changes(page)

            content = await page.content()
            await context.close()

            logger.debug(f"✅ Получен контент: {len(content)} символов")
            return content

        except Exception as e:
            logger.error(f"❌ Ошибка Playwright: {e}")
            return None

    async def _get_content_cloudscraper(self, url: str) -> Optional[str]:
        """Получение контента через CloudScraper"""
        try:
            logger.debug(f"🌐 Загрузка {url} через CloudScraper...")

            # Пробуем разные конфигурации CloudScraper
            configs = [
                {'browser': 'chrome', 'platform': 'darwin'},  # macOS
                {'browser': 'chrome', 'platform': 'windows'},
                {'browser': 'firefox', 'platform': 'windows'},
                {'browser': 'chrome', 'platform': 'linux'},
            ]

            for i, config in enumerate(configs):
                try:
                    logger.debug(f"🔄 Пробуем конфиг {i + 1}: {config}")
                    scraper = cloudscraper.create_scraper(browser=config)

                    # Добавляем случайную задержку
                    await asyncio.sleep(random.uniform(2, 5))

                    response = scraper.get(url, timeout=30)

                    if response.status_code == 200:
                        logger.debug(f"✅ Получен контент: {len(response.text)} символов")
                        return response.text
                    elif response.status_code == 403:
                        logger.debug(f"⚠️ 403 с конфигом {config}, пробуем следующий...")
                        continue
                    else:
                        logger.warning(f"⚠️ CloudScraper статус: {response.status_code}")

                except Exception as e:
                    logger.debug(f"Ошибка конфига {config}: {e}")
                    continue

            logger.warning("⚠️ Все конфигурации CloudScraper не сработали")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка CloudScraper: {e}")
            return None

    async def _get_content_stealth(self, url: str) -> Optional[str]:
        """Стелс-режим с множественными попытками"""
        try:
            logger.debug(f"🥷 Стелс-загрузка {url}...")

            # Пробуем несколько User-Agent
            user_agents = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            ]

            for i, ua in enumerate(user_agents):
                try:
                    logger.debug(f"🔄 Попытка {i + 1} с UA: {ua[:50]}...")

                    headers = {
                        'User-Agent': ua,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Cache-Control': 'max-age=0',
                        'Pragma': 'no-cache',
                    }

                    timeout = aiohttp.ClientTimeout(total=30)

                    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                        # Большая случайная задержка
                        await asyncio.sleep(random.uniform(3, 8))

                        async with session.get(url) as response:
                            content = await response.text()

                            logger.debug(f"📊 Статус: {response.status}, размер: {len(content)}")

                            if response.status == 200 and len(content) > 5000:
                                # Проверяем что это не Cloudflare страница
                                if not (
                                        'just a moment' in content.lower() or 'checking your browser' in content.lower()):
                                    logger.debug(f"✅ Успешно получен контент")
                                    return content

                            if response.status == 403:
                                logger.debug(f"⚠️ 403 с UA {i + 1}, пробуем следующий...")
                                continue

                except Exception as e:
                    logger.debug(f"Ошибка с UA {i + 1}: {e}")
                    continue

            logger.warning("⚠️ Все User-Agent не сработали")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка стелс-режима: {e}")
            return None

    async def _get_content_basic(self, url: str) -> Optional[str]:
        """Базовое получение контента (fallback)"""
        try:
            logger.debug(f"🌐 Загрузка {url} базовым методом...")

            # Используем максимально реалистичные заголовки
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }

            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                # Добавляем случайную задержку
                await asyncio.sleep(random.uniform(2, 5))

                async with session.get(url) as response:
                    content = await response.text()

                    if response.status == 200:
                        logger.debug(f"✅ Получен контент: {len(content)} символов")
                        return content
                    else:
                        logger.warning(f"⚠️ Базовый метод статус: {response.status}")
                        return content  # Возвращаем даже если не 200

        except Exception as e:
            logger.error(f"❌ Ошибка базового метода: {e}")
            return None

    async def _wait_for_button_changes(self, page):
        """Ожидание изменений в кнопке покупки"""
        try:
            logger.debug("👁️ Мониторинг изменений кнопки...")

            # Ждем появления активной кнопки покупки
            button_selectors = [
                'button:has-text("buy")',
                'button:has-text("купить")',
                'a:has-text("buy")',
                'a:has-text("купить")',
                '[class*="buy"]:visible',
                '[id*="buy"]:visible',
                'button[href]',
                'button[onclick]'
            ]

            for selector in button_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000, state='visible')
                    logger.info(f"✅ Обнаружена активная кнопка: {selector}")
                    return
                except:
                    continue

            logger.debug("⏱️ Кнопка не стала активной за время ожидания")

        except Exception as e:
            logger.debug(f"Ошибка мониторинга кнопки: {e}")

    async def health_check(self, url: str) -> Dict:
        """Проверка работоспособности обхода"""
        try:
            start_time = time.time()
            content = await self.get_page_content(url)
            response_time = (time.time() - start_time) * 1000

            if content and len(content) > 1000:  # Минимальный размер для валидной страницы
                # Проверяем признаки Cloudflare блокировки
                if 'just a moment' in content.lower() or 'checking your browser' in content.lower():
                    status = "blocked"
                else:
                    status = "working"
            else:
                status = "failed"

            return {
                "status": status,
                "method": self.method,
                "response_time_ms": response_time,
                "content_size": len(content) if content else 0,
                "available_methods": {
                    "playwright": PLAYWRIGHT_AVAILABLE,
                    "cloudscraper": CLOUDSCRAPER_AVAILABLE,
                    "basic": True
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "method": self.method,
                "error": str(e),
                "available_methods": {
                    "playwright": PLAYWRIGHT_AVAILABLE,
                    "cloudscraper": CLOUDSCRAPER_AVAILABLE,
                    "basic": True
                }
            }


# Глобальный экземпляр
cloudflare_bypass = CloudflareBypass()