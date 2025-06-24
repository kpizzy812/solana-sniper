import os
import random
from typing import List, Optional
from dataclasses import dataclass
from loguru import logger

# Проверяем доступность библиотек
try:
    from solders.keypair import Keypair
    import base58

    CRYPTO_LIBS_AVAILABLE = True
except ImportError:
    CRYPTO_LIBS_AVAILABLE = False
    logger.warning("⚠️ Библиотеки для множественных кошельков недоступны")


@dataclass
class MultiWalletInfo:
    """Информация о кошельке для торговли"""
    index: int
    address: str
    keypair: Keypair
    balance_sol: float = 0.0
    reserved_gas: float = 0.02
    available_balance: float = 0.0
    last_used: float = 0.0  # Время последнего использования
    trades_count: int = 0  # Количество сделок

    def update_balance(self, new_balance: float):
        """Обновление баланса с учетом резерва на газ"""
        self.balance_sol = new_balance
        self.available_balance = max(0, new_balance - self.reserved_gas)

    def can_trade(self, amount: float) -> bool:
        """Проверка возможности совершить сделку на указанную сумму"""
        return self.available_balance >= amount

    def mark_used(self, amount: float):
        """Отметка об использовании кошелька"""
        import time
        self.last_used = time.time()
        self.trades_count += 1
        self.available_balance -= amount


