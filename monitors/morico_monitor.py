"""
🎯 MORI Sniper Bot - Специальный монитор для MORICO.IN
Мониторинг появления активной кнопки "Купить МОРИ" на сайте
"""

import asyncio
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import settings
from ai.analyzer import analyzer
from .cloudflare_bypass import cloudflare_bypass


@dataclass
class MoricoButtonState:
    """Состояние кнопки покупки МОРИ"""
    is_active: bool
    button_text: str
    button_url: str
    button_selector: str
    contracts_found: List[str]
    timestamp: datetime


class MoricoSiteMonitor:
    """Специальный монитор для сайта MORICO.IN"""

    def __init__(self, trading_callback=None):
        self.trading_callback = trading_callback
        self.url = "https://morico.in/"

        # Состояние мониторинга
        self.running = False
        self.last_content_hash = None
        self.last_button_state = None
        self.check_interval = 10  # Проверка каждые 10 секунд

        # Статистика
        self.stats = {
            'checks_performed': 0,
            'content_changes': 0,
            'button_activations': 0,
            'contracts_found': 0,
            'cloudflare_blocks': 0,
            'errors': 0
        }

        # Селекторы для поиска кнопки
        self.button_selectors = [
            # Общие селекторы кнопок
            'button', 'a.btn', '.button', '.buy-button',
            '[class*="buy"]', '[id*="buy"]', '[class*="purchase"]',

            # МОРИ специфичные селекторы
            'button:contains("МОРИ")', 'button:contains("MORI")',
            'a:contains("МОРИ")', 'a:contains("MORI")',
            'button:contains("купить")', 'button:contains("buy")',

            # Кнопки с ссылками
            'button[href]', 'button[onclick]', 'a[href*="jup"]',
            'a[href*="jupiter"]', 'a[href*="raydium"]', 'a[href*="dex"]',
        ]

    async def start(self) -> bool:
        """Запуск мониторинга MORICO сайта"""
        logger.info("🎯 Запуск мониторинга MORICO.IN...")

        try:
            # Инициализируем Cloudflare bypass
            await cloudflare_bypass.start()

            # Тестируем доступ к сайту
            health = await cloudflare_bypass.health_check(self.url)

            if health['status'] == 'working':
                logger.success("✅ Доступ к MORICO.IN получен")
                logger.info(f"🛡️ Метод обхода: {health['method']}")
            elif health['status'] == 'blocked':
                logger.warning("⚠️ Cloudflare блокировка активна, но продолжаем попытки")
            else:
                logger.error("❌ Не удалось получить доступ к MORICO.IN")
                return False

            # Получаем начальное состояние сайта
            await self.get_initial_state()

            # Запускаем основной цикл мониторинга
            self.running = True
            asyncio.create_task(self.monitoring_loop())

            logger.success("✅ Мониторинг MORICO.IN запущен")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска мониторинга MORICO: {e}")
            return False

    async def stop(self):
        """Остановка мониторинга"""
        self.running = False
        await cloudflare_bypass.stop()
        logger.info("🛑 Мониторинг MORICO.IN остановлен")

    async def get_initial_state(self):
        """Получение начального состояния сайта"""
        try:
            logger.info("📸 Получение начального состояния MORICO.IN...")

            content = await cloudflare_bypass.get_page_content(self.url)
            if content:
                self.last_content_hash = hashlib.md5(content.encode()).hexdigest()
                button_state = self.analyze_button_state(content)
                self.last_button_state = button_state

                logger.info(f"📊 Начальное состояние:")
                logger.info(f"   Кнопка активна: {button_state.is_active}")
                logger.info(f"   Текст кнопки: {button_state.button_text}")
                if button_state.button_url:
                    logger.info(f"   URL кнопки: {button_state.button_url}")
                if button_state.contracts_found:
                    logger.warning(f"🎯 Контракты уже найдены: {button_state.contracts_found}")

        except Exception as e:
            logger.error(f"❌ Ошибка получения начального состояния: {e}")

    async def monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info("🔄 Запуск цикла мониторинга MORICO.IN...")

        while self.running:
            try:
                start_time = time.time()

                # Проверяем изменения на сайте
                await self.check_site_changes()

                # Обновляем статистику
                self.stats['checks_performed'] += 1

                # Вычисляем время до следующей проверки
                processing_time = time.time() - start_time
                sleep_time = max(0, self.check_interval - processing_time)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"⚠️ Мониторинг MORICO превышает интервал: {processing_time:.1f}s")

            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга MORICO: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(10)  # Пауза при ошибке

    async def check_site_changes(self):
        """Проверка изменений на сайте"""
        try:
            content = await cloudflare_bypass.get_page_content(self.url)

            if not content:
                logger.debug("⚠️ Не удалось получить контент MORICO")
                return

            # Проверяем блокировку Cloudflare
            if 'just a moment' in content.lower() or 'checking your browser' in content.lower():
                self.stats['cloudflare_blocks'] += 1
                logger.debug("🛡️ Cloudflare блокировка активна")
                return

            # Вычисляем хеш контента
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # Проверяем изменения
            if content_hash != self.last_content_hash:
                logger.info("🔄 Обнаружены изменения на MORICO.IN")
                self.stats['content_changes'] += 1
                self.last_content_hash = content_hash

                # Анализируем новое состояние кнопки
                button_state = self.analyze_button_state(content)
                await self.handle_button_changes(button_state)

            else:
                logger.debug("📄 MORICO.IN без изменений")

        except Exception as e:
            logger.error(f"❌ Ошибка проверки изменений MORICO: {e}")
            self.stats['errors'] += 1

    def analyze_button_state(self, content: str) -> MoricoButtonState:
        """Анализ состояния кнопки покупки"""
        try:
            soup = BeautifulSoup(content, 'html.parser')

            # Ищем кнопки покупки
            for selector in self.button_selectors:
                try:
                    buttons = soup.select(selector)
                    for button in buttons:
                        text = button.get_text().strip()

                        # Проверяем релевантность кнопки
                        if self.is_buy_button(text):
                            # Анализируем активность кнопки
                            is_active = self.is_button_active(button)
                            button_url = self.get_button_url(button)

                            # Ищем контракты в URL или onclick
                            contracts = self.extract_contracts_from_button(button, button_url)

                            return MoricoButtonState(
                                is_active=is_active,
                                button_text=text,
                                button_url=button_url or '',
                                button_selector=selector,
                                contracts_found=contracts,
                                timestamp=datetime.now()
                            )

                except Exception as e:
                    logger.debug(f"Ошибка анализа селектора {selector}: {e}")
                    continue

            # Кнопка не найдена или неактивна
            return MoricoButtonState(
                is_active=False,
                button_text='',
                button_url='',
                button_selector='',
                contracts_found=[],
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"❌ Ошибка анализа состояния кнопки: {e}")
            return MoricoButtonState(False, '', '', '', [], datetime.now())

    def is_buy_button(self, text: str) -> bool:
        """Проверка является ли текст кнопкой покупки"""
        text_lower = text.lower()
        buy_keywords = ['buy', 'купить', 'purchase', 'мори', 'mori', 'get', 'получить']
        return any(keyword in text_lower for keyword in buy_keywords)

    def is_button_active(self, button) -> bool:
        """Проверка активности кнопки"""
        try:
            # Проверяем стили
            style = button.get('style', '')
            if 'display:none' in style.replace(' ', '') or 'opacity:0' in style.replace(' ', ''):
                return False

            # Проверяем CSS классы
            classes = button.get('class', [])
            if isinstance(classes, list):
                classes = ' '.join(classes)

            if any(cls in classes.lower() for cls in ['disabled', 'inactive', 'hidden']):
                return False

            # Проверяем атрибуты
            if button.get('disabled'):
                return False

            # Если есть href или onclick - скорее всего активна
            if button.get('href') or button.get('onclick'):
                return True

            return True  # По умолчанию считаем активной

        except Exception as e:
            logger.debug(f"Ошибка проверки активности кнопки: {e}")
            return False

    def get_button_url(self, button) -> Optional[str]:
        """Получение URL из кнопки"""
        # Прямая ссылка
        href = button.get('href')
        if href:
            return href

        # JavaScript onclick
        onclick = button.get('onclick')
        if onclick:
            # Пытаемся извлечь URL из onclick
            import re
            url_match = re.search(r'(?:window\.open|location\.href|window\.location)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                                  onclick)
            if url_match:
                return url_match.group(1)

        return None

    def extract_contracts_from_button(self, button, button_url: str) -> List[str]:
        """Извлечение контрактов из кнопки"""
        contracts = []

        try:
            # Анализируем URL кнопки
            if button_url:
                from utils.addresses import extract_addresses_from_any_url
                url_contracts = extract_addresses_from_any_url(button_url)
                contracts.extend(url_contracts)

            # Анализируем onclick
            onclick = button.get('onclick', '')
            if onclick:
                from utils.addresses import extract_addresses_fast
                onclick_contracts = extract_addresses_fast(onclick, settings.ai)
                contracts.extend(onclick_contracts)

            # Анализируем data атрибуты
            for attr_name, attr_value in button.attrs.items():
                if 'contract' in attr_name.lower() or 'address' in attr_name.lower():
                    from utils.addresses import is_valid_solana_address
                    if is_valid_solana_address(attr_value):
                        contracts.append(attr_value)

        except Exception as e:
            logger.debug(f"Ошибка извлечения контрактов из кнопки: {e}")

        return list(set(contracts))  # Убираем дубликаты

    async def handle_button_changes(self, new_state: MoricoButtonState):
        """Обработка изменений в состоянии кнопки"""
        try:
            if not self.last_button_state:
                self.last_button_state = new_state
                return

            # Проверяем активацию кнопки
            if not self.last_button_state.is_active and new_state.is_active:
                logger.critical("🚨 КНОПКА 'КУПИТЬ МОРИ' СТАЛА АКТИВНОЙ!")
                self.stats['button_activations'] += 1

                # Проверяем появление контрактов
                if new_state.contracts_found:
                    logger.critical(f"🎯 КОНТРАКТЫ НАЙДЕНЫ В КНОПКЕ: {new_state.contracts_found}")
                    await self.trigger_trading(new_state)
                elif new_state.button_url:
                    logger.info(f"🔗 Кнопка ведет на: {new_state.button_url}")
                    # Анализируем страницу по ссылке
                    await self.analyze_button_target(new_state.button_url)

            # Проверяем появление новых контрактов
            elif new_state.contracts_found and new_state.contracts_found != self.last_button_state.contracts_found:
                logger.critical(f"🎯 НОВЫЕ КОНТРАКТЫ В КНОПКЕ: {new_state.contracts_found}")
                await self.trigger_trading(new_state)

            self.last_button_state = new_state

        except Exception as e:
            logger.error(f"❌ Ошибка обработки изменений кнопки: {e}")

    async def analyze_button_target(self, target_url: str):
        """Анализ страницы на которую ведет кнопка"""
        try:
            logger.info(f"🔍 Анализ целевой страницы: {target_url}")

            # Если это внешняя ссылка на DEX - извлекаем контракт
            if any(dex in target_url.lower() for dex in ['jup.ag', 'jupiter', 'raydium', 'dexscreener']):
                from utils.addresses import extract_addresses_from_any_url
                contracts = extract_addresses_from_any_url(target_url)

                if contracts:
                    logger.critical(f"🎯 КОНТРАКТ ИЗ ССЫЛКИ КНОПКИ: {contracts}")

                    # Создаем состояние для торговли
                    trading_state = MoricoButtonState(
                        is_active=True,
                        button_text="External DEX Link",
                        button_url=target_url,
                        button_selector="external_link",
                        contracts_found=contracts,
                        timestamp=datetime.now()
                    )

                    await self.trigger_trading(trading_state)
                    return

            # Если это внутренняя ссылка - загружаем и анализируем
            if target_url.startswith('/') or 'morico.in' in target_url:
                full_url = target_url if target_url.startswith('http') else f"https://morico.in{target_url}"

                content = await cloudflare_bypass.get_page_content(full_url)
                if content:
                    # Анализируем страницу на контракты
                    from utils.addresses import extract_addresses_fast
                    contracts = extract_addresses_fast(content, settings.ai)

                    if contracts:
                        logger.critical(f"🎯 КОНТРАКТ НА ЦЕЛЕВОЙ СТРАНИЦЕ: {contracts}")

                        trading_state = MoricoButtonState(
                            is_active=True,
                            button_text="Target Page",
                            button_url=full_url,
                            button_selector="target_page",
                            contracts_found=contracts,
                            timestamp=datetime.now()
                        )

                        await self.trigger_trading(trading_state)

        except Exception as e:
            logger.error(f"❌ Ошибка анализа целевой страницы: {e}")

    async def trigger_trading(self, button_state: MoricoButtonState):
        """Запуск торговли"""
        try:
            if not self.trading_callback:
                logger.warning("⚠️ Trading callback не настроен")
                return

            self.stats['contracts_found'] += len(button_state.contracts_found)

            trading_data = {
                'platform': 'morico_website',
                'source': 'morico.in',
                'author': 'MORICO Official',
                'url': self.url,
                'contracts': button_state.contracts_found,
                'confidence': 0.95,  # Высокая уверенность для официального сайта
                'urgency': 'high',
                'timestamp': button_state.timestamp,
                'content_preview': f"Button: {button_state.button_text}",
                'button_info': {
                    'text': button_state.button_text,
                    'url': button_state.button_url,
                    'selector': button_state.button_selector,
                    'is_active': button_state.is_active
                }
            }

            logger.critical("🚨 ЗАПУСК ТОРГОВЛИ С САЙТА MORICO!")
            await self.trading_callback(trading_data)

        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговли: {e}")

    async def health_check(self) -> Dict:
        """Проверка здоровья монитора MORICO"""
        try:
            health = await cloudflare_bypass.health_check(self.url)

            return {
                "status": "healthy" if health['status'] == 'working' else "degraded",
                "morico_accessible": health['status'] == 'working',
                "cloudflare_bypass": health['method'],
                "running": self.running,
                "last_button_active": self.last_button_state.is_active if self.last_button_state else False,
                "stats": self.stats
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> Dict:
        """Получение статистики мониторинга"""
        return {
            **self.stats,
            "running": self.running,
            "url": self.url,
            "check_interval": self.check_interval,
            "last_check": datetime.now().isoformat() if self.running else None,
            "button_state": {
                "is_active": self.last_button_state.is_active if self.last_button_state else False,
                "text": self.last_button_state.button_text if self.last_button_state else '',
                "has_contracts": bool(self.last_button_state.contracts_found) if self.last_button_state else False
            }
        }


# Глобальный экземпляр монитора
morico_monitor = MoricoSiteMonitor()