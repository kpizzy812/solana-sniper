#!/usr/bin/env python3
"""
🧙‍♂️ MORI Sniper Bot Configuration Wizard
Интерактивная настройка конфигурации для новых пользователей
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional


class ConfigWizard:
    """Мастер настройки конфигурации"""

    def __init__(self):
        self.config = {}
        self.env_file_path = Path('.env')

    def print_header(self):
        """Печать заголовка"""
        print("🧙‍♂️ MORI Sniper Bot - Мастер Настройки")
        print("=" * 50)
        print()
        print("Этот мастер поможет вам настроить бота пошагово")
        print("Нажмите Enter для значения по умолчанию")
        print()

    def ask_input(self, prompt: str, default: str = "", required: bool = False, secret: bool = False) -> str:
        """Запрос ввода от пользователя"""
        if default:
            display_prompt = f"{prompt} [{default}]: "
        else:
            display_prompt = f"{prompt}: "

        while True:
            if secret:
                import getpass
                value = getpass.getpass(display_prompt)
            else:
                value = input(display_prompt).strip()

            if value:
                return value
            elif default:
                return default
            elif required:
                print("❌ Это поле обязательно для заполнения")
                continue
            else:
                return ""

    def ask_yes_no(self, prompt: str, default: bool = True) -> bool:
        """Запрос да/нет"""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{prompt} [{default_str}]: ").strip().lower()

        if not response:
            return default

        return response in ['y', 'yes', 'да', 'д']

    def choose_option(self, prompt: str, options: Dict[str, str], default: str = None) -> str:
        """Выбор опции из списка"""
        print(f"\n{prompt}")
        for key, description in options.items():
            marker = " (по умолчанию)" if key == default else ""
            print(f"  {key}) {description}{marker}")

        while True:
            choice = input("Выберите опцию: ").strip()

            if choice in options:
                return choice
            elif not choice and default:
                return default
            else:
                print("❌ Неверный выбор. Попробуйте снова.")

    def configure_solana(self):
        """Настройка Solana"""
        print("⛓️ НАСТРОЙКА SOLANA БЛОКЧЕЙНА")
        print("-" * 30)

        # Выбор сети
        networks = {
            "1": "Mainnet (РЕАЛЬНЫЕ ДЕНЬГИ)",
            "2": "Devnet (ТЕСТОВАЯ СЕТЬ)"
        }

        network_choice = self.choose_option(
            "Выберите сеть Solana:",
            networks,
            "2"
        )

        if network_choice == "1":
            self.config['SOLANA_RPC_URL'] = 'https://api.mainnet-beta.solana.com'
            print("⚠️ ВНИМАНИЕ: Вы выбрали mainnet с реальными деньгами!")
        else:
            self.config['SOLANA_RPC_URL'] = 'https://api.devnet.solana.com'
            print("✅ Devnet выбран для безопасного тестирования")

        # Приватный ключ или seed phrase
        key_methods = {
            "1": "Приватный ключ (base58)",
            "2": "Seed phrase (12/24 слова)"
        }

        key_method = self.choose_option(
            "Как вы хотите предоставить ключ кошелька:",
            key_methods,
            "1"
        )

        if key_method == "1":
            private_key = self.ask_input(
                "Введите приватный ключ (base58 из Phantom)",
                required=True,
                secret=True
            )
            self.config['SOLANA_PRIVATE_KEY'] = private_key
        else:
            seed_phrase = self.ask_input(
                "Введите seed phrase (12-24 слова)",
                required=True,
                secret=True
            )
            self.config['SOLANA_SEED_PHRASE'] = seed_phrase

        print("✅ Solana настроен")

    def configure_trading(self):
        """Настройка торговли"""
        print("\n💰 НАСТРОЙКА ТОРГОВЛИ")
        print("-" * 20)

        # Стратегия торговли
        strategies = {
            "1": "Консервативная (новички) - 0.05 SOL x 1",
            "2": "Умеренная (рекомендуется) - 0.1 SOL x 3",
            "3": "Агрессивная (опытные) - 0.2 SOL x 5",
            "4": "Кастомная (настрою сам)"
        }

        strategy = self.choose_option(
            "Выберите стратегию торговли:",
            strategies,
            "2"
        )

        if strategy == "1":
            self.config['TRADE_AMOUNT_SOL'] = '0.05'
            self.config['NUM_PURCHASES'] = '1'
            self.config['SLIPPAGE_BPS'] = '1000'
        elif strategy == "2":
            self.config['TRADE_AMOUNT_SOL'] = '0.1'
            self.config['NUM_PURCHASES'] = '3'
            self.config['SLIPPAGE_BPS'] = '500'
        elif strategy == "3":
            self.config['TRADE_AMOUNT_SOL'] = '0.2'
            self.config['NUM_PURCHASES'] = '5'
            self.config['SLIPPAGE_BPS'] = '500'
        else:
            # Кастомная настройка
            self.config['TRADE_AMOUNT_SOL'] = self.ask_input(
                "Размер одной сделки (SOL)", "0.1"
            )
            self.config['NUM_PURCHASES'] = self.ask_input(
                "Количество одновременных покупок", "3"
            )
            self.config['SLIPPAGE_BPS'] = self.ask_input(
                "Проскальзывание (BPS, 500 = 5%)", "500"
            )

        print(f"✅ Стратегия: {self.config['NUM_PURCHASES']} x {self.config['TRADE_AMOUNT_SOL']} SOL")

    def configure_telegram(self):
        """Настройка Telegram"""
        print("\n📱 НАСТРОЙКА TELEGRAM МОНИТОРИНГА")
        print("-" * 35)

        # Выбор метода
        if self.ask_yes_no("Использовать Telegram User Bot (рекомендуется)?", True):
            self.config['USE_TELEGRAM_USER_BOT'] = 'true'

            print("\n📋 Для User Bot нужны API ключи с https://my.telegram.org/apps")
            print("1. Идите на https://my.telegram.org/apps")
            print("2. Войдите с номером телефона")
            print("3. Создайте приложение")
            print("4. Скопируйте API ID и API Hash")
            print()

            api_id = self.ask_input("API ID", required=True)
            api_hash = self.ask_input("API Hash", required=True)
            phone = self.ask_input("Номер телефона (+1234567890)", required=True)

            self.config['TELEGRAM_API_ID'] = api_id
            self.config['TELEGRAM_API_HASH'] = api_hash
            self.config['TELEGRAM_PHONE_NUMBER'] = phone

            # Каналы и группы для мониторинга
            print("\n📺 Настройка каналов для мониторинга:")
            channel1 = self.ask_input("Канал 1 (@username или ссылка)", "@example_channel")
            if channel1:
                self.config['USER_BOT_CHANNEL_1'] = channel1

            channel2 = self.ask_input("Канал 2 (опционально)")
            if channel2:
                self.config['USER_BOT_CHANNEL_2'] = channel2

            print("\n👥 Настройка групп для мониторинга:")
            group1 = self.ask_input("Группа 1 (@username или ID)")
            if group1:
                self.config['USER_BOT_GROUP_1'] = group1

            print("\n👑 Настройка админов (их сообщения будут обрабатываться):")
            admin1 = self.ask_input("Админ 1 (username без @)", required=True)
            self.config['USER_BOT_ADMIN_1'] = admin1

            admin2 = self.ask_input("Админ 2 (опционально)")
            if admin2:
                self.config['USER_BOT_ADMIN_2'] = admin2

        else:
            self.config['USE_TELEGRAM_USER_BOT'] = 'false'

        # Bot API как резерв
        if self.ask_yes_no("Настроить Telegram Bot API как резерв?", False):
            self.config['USE_TELEGRAM_BOT_API'] = 'true'

            print("\n🤖 Для Bot API нужен токен от @BotFather")
            bot_token = self.ask_input("Bot Token", required=True)
            self.config['TELEGRAM_BOT_TOKEN'] = bot_token
        else:
            self.config['USE_TELEGRAM_BOT_API'] = 'false'

        print("✅ Telegram настроен")

    def configure_additional(self):
        """Настройка дополнительных функций"""
        print("\n🔧 ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ")
        print("-" * 25)

        # Twitter
        if self.ask_yes_no("Настроить мониторинг Twitter?", False):
            print("📋 Нужен Bearer Token с https://developer.twitter.com")
            twitter_token = self.ask_input("Twitter Bearer Token")
            if twitter_token:
                self.config['TWITTER_BEARER_TOKEN'] = twitter_token

                username1 = self.ask_input("Twitter аккаунт 1 (без @)")
                if username1:
                    self.config['TWITTER_USERNAME_1'] = username1

        # Website мониторинг
        if self.ask_yes_no("Настроить мониторинг веб-сайтов?", False):
            website1 = self.ask_input("URL сайта 1")
            if website1:
                self.config['WEBSITE_URL_1'] = website1

        # AI анализ
        if self.ask_yes_no("Настроить AI анализ (OpenAI)?", False):
            print("📋 Нужен API ключ с https://platform.openai.com/api-keys")
            openai_key = self.ask_input("OpenAI API Key")
            if openai_key:
                self.config['OPENAI_API_KEY'] = openai_key

        # Безопасность
        print("\n🛡️ Настройки безопасности:")
        self.config['MIN_LIQUIDITY'] = self.ask_input(
            "Минимальная ликвидность (SOL)", "5"
        )
        self.config['MAX_PRICE_IMPACT'] = self.ask_input(
            "Максимальное проскальзывание (%)", "15.0"
        )

        print("✅ Дополнительные настройки завершены")

    def save_config(self):
        """Сохранение конфигурации в .env"""
        print("\n💾 СОХРАНЕНИЕ КОНФИГУРАЦИИ")
        print("-" * 25)

        # Загружаем шаблон
        if not Path('.env.example').exists():
            print("❌ Файл .env.example не найден")
            return False

        with open('.env.example', 'r', encoding='utf-8') as f:
            content = f.read()

        # Заменяем значения
        for key, value in self.config.items():
            # Ищем строку с ключом
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith(f'{key}=') or line.startswith(f'#{key}='):
                    lines[i] = f'{key}={value}'
                    break

            content = '\n'.join(lines)

        # Сохраняем
        try:
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Конфигурация сохранена в {self.env_file_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
            return False

    def show_summary(self):
        """Показ итогов"""
        print("\n📊 ИТОГИ НАСТРОЙКИ")
        print("=" * 20)

        print(f"⛓️ Сеть: {'Mainnet' if 'mainnet' in self.config.get('SOLANA_RPC_URL', '') else 'Devnet'}")
        print(f"💰 Торговля: {self.config.get('NUM_PURCHASES', '?')} x {self.config.get('TRADE_AMOUNT_SOL', '?')} SOL")

        telegram_method = "User Bot" if self.config.get('USE_TELEGRAM_USER_BOT') == 'true' else "Bot API"
        print(f"📱 Telegram: {telegram_method}")

        if self.config.get('TWITTER_BEARER_TOKEN'):
            print("🐦 Twitter: Включен")

        if self.config.get('OPENAI_API_KEY'):
            print("🧠 AI анализ: Включен")

        print("\n🚀 СЛЕДУЮЩИЕ ШАГИ:")
        print("1. python test_telegram_user.py - тест авторизации")
        print("2. python test_sniper.py - тест всей системы")
        print("3. python main.py - запуск бота")

        print("\n⚠️ ВАЖНО:")
        print("- Начните с devnet для тестов")
        print("- Используйте малые суммы")
        print("- Проверяйте логи регулярно")

    def run(self):
        """Запуск мастера настройки"""
        self.print_header()

        try:
            # Основные настройки
            self.configure_solana()
            self.configure_trading()
            self.configure_telegram()
            self.configure_additional()

            # Сохранение
            if self.save_config():
                self.show_summary()
                return True
            else:
                print("❌ Не удалось сохранить конфигурацию")
                return False

        except KeyboardInterrupt:
            print("\n❌ Настройка прервана пользователем")
            return False
        except Exception as e:
            print(f"\n❌ Ошибка настройки: {e}")
            return False


def main():
    """Главная функция"""
    wizard = ConfigWizard()

    if wizard.env_file_path.exists():
        print("⚠️ Файл .env уже существует")
        if not input("Перезаписать? [y/N]: ").lower().startswith('y'):
            print("❌ Настройка отменена")
            return

    success = wizard.run()
    if success:
        print("\n🎉 Настройка завершена успешно!")
    else:
        print("\n❌ Настройка не завершена")
        sys.exit(1)


if __name__ == "__main__":
    main()