@dataclass
class MultiWalletConfig:
    """Конфигурация системы множественных кошельков"""

    # Основные настройки
    use_multi_wallet: bool = os.getenv('USE_MULTI_WALLET', 'false').lower() in ['true', '1', 'yes']

    # НОВАЯ НАСТРОЙКА для трат всего баланса
    use_max_available_balance: bool = os.getenv('USE_MAX_AVAILABLE_BALANCE', 'false').lower() in ['true', '1', 'yes']

    private_keys_str: str = os.getenv('MULTI_WALLET_PRIVATE_KEYS', '')
    gas_reserve: float = float(os.getenv('WALLET_GAS_RESERVE', '0.02'))
    min_balance: float = float(os.getenv('MIN_WALLET_BALANCE', '0.05'))

    # Стратегии распределения
    distribution_strategy: str = os.getenv('WALLET_DISTRIBUTION_STRATEGY', 'balanced')  # balanced, random, sequential
    max_trades_per_wallet: int = int(os.getenv('MAX_TRADES_PER_WALLET', '3'))

    # Рандомизация для маскировки
    randomize_amounts: bool = os.getenv('RANDOMIZE_TRADE_AMOUNTS', 'true').lower() in ['true', '1', 'yes']
    amount_variation_percent: float = float(os.getenv('AMOUNT_VARIATION_PERCENT', '15'))  # ±15%

    # Задержка между покупками
    initial_delay_seconds: float = float(os.getenv('INITIAL_TRADING_DELAY', '15'))  # 15 сек задержка
    inter_trade_delay: tuple = (0.25, 0.6)  # Задержка между сделками разных кошельков

    # Загруженные кошельки
    wallets: List[MultiWalletInfo] = None

    def __post_init__(self):
        """Инициализация кошельков при создании конфигурации"""
        if self.use_multi_wallet and self.private_keys_str:
            self.wallets = self._load_wallets()
        else:
            self.wallets = []

    def _load_wallets(self) -> List[MultiWalletInfo]:
        """Загрузка кошельков из приватных ключей"""
        if not CRYPTO_LIBS_AVAILABLE:
            logger.error("❌ Библиотеки для множественных кошельков не установлены")
            return []

        wallets = []
        private_keys = [key.strip() for key in self.private_keys_str.split(',') if key.strip()]

        logger.info(f"🔄 Загрузка {len(private_keys)} кошельков...")

        for i, private_key in enumerate(private_keys):
            try:
                # Декодируем приватный ключ
                private_key_bytes = base58.b58decode(private_key)
                keypair = Keypair.from_bytes(private_key_bytes)

                wallet = MultiWalletInfo(
                    index=i + 1,
                    address=str(keypair.pubkey()),
                    keypair=keypair,
                    reserved_gas=self.gas_reserve
                )

                wallets.append(wallet)
                logger.debug(f"✅ Кошелек {i + 1}: {wallet.address}")

            except Exception as e:
                logger.error(f"❌ Ошибка загрузки кошелька {i + 1}: {e}")
                continue

        logger.success(f"✅ Загружено {len(wallets)} кошельков для торговли")
        return wallets

    def is_enabled(self) -> bool:
        """Проверка, включена ли система множественных кошельков"""
        return self.use_multi_wallet and len(self.wallets) > 0

    def get_available_wallets(self, min_amount: float = 0) -> List[MultiWalletInfo]:
        """Получение доступных кошельков с достаточным балансом"""
        if not self.wallets:
            return []

        available = []
        for wallet in self.wallets:
            if (wallet.balance_sol >= self.min_balance and
                    wallet.can_trade(min_amount) and
                    wallet.trades_count < self.max_trades_per_wallet):
                available.append(wallet)

        return available

    def get_total_available_balance(self) -> float:
        """Получение общего доступного баланса всех кошельков"""
        if not self.wallets:
            return 0.0

        return sum(wallet.available_balance for wallet in self.wallets)

    def select_wallet_for_trade(self, amount: float) -> Optional[MultiWalletInfo]:
        """
        Выбор кошелька для сделки на основе стратегии распределения

        Args:
            amount: Сумма сделки в SOL

        Returns:
            MultiWalletInfo: Выбранный кошелек или None
        """
        available_wallets = self.get_available_wallets(amount)

        if not available_wallets:
            logger.warning(f"⚠️ Нет доступных кошельков для сделки на {amount} SOL")
            return None

        if self.distribution_strategy == 'random':
            return random.choice(available_wallets)

        elif self.distribution_strategy == 'sequential':
            # Выбираем кошелек с наименьшим количеством сделок
            return min(available_wallets, key=lambda w: w.trades_count)

        elif self.distribution_strategy == 'balanced':
            # Выбираем кошелек с наибольшим доступным балансом
            return max(available_wallets, key=lambda w: w.available_balance)

        else:
            # По умолчанию случайный выбор
            return random.choice(available_wallets)

    def get_max_trade_amount_for_wallet(self, wallet: MultiWalletInfo) -> float:
        """
        Получить максимальную сумму для торговли с кошелька

        Returns:
            float: Сумма доступная для торговли (баланс - резерв на газ)
        """
        if not self.use_max_available_balance:
            # Используем стандартную логику
            try:
                from config.settings import settings
                return settings.trading.trade_amount_sol
            except ImportError:
                # Fallback если settings недоступны
                return 0.1

        # Тратим весь доступный баланс
        max_amount = wallet.available_balance

        # Дополнительная защита
        try:
            from config.settings import settings
            max_allowed = settings.trading.max_trade_amount_sol
        except ImportError:
            # Fallback защита
            max_allowed = 1.0

        return min(max_amount, max_allowed)

    def select_wallet_for_max_trade(self) -> Optional[MultiWalletInfo]:
        """
        Выбрать кошелек с максимальным доступным балансом
        """
        available_wallets = self.get_available_wallets()

        if not available_wallets:
            return None

        # Возвращаем кошелек с максимальным доступным балансом
        return max(available_wallets, key=lambda w: w.available_balance)

    def randomize_trade_amount(self, base_amount: float) -> float:
        """
        Рандомизация суммы сделки для маскировки

        Args:
            base_amount: Базовая сумма сделки

        Returns:
            float: Рандомизированная сумма
        """
        if not self.randomize_amounts:
            return base_amount

        # Применяем случайную вариацию ±15% (или другой процент)
        variation = random.uniform(
            -self.amount_variation_percent / 100,
            self.amount_variation_percent / 100
        )

        randomized_amount = base_amount * (1 + variation)

        # Округляем до 4 знаков для естественности
        randomized_amount = round(randomized_amount, 4)

        logger.debug(f"💫 Рандомизация: {base_amount} SOL → {randomized_amount} SOL ({variation * 100:+.1f}%)")
        return randomized_amount

    def get_inter_trade_delay(self) -> float:
        """Получение случайной задержки между сделками"""
        return random.uniform(*self.inter_trade_delay)

    def get_stats(self) -> dict:
        """Статистика множественных кошельков"""
        if not self.wallets:
            return {"multi_wallet_enabled": False}

        total_balance = sum(w.balance_sol for w in self.wallets)
        total_available = sum(w.available_balance for w in self.wallets)
        total_trades = sum(w.trades_count for w in self.wallets)

        available_wallets = len(self.get_available_wallets())

        return {
            "multi_wallet_enabled": True,
            "use_max_available_balance": self.use_max_available_balance,
            "total_wallets": len(self.wallets),
            "available_wallets": available_wallets,
            "total_balance_sol": total_balance,
            "total_available_sol": total_available,
            "total_trades_executed": total_trades,
            "distribution_strategy": self.distribution_strategy,
            "randomization_enabled": self.randomize_amounts,
            "initial_delay_seconds": self.initial_delay_seconds,
            "wallets_summary": [
                {
                    "index": w.index,
                    "address": w.address[:8] + "..." + w.address[-8:],  # Сокращенный адрес
                    "balance": w.balance_sol,
                    "available": w.available_balance,
                    "trades": w.trades_count
                } for w in self.wallets
            ]
        }

    def reset_trades_count(self):
        """Сброс счетчика сделок (для тестирования или сброса лимитов)"""
        if self.wallets:
            for wallet in self.wallets:
                wallet.trades_count = 0
            logger.info("📊 Счетчик сделок сброшен для всех кошельков")