import os
from dataclasses import dataclass
from loguru import logger

# Импорты для конвертации seed phrase
try:
    from mnemonic import Mnemonic
    from solders.keypair import Keypair
    import base58

    CRYPTO_LIBS_AVAILABLE = True
except ImportError:
    CRYPTO_LIBS_AVAILABLE = False
    logger.warning("⚠️ Библиотеки для seed phrase не установлены. Используйте: pip install mnemonic")


def convert_seed_to_private_key(seed_phrase: str) -> str:
    """Конвертирует seed phrase в base58 приватный ключ"""
    if not CRYPTO_LIBS_AVAILABLE:
        raise ImportError("Установите: pip install mnemonic solders")

    try:
        mnemo = Mnemonic("english")
        clean_phrase = seed_phrase.strip()

        if not mnemo.check(clean_phrase):
            raise ValueError("Неверная seed phrase")

        seed = mnemo.to_seed(clean_phrase)
        keypair = Keypair.from_seed(seed[:32])
        private_key = base58.b58encode(bytes(keypair)).decode('utf-8')

        logger.info(f"✅ Приватный ключ сгенерирован из seed phrase")
        logger.info(f"🏦 Адрес кошелька: {keypair.pubkey()}")

        return private_key
    except Exception as e:
        raise ValueError(f"Ошибка конвертации seed phrase: {e}")


@dataclass
class SolanaConfig:
    """Настройки Solana блокчейна и кошелька"""
    rpc_url: str = os.getenv('SOLANA_RPC_URL', 'https://api.devnet.solana.com')
    network: str = 'mainnet'  # devnet для тестов, mainnet-beta для продакшена
    private_key: str = ''
    commitment: str = 'confirmed'

    def __post_init__(self):
        """Автоматическая конвертация seed phrase в private key"""
        # Сначала пробуем получить готовый приватный ключ
        direct_key = os.getenv('SOLANA_PRIVATE_KEY', '')

        if direct_key:
            self.private_key = direct_key
            logger.debug("🔑 Используется готовый приватный ключ")
        else:
            # Если нет готового ключа, конвертируем из seed phrase
            seed_phrase = os.getenv('SOLANA_SEED_PHRASE', '')

            if seed_phrase:
                try:
                    self.private_key = convert_seed_to_private_key(seed_phrase)
                    logger.success("🔄 Seed phrase сконвертирована в приватный ключ")
                except Exception as e:
                    logger.error(f"❌ Ошибка конвертации seed phrase: {e}")
                    raise
            else:
                logger.error("❌ Не найден ни SOLANA_PRIVATE_KEY, ни SOLANA_SEED_PHRASE")

        # Определяем сеть из RPC URL
        if 'mainnet' in self.rpc_url:
            self.network = 'mainnet-beta'
        elif 'devnet' in self.rpc_url:
            self.network = 'devnet'

    @property
    def is_production(self) -> bool:
        """Проверка, что работаем в mainnet"""
        return self.network == 'mainnet-beta'