import os
import re
from typing import List
from dataclasses import dataclass
from loguru import logger


@dataclass
class AIConfig:
    """Настройки AI анализа и обработки текста"""
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    model: str = 'gpt-4o-mini'  # Более быстрая модель
    max_tokens: int = 100  # Уменьшено для скорости
    temperature: float = 0.1

    # Оптимизация скорости
    use_fast_analysis: bool = True  # Использовать regex в первую очередь
    use_ai_confirmation: bool = False  # AI анализ отключен по умолчанию
    ai_timeout: float = 3.0  # Максимальное время для AI анализа
    cache_ai_results: bool = True

    # Компилированные regex паттерны для скорости
    _solana_address_patterns = None
    urgent_keywords: List[str] = None

    def __post_init__(self):
        # Автоматически включаем AI если есть ключ
        if self.openai_api_key and not self.use_ai_confirmation:
            self.use_ai_confirmation = True
            logger.info("✅ AI анализ включен автоматически (найден OpenAI ключ)")

        if self._solana_address_patterns is None:
            self._init_solana_patterns()

        if self.urgent_keywords is None:
            self.urgent_keywords = [
                '$mori', 'contract', 'launch', 'live', 'now', 'urgent',
                'ca:', 'mint:', 'address:', 'buy now', 'launching',
                'контракт', 'запуск', 'токен', 'адрес', 'покупай'
            ]

    def _init_solana_patterns(self):
        """Инициализация компилированных regex паттернов для Solana адресов"""
        self._solana_address_patterns = [
            # Основной паттерн Solana адресов (32-44 символа, строго base58)
            re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'),

            # Паттерны с ключевыми словами (более строгие границы)
            re.compile(r'\bcontract[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bmint[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\baddress[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bca[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bтокен[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),
            re.compile(r'\bконтракт[:\s=]+([1-9A-HJ-NP-Za-km-z]{32,44})\b', re.IGNORECASE),

            # Jupiter паттерны (улучшенные с границами слов)
            re.compile(r'\bjup\.ag/swap/[^-\s]*-([1-9A-HJ-NP-Za-km-z]{32,44})[\s?&#]', re.IGNORECASE),
            re.compile(r'\bjup\.ag[^\s]*?([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),

            # Другие DEX паттерны
            re.compile(r'\braydium\.io[^\s]*?([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
            re.compile(r'\bdexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),
            re.compile(r'\bbirdeye\.so/token/([1-9A-HJ-NP-Za-km-z]{32,44})', re.IGNORECASE),

            # URL параметры с границами
            re.compile(r'[?&]token=([1-9A-HJ-NP-Za-km-z]{32,44})(?:[&#]|$)', re.IGNORECASE),
            re.compile(r'[?&]mint=([1-9A-HJ-NP-Za-km-z]{32,44})(?:[&#]|$)', re.IGNORECASE),
            re.compile(r'[?&]address=([1-9A-HJ-NP-Za-km-z]{32,44})(?:[&#]|$)', re.IGNORECASE),

            # Специальный паттерн для точного извлечения из Jupiter ссылок
            re.compile(
                r'So11111111111111111111111111111111111111112-([1-9A-HJ-NP-Za-km-z]{32,44})(?:[^A-HJ-NP-Za-km-z1-9]|$)',
                re.IGNORECASE),

            # Паттерн для адресов в кавычках или скобках
            re.compile(r'["\'`\(\[]([1-9A-HJ-NP-Za-km-z]{32,44})["\'`\)\]]'),
        ]

    @property
    def solana_address_patterns(self):
        """Получить компилированные regex паттерны для Solana адресов"""
        if self._solana_address_patterns is None:
            self._init_solana_patterns()
        return self._solana_address_patterns

    def has_urgent_keywords(self, text: str) -> bool:
        """Быстрое обнаружение ключевых слов"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.urgent_keywords)

    def add_urgent_keyword(self, keyword: str):
        """Добавление нового ключевого слова"""
        if keyword not in self.urgent_keywords:
            self.urgent_keywords.append(keyword)

    def remove_urgent_keyword(self, keyword: str):
        """Удаление ключевого слова"""
        if keyword in self.urgent_keywords:
            self.urgent_keywords.remove(keyword)