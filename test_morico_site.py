#!/usr/bin/env python3
"""
🧪 Тест доступа к сайту https://morico.in/
Проверяем Cloudflare защиту и ищем кнопку "Купить МОРИ"
"""

import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup


class MoricoSiteTester:
    """Тестер сайта MORICO"""

    def __init__(self):
        self.url = "https://morico.in/"
        self.session = None

    async def test_site_access(self):
        """Тест доступа к сайту"""
        print("🧪 Тестирование доступа к https://morico.in/")
        print("=" * 60)

        # Создаем сессию с разными User-Agent
        await self.test_with_different_headers()

    async def test_with_different_headers(self):
        """Тест с разными заголовками"""

        # Разные User-Agent для обхода Cloudflare
        user_agents = [
            # Обычный браузер
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            # Safari
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.1 Safari/537.36',
        ]

        for i, ua in enumerate(user_agents):
            print(f"\n🔍 Тест {i + 1}: {ua[:50]}...")

            try:
                timeout = aiohttp.ClientTimeout(total=30)
                headers = {
                    'User-Agent': ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }

                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    start_time = time.time()

                    async with session.get(self.url) as response:
                        response_time = (time.time() - start_time) * 1000
                        content = await response.text()

                        print(f"   📊 Статус: {response.status}")
                        print(f"   ⏱️ Время ответа: {response_time:.0f}ms")
                        print(f"   📏 Размер контента: {len(content)} символов")

                        # Проверяем признаки Cloudflare
                        if 'cloudflare' in content.lower() or 'checking your browser' in content.lower():
                            print("   🛡️ Cloudflare защита: АКТИВНА")
                            print("   ⚠️ Требуется обход защиты")
                        else:
                            print("   ✅ Cloudflare защита: обойдена или отсутствует")

                            # Анализируем содержимое
                            await self.analyze_content(content)
                            return  # Успешно получили контент

            except Exception as e:
                print(f"   ❌ Ошибка: {e}")

        print("\n❌ Все попытки доступа неудачны")

    async def analyze_content(self, content: str):
        """Анализ содержимого сайта"""
        print("\n🔍 АНАЛИЗ СОДЕРЖИМОГО САЙТА:")

        try:
            soup = BeautifulSoup(content, 'html.parser')

            # Ищем заголовок страницы
            title = soup.find('title')
            if title:
                print(f"📄 Заголовок: {title.get_text().strip()}")

            # Ищем кнопки "Купить" или "Buy"
            buy_buttons = []

            # Поиск по тексту
            possible_selectors = [
                'button', 'a', '.btn', '.button', '[class*="buy"]', '[class*="purchase"]',
                '[id*="buy"]', '[id*="purchase"]', 'input[type="button"]'
            ]

            for selector in possible_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip().lower()
                    if any(word in text for word in ['buy', 'купить', 'purchase', 'мори', 'mori']):
                        buy_buttons.append(element)

            print(f"\n🔘 Найдено потенциальных кнопок покупки: {len(buy_buttons)}")

            for i, button in enumerate(buy_buttons):
                print(f"\n   Кнопка {i + 1}:")
                print(f"   📝 Текст: {button.get_text().strip()}")
                print(f"   🏷️ Tag: {button.name}")
                print(f"   🎨 Class: {button.get('class', [])}")
                print(f"   🆔 ID: {button.get('id', 'нет')}")
                print(f"   🔗 Href: {button.get('href', 'нет')}")
                print(f"   🎯 Onclick: {button.get('onclick', 'нет')}")

                # Проверяем стили
                style = button.get('style', '')
                if style:
                    print(f"   🎨 Style: {style}")
                    if 'display:none' in style or 'opacity:0' in style:
                        print("   👻 КНОПКА СКРЫТА!")

            # Ищем любые Solana адреса в коде
            import re
            solana_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
            addresses = re.findall(solana_pattern, content)

            if addresses:
                print(f"\n🎯 Найдены потенциальные Solana адреса: {len(addresses)}")
                for addr in addresses[:5]:  # Показываем первые 5
                    print(f"   📍 {addr}")
            else:
                print("\n❌ Solana адреса не найдены")

            # Ищем JavaScript код связанный с покупкой
            scripts = soup.find_all('script')
            print(f"\n📜 JavaScript скриптов: {len(scripts)}")

            for script in scripts:
                script_content = script.get_text()
                if any(word in script_content.lower() for word in ['buy', 'purchase', 'contract', 'solana', 'jupiter']):
                    print("   🎯 Найден JS код связанный с покупкой")
                    # Показываем только релевантные строки
                    lines = script_content.split('\n')
                    for line in lines:
                        if any(word in line.lower() for word in ['buy', 'contract', 'solana']):
                            print(f"      📜 {line.strip()[:100]}")
                    break

        except Exception as e:
            print(f"❌ Ошибка анализа контента: {e}")

    async def test_with_selenium_headers(self):
        """Тест с заголовками похожими на Selenium (если нужно)"""
        # Можно добавить позже если aiohttp не сработает
        pass


async def main():
    """Главная функция"""
    tester = MoricoSiteTester()
    await tester.test_site_access()


if __name__ == "__main__":
    asyncio.run(main())