import re
from typing import List
from loguru import logger


def is_valid_solana_address(address: str) -> bool:
    """Строгая валидация формата Solana адреса с base58 декодированием"""
    if not address or not isinstance(address, str):
        return False

    # Проверка длины (32-44 символа для base58)
    if len(address) < 32 or len(address) > 44:
        return False

    # Набор символов Base58 (исключает 0, O, I, l для избежания путаницы)
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_chars for c in address):
        return False

    # Исключаем очевидные ложные срабатывания
    if address == '1' * len(address):  # Все единицы
        return False
    if len(set(address)) < 8:  # Слишком мало уникальных символов
        return False

    # КРИТИЧНАЯ ПРОВЕРКА: Реальное base58 декодирование
    try:
        import base58
        decoded = base58.b58decode(address)
        # Solana адреса должны быть ровно 32 байта
        if len(decoded) != 32:
            return False
        return True
    except Exception:
        return False


def is_wrapped_sol(address: str) -> bool:
    """Проверка является ли адрес Wrapped SOL"""
    return address == 'So11111111111111111111111111111111111111112'


def filter_trading_targets(addresses: List[str]) -> List[str]:
    """Фильтрация адресов для торговли (исключаем SOL и известные базовые токены)"""
    filtered = []

    # Известные базовые токены которые НЕ покупаем
    base_tokens = {
        'So11111111111111111111111111111111111111112',  # Wrapped SOL
        'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
        'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
        '11111111111111111111111111111112',  # System Program
    }

    for addr in addresses:
        if addr not in base_tokens:
            logger.info(f"✅ Целевой токен для торговли: {addr}")
            filtered.append(addr)
        else:
            logger.debug(f"⏭️ Пропускаем базовый токен: {addr}")

    return filtered


