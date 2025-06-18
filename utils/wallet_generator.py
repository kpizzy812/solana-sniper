#!/usr/bin/env python3
"""
💰 MORI Sniper Bot - Генератор множественных кошельков
Создание пула кошельков для снижения риска попадания в блэклист
"""

import os
import json
import secrets
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

# Проверяем доступность библиотек
try:
    from solders.keypair import Keypair
    from mnemonic import Mnemonic
    import base58

    CRYPTO_LIBS_AVAILABLE = True
except ImportError:
    CRYPTO_LIBS_AVAILABLE = False
    print("❌ Установите библиотеки: pip install solders mnemonic")


@dataclass
class WalletInfo:
    """Информация о кошельке"""
    index: int
    address: str
    private_key: str
    seed_phrase: str
    balance_sol: float = 0.0
    reserved_gas: float = 0.02  # Резерв на газ
    available_balance: float = 0.0

    def update_balance(self, new_balance: float):
        """Обновление баланса с учетом резерва"""
        self.balance_sol = new_balance
        self.available_balance = max(0, new_balance - self.reserved_gas)


class MultiWalletGenerator:
    """Генератор и менеджер множественных кошельков"""

    def __init__(self, wallets_dir: str = "wallets"):
        self.wallets_dir = Path(wallets_dir)
        self.wallets_dir.mkdir(exist_ok=True)

        # Файлы для хранения данных
        self.wallets_file = self.wallets_dir / "generated_wallets.json"
        self.addresses_file = self.wallets_dir / "addresses_for_deposit.txt"

        # Загруженные кошельки
        self.wallets: List[WalletInfo] = []

        if not CRYPTO_LIBS_AVAILABLE:
            raise ImportError("Установите: pip install solders mnemonic")

    def generate_wallets(self, count: int) -> List[WalletInfo]:
        """
        Генерация указанного количества кошельков

        Args:
            count: Количество кошельков для генерации

        Returns:
            List[WalletInfo]: Список сгенерированных кошельков
        """
        print(f"🔄 Генерация {count} новых кошельков...")

        mnemo = Mnemonic("english")
        generated_wallets = []

        for i in range(count):
            try:
                # Генерируем случайную энтропию
                entropy = secrets.token_bytes(16)  # 128 бит энтропии

                # Создаем seed phrase
                seed_phrase = mnemo.to_mnemonic(entropy)

                # Генерируем keypair из seed
                seed = mnemo.to_seed(seed_phrase)
                keypair = Keypair.from_seed(seed[:32])

                # Получаем данные кошелька
                address = str(keypair.pubkey())
                private_key = base58.b58encode(bytes(keypair)).decode('utf-8')

                wallet = WalletInfo(
                    index=i + 1,
                    address=address,
                    private_key=private_key,
                    seed_phrase=seed_phrase
                )

                generated_wallets.append(wallet)
                print(f"✅ Кошелек {i + 1}: {address}")

            except Exception as e:
                print(f"❌ Ошибка генерации кошелька {i + 1}: {e}")
                continue

        print(f"🎉 Успешно сгенерировано {len(generated_wallets)} кошельков")
        return generated_wallets

    def save_wallets(self, wallets: List[WalletInfo]):
        """Сохранение кошельков в файлы"""
        print("💾 Сохранение кошельков...")

        # Подготавливаем данные для JSON
        wallets_data = []
        addresses_for_deposit = []

        for wallet in wallets:
            wallets_data.append({
                "index": wallet.index,
                "address": wallet.address,
                "private_key": wallet.private_key,
                "seed_phrase": wallet.seed_phrase,
                "balance_sol": wallet.balance_sol,
                "reserved_gas": wallet.reserved_gas
            })

            addresses_for_deposit.append(f"{wallet.index}. {wallet.address}")

        # Сохраняем полную информацию (ОСТОРОЖНО - содержит приватные ключи!)
        try:
            with open(self.wallets_file, 'w', encoding='utf-8') as f:
                json.dump(wallets_data, f, indent=2, ensure_ascii=False)

            # Устанавливаем ограниченные права доступа
            os.chmod(self.wallets_file, 0o600)  # Только владелец может читать/писать
            print(f"✅ Кошельки сохранены: {self.wallets_file}")

        except Exception as e:
            print(f"❌ Ошибка сохранения кошельков: {e}")

        # Сохраняем только адреса для пополнения
        try:
            with open(self.addresses_file, 'w', encoding='utf-8') as f:
                f.write("# Адреса для пополнения с CEX бирж\n")
                f.write("# Рекомендуется пополнять разными суммами для маскировки\n\n")
                for addr in addresses_for_deposit:
                    f.write(f"{addr}\n")

            print(f"✅ Адреса для пополнения сохранены: {self.addresses_file}")

        except Exception as e:
            print(f"❌ Ошибка сохранения адресов: {e}")

    def load_wallets(self) -> List[WalletInfo]:
        """Загрузка сохраненных кошельков"""
        if not self.wallets_file.exists():
            print("⚠️ Файл кошельков не найден")
            return []

        try:
            with open(self.wallets_file, 'r', encoding='utf-8') as f:
                wallets_data = json.load(f)

            wallets = []
            for data in wallets_data:
                wallet = WalletInfo(
                    index=data["index"],
                    address=data["address"],
                    private_key=data["private_key"],
                    seed_phrase=data["seed_phrase"],
                    balance_sol=data.get("balance_sol", 0.0),
                    reserved_gas=data.get("reserved_gas", 0.02)
                )
                wallet.update_balance(wallet.balance_sol)
                wallets.append(wallet)

            self.wallets = wallets
            print(f"✅ Загружено {len(wallets)} кошельков")
            return wallets

        except Exception as e:
            print(f"❌ Ошибка загрузки кошельков: {e}")
            return []

    def generate_wallet_config(self, wallets: List[WalletInfo]) -> str:
        """
        Генерация конфигурации для использования в основном боте

        Returns:
            str: Строка для добавления в .env файл
        """
        if not wallets:
            return ""

        # Создаем строки приватных ключей
        private_keys = [wallet.private_key for wallet in wallets]
        addresses = [wallet.address for wallet in wallets]

        config_lines = [
            "# ================================",
            "# МНОЖЕСТВЕННЫЕ КОШЕЛЬКИ ДЛЯ СНАЙПИНГА",
            "# ================================",
            "",
            "# Включить систему множественных кошельков",
            "USE_MULTI_WALLET=true",
            "",
            "# Приватные ключи кошельков (через запятую)",
            f"MULTI_WALLET_PRIVATE_KEYS={','.join(private_keys)}",
            "",
            "# Адреса кошельков (для справки)",
            f"MULTI_WALLET_ADDRESSES={','.join(addresses)}",
            "",
            "# Резерв газа на каждом кошельке (SOL)",
            "WALLET_GAS_RESERVE=0.02",
            "",
            "# Минимальный баланс для использования кошелька",
            "MIN_WALLET_BALANCE=0.05",
            ""
        ]

        return "\n".join(config_lines)

    def create_deposit_instructions(self, wallets: List[WalletInfo], total_budget: float = 20.0):
        """Создание инструкций для пополнения кошельков"""
        if not wallets:
            return

        instructions_file = self.wallets_dir / "deposit_instructions.md"

        # Рассчитываем рекомендуемые суммы (с рандомизацией)
        import random

        # Базовая сумма на кошелек
        base_amount = total_budget / len(wallets)

        # Создаем варированные суммы (80%-120% от базовой)
        amounts = []
        total_allocated = 0

        for i, wallet in enumerate(wallets[:-1]):  # Все кроме последнего
            # Случайная вариация от базовой суммы
            variation = random.uniform(0.8, 1.2)
            amount = round(base_amount * variation, 3)
            amounts.append(amount)
            total_allocated += amount

        # Последний кошелек получает остаток
        last_amount = round(total_budget - total_allocated, 3)
        amounts.append(last_amount)

        # Создаем инструкции
        instructions = [
            "# 💰 Инструкции по пополнению кошельков",
            "",
            f"**Общий бюджет:** {total_budget} SOL (~${total_budget * 150:.0f})",
            f"**Количество кошельков:** {len(wallets)}",
            "",
            "## 🏦 Рекомендации по пополнению:",
            "",
            "1. **Используйте разные CEX биржи** для разных кошельков",
            "2. **Пополняйте в разное время** (интервалы 10-30 минут)",
            "3. **Суммы варьируются** для имитации естественного поведения",
            "4. **Не круглые числа** выглядят более естественно",
            "",
            "## 📋 Адреса и рекомендуемые суммы:",
            "",
        ]

        for i, (wallet, amount) in enumerate(zip(wallets, amounts)):
            instructions.extend([
                f"### Кошелек {i + 1}:",
                f"- **Адрес:** `{wallet.address}`",
                f"- **Рекомендуемая сумма:** {amount} SOL",
                f"- **Доступно для торговли:** ~{amount - 0.02:.3f} SOL (с учетом газа)",
                ""
            ])

        instructions.extend([
            "## ⚡ После пополнения:",
            "",
            "1. Запустите проверку балансов: `python check_wallets.py`",
            "2. Обновите конфигурацию бота",
            "3. Протестируйте систему: `python test_multi_wallet.py`",
            "",
            "## ⚠️ Безопасность:",
            "",
            "- Файл `generated_wallets.json` содержит приватные ключи!",
            "- Не передавайте его третьим лицам",
            "- Сделайте резервную копию в безопасном месте",
        ])

        # Сохраняем инструкции
        try:
            with open(instructions_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(instructions))

            print(f"✅ Инструкции сохранены: {instructions_file}")

        except Exception as e:
            print(f"❌ Ошибка создания инструкций: {e}")

    def print_summary(self, wallets: List[WalletInfo]):
        """Печать сводки созданных кошельков"""
        print("\n" + "=" * 60)
        print("📊 СВОДКА СОЗДАННЫХ КОШЕЛЬКОВ")
        print("=" * 60)
        print(f"Количество кошельков: {len(wallets)}")
        print(f"Файл с кошельками: {self.wallets_file}")
        print(f"Адреса для пополнения: {self.addresses_file}")
        print()

        print("🔐 ПЕРВЫЕ 3 КОШЕЛЬКА (для проверки):")
        for wallet in wallets[:3]:
            print(f"  {wallet.index}. {wallet.address}")

        if len(wallets) > 3:
            print(f"  ... и еще {len(wallets) - 3} кошельков")

        print()
        print("⚠️  ВАЖНО:")
        print("1. Сделайте резервную копию файла generated_wallets.json")
        print("2. Пополните кошельки с разных CEX бирж")
        print("3. Используйте разные суммы для каждого кошелька")
        print("4. Не пополняйте все кошельки одновременно")


