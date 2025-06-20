#!/usr/bin/env python3
"""
🧪 Тест мониторинга сайта MORICO.IN
Проверка обхода Cloudflare и мониторинга кнопки покупки
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from loguru import logger
from monitors.morico_monitor import morico_monitor
from monitors.cloudflare_bypass import cloudflare_bypass


class MoricoMonitorTester:
    """Тестер мониторинга MORICO"""

    def __init__(self):
        self.test_results = {}
        self.received_signals = []

    async def run_all_tests(self):
        """Запуск всех тестов MORICO мониторинга"""
        logger.info("🧪 Тестирование мониторинга MORICO.IN")
        logger.info("=" * 60)

        # Тест Cloudflare bypass
        await self.test_cloudflare_bypass()

        # Тест доступа к сайту
        await self.test_site_access()

        # Тест анализа кнопки
        await self.test_button_analysis()

        # Тест живого мониторинга
        if self.test_results.get('site_access', False):
            await self.test_live_monitoring()

        # Итоговый отчет
        self.print_summary()

    async def test_cloudflare_bypass(self):
        """Тест системы обхода Cloudflare"""
        logger.info("🛡️ Тестирование Cloudflare bypass...")

        try:
            # Проверяем доступные методы
            logger.info("📋 Проверка доступных методов обхода:")

            try:
                import cloudscraper
                logger.info("   ✅ CloudScraper доступен")
            except ImportError:
                logger.warning("   ⚠️ CloudScraper недоступен (установите: pip install cloudscraper)")

            try:
                from playwright.async_api import async_playwright
                logger.info("   ✅ Playwright доступен")
            except ImportError:
                logger.warning("   ⚠️ Playwright недоступен (установите: pip install playwright)")

            # Инициализируем bypass
            await cloudflare_bypass.start()
            logger.info(f"🔧 Выбранный метод: {cloudflare_bypass.method}")

            self.test_results['cloudflare_bypass'] = True

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования Cloudflare bypass: {e}")
            self.test_results['cloudflare_bypass'] = False

    async def test_site_access(self):
        """Тест доступа к сайту MORICO"""
        logger.info("🌐 Тестирование доступа к MORICO.IN...")

        try:
            # Проверяем health check
            health = await cloudflare_bypass.health_check("https://morico.in/")

            logger.info(f"📊 Результат проверки:")
            logger.info(f"   Статус: {health['status']}")
            logger.info(f"   Метод: {health['method']}")
            logger.info(f"   Время ответа: {health.get('response_time_ms', 0):.0f}ms")
            logger.info(f"   Размер контента: {health.get('content_size', 0)} символов")

            if health['status'] == 'working':
                logger.success("✅ Доступ к MORICO.IN получен")
                self.test_results['site_access'] = True
            elif health['status'] == 'blocked':
                logger.warning("⚠️ Cloudflare блокировка активна")
                self.test_results['site_access'] = False
            else:
                logger.error("❌ Доступ к MORICO.IN недоступен")
                self.test_results['site_access'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования доступа: {e}")
            self.test_results['site_access'] = False

    async def test_button_analysis(self):
        """Тест анализа кнопки покупки"""
        logger.info("🔘 Тестирование анализа кнопки...")

        try:
            # Получаем контент сайта
            content = await cloudflare_bypass.get_page_content("https://morico.in/")

            if not content:
                logger.error("❌ Не удалось получить контент для анализа")
                self.test_results['button_analysis'] = False
                return

            # Анализируем состояние кнопки
            button_state = morico_monitor.analyze_button_state(content)

            logger.info(f"📊 Состояние кнопки:")
            logger.info(f"   Активна: {button_state.is_active}")
            logger.info(f"   Текст: '{button_state.button_text}'")
            logger.info(f"   URL: {button_state.button_url}")
            logger.info(f"   Селектор: {button_state.button_selector}")
            logger.info(f"   Контракты: {button_state.contracts_found}")

            if button_state.button_text:
                logger.success("✅ Кнопка найдена")
                if button_state.is_active:
                    logger.critical("🚨 КНОПКА УЖЕ АКТИВНА!")
                    if button_state.contracts_found:
                        logger.critical(f"🎯 КОНТРАКТЫ УЖЕ ДОСТУПНЫ: {button_state.contracts_found}")
                else:
                    logger.info("⏸️ Кнопка найдена но неактивна (ожидаемо)")

                self.test_results['button_analysis'] = True
            else:
                logger.warning("⚠️ Кнопка не найдена или не распознана")
                self.test_results['button_analysis'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования анализа кнопки: {e}")
            self.test_results['button_analysis'] = False

    async def test_live_monitoring(self):
        """Тест живого мониторинга"""
        logger.info("👁️ Тест живого мониторинга...")

        try:
            # Подключаем тестовый callback
            original_callback = morico_monitor.trading_callback
            morico_monitor.trading_callback = self.test_trading_callback

            # Запускаем монитор
            if await morico_monitor.start():
                logger.success("✅ MORICO монитор запущен")

                logger.critical("🚨 МОНИТОРИНГ АКТИВЕН!")
                logger.info("⏱️ Мониторинг на 30 секунд...")
                logger.info("💡 Если кнопка уже активна, сигнал придет сразу")

                start_time = time.time()
                monitoring_duration = 30

                while time.time() - start_time < monitoring_duration:
                    await asyncio.sleep(1)

                    # Показываем прогресс
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0 and elapsed > 0:
                        remaining = monitoring_duration - elapsed
                        stats = morico_monitor.get_stats()
                        logger.info(
                            f"⏱️ Осталось {remaining}s | проверок: {stats['checks_performed']} | сигналов: {len(self.received_signals)}")

                # Останавливаем монитор
                await morico_monitor.stop()

                # Восстанавливаем callback
                morico_monitor.trading_callback = original_callback

                # Анализируем результаты
                if self.received_signals:
                    logger.critical(f"🚨 ПОЛУЧЕНО {len(self.received_signals)} ТОРГОВЫХ СИГНАЛОВ!")
                    for i, signal in enumerate(self.received_signals):
                        logger.info(f"   Сигнал {i + 1}: {signal.get('contracts', [])}")
                    self.test_results['live_monitoring'] = True
                else:
                    logger.info("📄 Торговых сигналов не получено (кнопка еще неактивна)")
                    self.test_results['live_monitoring'] = None  # Не провал

            else:
                logger.error("❌ Не удалось запустить MORICO монитор")
                self.test_results['live_monitoring'] = False

        except Exception as e:
            logger.error(f"❌ Ошибка тестирования живого мониторинга: {e}")
            self.test_results['live_monitoring'] = False

    async def test_trading_callback(self, signal_data: dict):
        """Тестовый callback для торговых сигналов"""
        try:
            logger.critical("🚨 ПОЛУЧЕН ТОРГОВЫЙ СИГНАЛ ОТ MORICO!")
            logger.info(f"🎯 Контракты: {signal_data.get('contracts', [])}")
            logger.info(f"📱 Источник: {signal_data.get('source', 'unknown')}")
            logger.info(f"🔘 Кнопка: {signal_data.get('button_info', {}).get('text', 'unknown')}")

            self.received_signals.append(signal_data)

        except Exception as e:
            logger.error(f"❌ Ошибка в тестовом callback: {e}")

    def print_summary(self):
        """Итоговый отчет"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 ИТОГИ ТЕСТИРОВАНИЯ MORICO МОНИТОРИНГА")
        logger.info("=" * 60)

        total_tests = 0
        passed_tests = 0

        for test_name, result in self.test_results.items():
            if result is None:
                status = "⏭️ ПРОПУЩЕН"
            elif result:
                status = "✅ ПРОЙДЕН"
                passed_tests += 1
                total_tests += 1
            else:
                status = "❌ ПРОВАЛЕН"
                total_tests += 1

            logger.info(f"{test_name.replace('_', ' ').title():<25} {status}")

        logger.info("=" * 60)

        if passed_tests == total_tests and total_tests > 0:
            logger.success(f"🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({passed_tests}/{total_tests})")
            logger.success("🚀 MORICO мониторинг готов к работе!")
        elif total_tests == 0:
            logger.warning("⚠️ Все тесты пропущены")
        else:
            logger.warning(f"⚠️ Тесты пройдены частично ({passed_tests}/{total_tests})")

        logger.info("\n💡 СЛЕДУЮЩИЕ ШАГИ:")
        logger.info("1. Установите библиотеки: pip install cloudscraper playwright")
        logger.info("2. Добавьте в main.py интеграцию MORICO монитора")
        logger.info("3. Запустите полный бот для мониторинга активации кнопки")

        if self.received_signals:
            logger.critical(f"\n🚨 ВАЖНО: Получено {len(self.received_signals)} сигналов!")
            logger.critical("Возможно кнопка уже активна!")

    async def cleanup(self):
        """Очистка ресурсов"""
        try:
            await cloudflare_bypass.stop()
        except:
            pass


async def main():
    """Главная функция"""
    print("🧪 Тест мониторинга MORICO.IN")
    print("=" * 50)

    tester = MoricoMonitorTester()

    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        logger.info("❌ Тест прерван пользователем")
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())