#!/usr/bin/env python3
"""
🎯 MORI Sniper Bot Setup Script
Устанавливает все зависимости и настраивает систему
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path


def print_header():
    """Печать заголовка"""
    print("🎯 MORI Token Sniper Bot - Установка")
    print("=" * 50)
    print()


def check_python_version():
    """Проверка версии Python"""
    print("🐍 Проверка версии Python...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"   Текущая версия: {version.major}.{version.minor}.{version.micro}")
        return False

    print(f"✅ Python {version.major}.{version.minor}.{version.micro} подходит")
    return True


def install_package(package, description=""):
    """Установка пакета"""
    try:
        print(f"📦 Устанавливаем {package}...")
        if description:
            print(f"   {description}")

        subprocess.check_call([
            sys.executable, "-m", "pip", "install", package, "--upgrade"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"✅ {package} установлен")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Ошибка установки {package}")
        return False


def create_directories():
    """Создание необходимых директорий"""
    print("📁 Создание директорий...")

    directories = ['logs', 'data', 'sessions']

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Директория {directory} создана")


def setup_env_file():
    """Настройка .env файла"""
    print("⚙️ Настройка конфигурации...")

    if not Path('.env').exists():
        if Path('.env.example').exists():
            shutil.copy('.env.example', '.env')
            print("✅ Файл .env создан из .env.example")
            print("⚠️ ВАЖНО: Отредактируйте .env файл с вашими настройками")
        else:
            print("❌ Файл .env.example не найден")
            return False
    else:
        print("✅ Файл .env уже существует")

    return True


def install_dependencies():
    """Установка всех зависимостей"""
    print("📦 Установка зависимостей...")
    print()

    # Основные пакеты
    core_packages = [
        ("wheel", "Основные инструменты"),
        ("setuptools", "Инструменты сборки"),
        ("pip>=23.0", "Менеджер пакетов"),
    ]

    print("1️⃣ Основные инструменты:")
    for package, desc in core_packages:
        install_package(package, desc)
    print()

    # Асинхронные фреймворки
    async_packages = [
        ("aiohttp>=3.8.0", "HTTP клиент/сервер"),
        ("aiofiles>=23.0.0", "Асинхронная работа с файлами"),
        ("asyncio", "Асинхронное программирование"),
    ]

    print("2️⃣ Асинхронные библиотеки:")
    for package, desc in async_packages:
        install_package(package, desc)
    print()

    # Solana и блокчейн
    blockchain_packages = [
        ("solana>=0.30.0", "Solana Python SDK"),
        ("base58>=2.1.0", "Base58 кодирование"),
        ("solders>=0.20.0", "Rust-based Solana tools"),
    ]

    print("3️⃣ Solana блокчейн:")
    for package, desc in blockchain_packages:
        install_package(package, desc)
    print()

    # Telegram API
    telegram_packages = [
        ("telethon>=1.34.0", "Telegram User Bot (РЕКОМЕНДУЕТСЯ)"),
        ("python-telegram-bot>=20.0", "Telegram Bot API (резерв)"),
    ]

    print("4️⃣ Telegram API:")
    for package, desc in telegram_packages:
        install_package(package, desc)
    print()

    # Социальные сети
    social_packages = [
        ("tweepy>=4.12.0", "Twitter API"),
        ("beautifulsoup4>=4.11.0", "Парсинг веб-страниц"),
        ("lxml>=4.9.0", "XML/HTML парсер"),
    ]

    print("5️⃣ Социальные сети и веб:")
    for package, desc in social_packages:
        install_package(package, desc)
    print()

    # Утилиты
    utility_packages = [
        ("python-dotenv>=1.0.0", "Загрузка .env файлов"),
        ("loguru>=0.7.0", "Продвинутое логирование"),
        ("requests>=2.28.0", "HTTP запросы"),
        ("psutil>=5.9.0", "Мониторинг системы"),
    ]

    print("6️⃣ Утилиты:")
    for package, desc in utility_packages:
        install_package(package, desc)
    print()

    # Криптография и безопасность
    crypto_packages = [
        ("mnemonic>=0.20", "Работа с seed phrases"),
        ("cryptography>=3.4.0", "Криптографические функции"),
    ]

    print("7️⃣ Криптография:")
    for package, desc in crypto_packages:
        install_package(package, desc)
    print()

    # Опциональные AI пакеты
    print("8️⃣ AI анализ (опционально):")
    ai_packages = [
        ("openai>=1.3.0", "OpenAI GPT API"),
    ]

    for package, desc in ai_packages:
        response = input(f"Установить {package} ({desc})? [y/N]: ").lower()
        if response in ['y', 'yes', 'да']:
            install_package(package, desc)
        else:
            print(f"⏭️ Пропускаем {package}")
    print()

    # Оптимизация производительности (Linux/Mac)
    if sys.platform in ['linux', 'darwin']:
        print("9️⃣ Оптимизация производительности:")
        perf_packages = [
            ("uvloop>=0.19.0", "Быстрый event loop"),
        ]

        for package, desc in perf_packages:
            install_package(package, desc)
    print()


def run_tests():
    """Запуск тестов"""
    print("🧪 Запуск тестов...")

    try:
        # Проверяем импорты
        result = subprocess.run([
            sys.executable, "-c",
            "import config.settings; import ai.analyzer; import trading.jupiter; print('✅ Все модули импортируются')"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Базовые импорты работают")
        else:
            print("❌ Ошибка импортов:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

    return True


def print_next_steps():
    """Печать следующих шагов"""
    print()
    print("🎉 УСТАНОВКА ЗАВЕРШЕНА!")
    print("=" * 50)
    print()
    print("📋 СЛЕДУЮЩИЕ ШАГИ:")
    print()
    print("1️⃣ Настройте .env файл:")
    print("   nano .env")
    print()
    print("2️⃣ Получите Telegram API ключи:")
    print("   https://my.telegram.org/apps")
    print()
    print("3️⃣ Настройте Solana кошелек:")
    print("   - Экспортируйте приватный ключ из Phantom")
    print("   - Или используйте seed phrase")
    print()
    print("4️⃣ Протестируйте систему:")
    print("   python test_telegram_user.py")
    print("   python test_sniper.py")
    print()
    print("5️⃣ Запустите бота:")
    print("   python main.py")
    print()
    print("📚 ДОКУМЕНТАЦИЯ:")
    print("   - README.md - полное руководство")
    print("   - config_examples.md - примеры настроек")
    print()
    print("⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ:")
    print("   - Начните с devnet для тестов")
    print("   - Используйте малые суммы сначала")
    print("   - User Bot быстрее Bot API")
    print("   - Регулярно проверяйте логи")
    print()


def main():
    """Главная функция установки"""
    print_header()

    # Проверка Python
    if not check_python_version():
        sys.exit(1)
    print()

    # Создание директорий
    create_directories()
    print()

    # Установка зависимостей
    install_dependencies()

    # Настройка конфигурации
    setup_env_file()
    print()

    # Тестирование
    if run_tests():
        print("✅ Система готова к работе")
    else:
        print("⚠️ Некоторые компоненты требуют настройки")
    print()

    # Следующие шаги
    print_next_steps()


if __name__ == "__main__":
    main()