def main():
    """Основная функция для генерации кошельков"""
    print("💰 Генератор множественных кошельков для MORI Sniper")
    print("=" * 60)

    try:
        # Запрашиваем количество кошельков
        while True:
            try:
                count = int(input("Сколько кошельков создать? (рекомендуется 5-10): "))
                if 1 <= count <= 50:
                    break
                else:
                    print("❌ Введите число от 1 до 50")
            except ValueError:
                print("❌ Введите корректное число")

        # Запрашиваем общий бюджет
        while True:
            try:
                budget = float(input("Общий бюджет в SOL? (например, 20): "))
                if budget > 0:
                    break
                else:
                    print("❌ Бюджет должен быть больше 0")
            except ValueError:
                print("❌ Введите корректное число")

        # Создаем генератор
        generator = MultiWalletGenerator()

        # Генерируем кошельки
        wallets = generator.generate_wallets(count)

        if wallets:
            # Сохраняем
            generator.save_wallets(wallets)

            # Создаем инструкции по пополнению
            generator.create_deposit_instructions(wallets, budget)

            # Генерируем конфигурацию
            config = generator.generate_wallet_config(wallets)
            config_file = generator.wallets_dir / "multi_wallet_config.env"
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config)
            print(f"✅ Конфигурация сохранена: {config_file}")

            # Печатаем сводку
            generator.print_summary(wallets)

        else:
            print("❌ Не удалось создать кошельки")

    except KeyboardInterrupt:
        print("\n❌ Операция прервана пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()