def extract_jupiter_swap_addresses(text: str) -> List[str]:
    """Улучшенный парсер для Jupiter swap ссылок с строгой валидацией"""
    addresses = []

    # Проверяем наличие различных DEX ссылок
    dex_indicators = ['jup.ag', 'jupiter', 'raydium', 'dexscreener', 'birdeye', 'pump.fun']
    if not any(indicator in text.lower() for indicator in dex_indicators):
        return addresses

    logger.debug(f"🔍 Обнаружены DEX ссылки в тексте: {text}")

    # Расширенные паттерны для различных DEX
    jupiter_patterns = [
        # Основные Jupiter паттерны
        r'jup\.ag/swap/([A-HJ-NP-Za-km-z1-9]{32,44})-([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'jup\.ag/swap\?.*?(?:inputMint|outputMint)=([A-HJ-NP-Za-km-z1-9]{32,44})',

        # Новые паттерны для кнопок/redirect ссылок
        r'jupiter[^?\s]*?([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'[?&]token=([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'[?&]mint=([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'[?&]address=([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'[?&]ca=([A-HJ-NP-Za-km-z1-9]{32,44})',

        # Другие DEX
        r'raydium\.io[^\s]*?([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'dexscreener\.com/solana/([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'birdeye\.so/token/([A-HJ-NP-Za-km-z1-9]{32,44})',
        r'pump\.fun[^\s]*?([A-HJ-NP-Za-km-z1-9]{32,44})',
    ]

    for pattern in jupiter_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Извлекаем все группы из матча
            for group in match.groups():
                if group and is_valid_solana_address(group):
                    # Дополнительная фильтрация: пропускаем Wrapped SOL
                    if not is_wrapped_sol(group):
                        logger.info(f"✅ Jupiter токен найден: {group}")
                        addresses.append(group)
                    else:
                        logger.debug(f"⏭️ Пропускаем Wrapped SOL: {group}")

    # Если основные паттерны не сработали, пробуем ручной парсинг
    if not addresses:
        addresses.extend(manual_jupiter_parsing(text))

    return addresses


def extract_addresses_from_any_url(url: str) -> List[str]:
    """Извлечение адресов из любых URL (включая redirect ссылки)"""
    addresses = []

    try:
        # Сначала ищем прямые адреса в URL
        direct_addresses = extract_jupiter_swap_addresses(url)
        addresses.extend(direct_addresses)

        # Ищем адреса в параметрах URL
        import re
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)

        # Проверяем query параметры
        if parsed.query:
            params = parse_qs(parsed.query)
            for key, values in params.items():
                if key.lower() in ['token', 'mint', 'address', 'ca', 'contract']:
                    for value in values:
                        if is_valid_solana_address(value):
                            addresses.append(value)
                            logger.info(f"✅ Адрес из параметра {key}: {value}")

        # Проверяем путь URL
        path_parts = parsed.path.split('/')
        for part in path_parts:
            if is_valid_solana_address(part):
                addresses.append(part)
                logger.info(f"✅ Адрес из пути URL: {part}")

    except Exception as e:
        logger.debug(f"Ошибка парсинга URL {url}: {e}")

    return list(set(addresses))  # Убираем дубликаты

def manual_jupiter_parsing(text: str) -> List[str]:
    """Ручной парсинг Jupiter ссылок для сложных случаев"""
    addresses = []

    try:
        # Ищем части URL после jup.ag/swap/
        parts = text.lower().split('jup.ag/swap/')
        if len(parts) < 2:
            return addresses

        # Берем часть после jup.ag/swap/
        url_part = parts[1].split()[0].split('?')[0].split('#')[0]
        logger.debug(f"🔍 Извлеченная часть URL: {url_part}")

        # Разделяем по дефису для формата TOKEN1-TOKEN2
        if '-' in url_part:
            tokens = url_part.split('-')
            for token in tokens:
                # Очищаем от лишних символов
                clean_token = ''.join(
                    c for c in token if c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')

                logger.debug(f"🧹 Проверяем очищенный токен: {clean_token}")

                if is_valid_solana_address(clean_token):
                    if not is_wrapped_sol(clean_token):
                        logger.info(f"✅ Найден валидный токен: {clean_token}")
                        addresses.append(clean_token)
                    else:
                        logger.debug(f"⏭️ Пропускаем Wrapped SOL: {clean_token}")
                else:
                    logger.debug(f"❌ Невалидный токен: {clean_token}")

        # Дополнительный поиск отдельных токенов в URL
        all_potential_tokens = re.findall(r'[A-HJ-NP-Za-km-z1-9]{32,44}', url_part)
        for token in all_potential_tokens:
            if is_valid_solana_address(token) and not is_wrapped_sol(token):
                if token not in addresses:
                    logger.info(f"✅ Дополнительный токен найден: {token}")
                    addresses.append(token)

    except Exception as e:
        logger.error(f"❌ Ошибка ручного парсинга Jupiter: {e}")

    return addresses


def extract_addresses_fast(text: str, ai_config) -> List[str]:
    """Ультра-быстрое извлечение адресов с улучшенной валидацией"""
    addresses = set()

    # ОТЛАДКА: Логируем входной текст
    logger.debug(f"🔍 Анализируем текст: {text[:200]}...")

    # НОВАЯ ЛОГИКА: Обработка URL из инлайн кнопок и гиперссылок
    import re
    urls_in_text = re.findall(r'https?://[^\s]+', text)
    if urls_in_text:
        logger.info(f"🔗 Найдены URL в тексте: {len(urls_in_text)} ссылок")
        for url in urls_in_text:
            url_addresses = extract_addresses_from_any_url(url)
            if url_addresses:
                logger.critical(f"🎯 АДРЕСА ИЗ URL: {url_addresses}")
                addresses.update(url_addresses)

    # СПЕЦИАЛЬНАЯ ОБРАБОТКА JUPITER ССЫЛОК (ПРИОРИТЕТ!)
    jupiter_addresses = extract_jupiter_swap_addresses(text)
    if jupiter_addresses:
        logger.critical(f"🎯 JUPITER SWAP НАЙДЕН: {jupiter_addresses}")
        addresses.update(jupiter_addresses)

    # Получаем паттерны
    try:
        patterns = ai_config.solana_address_patterns
        if not patterns:
            logger.warning("⚠️ Паттерны адресов не инициализированы")
            return list(addresses)
    except AttributeError:
        logger.error("❌ Ошибка доступа к паттернам адресов")
        return list(addresses)

    for i, pattern in enumerate(patterns):
        try:
            matches = pattern.findall(text)
            if matches:
                logger.debug(f"✅ Паттерн {i} нашел совпадения: {matches}")

            for match in matches:
                # Обрабатываем результаты tuple из групп
                addr = match if isinstance(match, str) else match[0] if match else ''

                if addr:
                    logger.debug(f"🔍 Проверяем адрес из паттерна {i}: {addr}")

                    # СТРОГАЯ ВАЛИДАЦИЯ
                    if is_valid_solana_address(addr):
                        # ФИЛЬТРУЕМ WRAPPED SOL
                        if is_wrapped_sol(addr):
                            logger.debug(f"⏭️ Пропускаем Wrapped SOL: {addr}")
                            continue

                        logger.info(f"✅ ВАЛИДНЫЙ АДРЕС НАЙДЕН: {addr}")
                        addresses.add(addr)
                    else:
                        logger.debug(f"❌ Невалидный адрес: {addr}")
        except Exception as e:
            logger.error(f"❌ Ошибка в паттерне {i}: {e}")

    # Фильтруем адреса для торговли
    result = filter_trading_targets(list(addresses))
    logger.info(f"🎯 ИТОГО НАЙДЕНО ЦЕЛЕВЫХ ТОКЕНОВ: {len(result)} | {result}")
    return result


def extract_addresses_from_message_data(message_text: str, inline_urls: List[str] = None,
                                        hyperlink_urls: List[str] = None, ai_config=None) -> List[str]:
    """
    Комплексное извлечение адресов из всех источников сообщения

    Args:
        message_text: Основной текст сообщения
        inline_urls: URL из инлайн кнопок
        hyperlink_urls: URL из гиперссылок
        ai_config: Конфигурация AI
    """
    all_addresses = set()

    # Анализируем основной текст
    text_addresses = extract_addresses_fast(message_text, ai_config)
    all_addresses.update(text_addresses)

    # Анализируем URL из кнопок
    if inline_urls:
        logger.info(f"🔘 Анализируем {len(inline_urls)} URL из инлайн кнопок")
        for url in inline_urls:
            button_addresses = extract_addresses_from_any_url(url)
            if button_addresses:
                logger.critical(f"🎯 КОНТРАКТ ИЗ ИНЛАЙН КНОПКИ: {button_addresses}")
                all_addresses.update(button_addresses)

    # Анализируем URL из гиперссылок
    if hyperlink_urls:
        logger.info(f"🔗 Анализируем {len(hyperlink_urls)} гиперссылок")
        for url in hyperlink_urls:
            link_addresses = extract_addresses_from_any_url(url)
            if link_addresses:
                logger.critical(f"🎯 КОНТРАКТ ИЗ ГИПЕРССЫЛКИ: {link_addresses}")
                all_addresses.update(link_addresses)

    final_addresses = filter_trading_targets(list(all_addresses))

    if final_addresses:
        logger.critical(f"🚨 ИТОГО НАЙДЕНО КОНТРАКТОВ: {len(final_addresses)} | {final_addresses}")

    return final_addresses