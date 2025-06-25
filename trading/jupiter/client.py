"""
🌐 MORI Sniper Bot - Jupiter API Client
HTTP клиент для работы с Jupiter DEX API v1
"""

import time
import json
from typing import Optional, Dict
import aiohttp
from loguru import logger

from config.settings import settings
from .models import QuoteResponse, SwapRequest


class JupiterAPIClient:
    """HTTP клиент для Jupiter DEX API"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.quote_cache = {}  # Кэш котировок

    async def start(self):
        """Инициализация HTTP сессии"""
        timeout = aiohttp.ClientTimeout(total=settings.jupiter.timeout)
        connector = aiohttp.TCPConnector(
            limit=settings.jupiter.max_concurrent_requests,
            limit_per_host=settings.jupiter.max_concurrent_requests
        )
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )
        logger.info("🌐 Jupiter API клиент инициализирован")

    async def stop(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
        logger.info("🛑 Jupiter API клиент остановлен")

    async def get_quote(self, input_mint: str, output_mint: str, amount: int,
                        slippage_bps: int) -> Optional[QuoteResponse]:
        """Получение котировки от Jupiter API - ИСПРАВЛЕННАЯ ВЕРСИЯ для v1"""
        try:
            # Проверяем кэш для быстрого доступа
            cache_key = f"{input_mint}:{output_mint}:{amount}:{slippage_bps}"
            if cache_key in self.quote_cache:
                cached_time, quote = self.quote_cache[cache_key]
                if time.time() - cached_time < 2:  # Кэш на 2 секунды
                    return quote

            # ПРИОРИТЕТ: Используем lite-api (бесплатный)
            if settings.jupiter.api_key and not settings.jupiter.use_lite_api:
                base_url = settings.jupiter.api_url
                headers = {
                    'Content-Type': 'application/json',
                    'x-api-key': settings.jupiter.api_key
                }
            else:
                base_url = settings.jupiter.lite_api_url
                headers = {'Content-Type': 'application/json'}

            url = f"{base_url}/quote"

            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false',
                'platformFeeBps': '0',
                'maxAccounts': '64'
            }

            logger.debug(f"🔍 Quote запрос: {url} с параметрами: {params}")

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()

                    # ИСПРАВЛЕННАЯ ОБРАБОТКА: добавляем все обязательные поля
                    quote = QuoteResponse(
                        input_mint=data['inputMint'],
                        output_mint=data['outputMint'],
                        in_amount=data['inAmount'],
                        out_amount=data['outAmount'],
                        other_amount_threshold=data.get('otherAmountThreshold', data['outAmount']),  # КРИТИЧНОЕ ПОЛЕ!
                        swap_mode=data.get('swapMode', 'ExactIn'),
                        slippage_bps=slippage_bps,
                        platform_fee=data.get('platformFee'),
                        price_impact_pct=data.get('priceImpactPct', '0'),
                        route_plan=data.get('routePlan', [])
                    )

                    # Кэшируем результат
                    self.quote_cache[cache_key] = (time.time(), quote)

                    logger.debug(f"✅ Quote получена через {base_url}")
                    return quote

                elif response.status == 401:
                    logger.warning("⚠️ 401 Unauthorized - переключаемся на lite-api")
                    return await self._get_quote_fallback(input_mint, output_mint, amount, slippage_bps)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка Quote API {response.status}: {error_text}")
                    return await self._get_quote_fallback(input_mint, output_mint, amount, slippage_bps)

        except Exception as e:
            logger.error(f"❌ Ошибка получения котировки: {e}")
            return await self._get_quote_fallback(input_mint, output_mint, amount, slippage_bps)

    async def _get_quote_fallback(self, input_mint: str, output_mint: str, amount: int,
                                  slippage_bps: int) -> Optional[QuoteResponse]:
        """Fallback метод для получения котировки"""
        try:
            # Пробуем альтернативный endpoint
            alt_url = settings.jupiter.api_url if settings.jupiter.use_lite_api else settings.jupiter.lite_api_url
            url = f"{alt_url}/quote"

            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false',
                'platformFeeBps': '0',
                'maxAccounts': '64'
            }

            headers = {'Content-Type': 'application/json'}
            if settings.jupiter.api_key and alt_url == settings.jupiter.api_url:
                headers['x-api-key'] = settings.jupiter.api_key

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Fallback quote получена через {alt_url}")

                    return QuoteResponse(
                        input_mint=data['inputMint'],
                        output_mint=data['outputMint'],
                        in_amount=data['inAmount'],
                        out_amount=data['outAmount'],
                        other_amount_threshold=data.get('otherAmountThreshold', data['outAmount']),
                        swap_mode=data.get('swapMode', 'ExactIn'),
                        slippage_bps=slippage_bps,
                        platform_fee=data.get('platformFee'),
                        price_impact_pct=data.get('priceImpactPct', '0'),
                        route_plan=data.get('routePlan', [])
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Fallback Quote API тоже не работает: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка fallback котировки: {e}")
            return None

    async def get_swap_transaction(self, swap_request: SwapRequest) -> Optional[str]:
        """Получение транзакции обмена от Jupiter API - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if settings.jupiter.api_key and not settings.jupiter.use_lite_api:
                base_url = settings.jupiter.api_url
                headers = {
                    'Content-Type': 'application/json',
                    'x-api-key': settings.jupiter.api_key
                }
            else:
                base_url = settings.jupiter.lite_api_url
                headers = {'Content-Type': 'application/json'}

            url = f"{base_url}/swap"
            payload = swap_request.to_dict()

            logger.debug(f"🔍 Swap запрос: {url}")
            logger.debug(f"📝 Payload: {json.dumps(payload, indent=2)}")

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"✅ Swap transaction получена через {base_url}")
                    return data.get('swapTransaction')

                elif response.status == 401:
                    logger.warning("⚠️ 401 Unauthorized при создании swap - переключаемся на lite-api")
                    return await self._get_swap_transaction_fallback(swap_request)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка Swap API {response.status}: {error_text}")
                    return await self._get_swap_transaction_fallback(swap_request)

        except Exception as e:
            logger.error(f"❌ Ошибка получения транзакции обмена: {e}")
            return await self._get_swap_transaction_fallback(swap_request)

    async def _get_swap_transaction_fallback(self, swap_request: SwapRequest) -> Optional[str]:
        """Fallback метод для получения транзакции обмена"""
        try:
            # Пробуем альтернативный endpoint
            alt_url = settings.jupiter.api_url if settings.jupiter.use_lite_api else settings.jupiter.lite_api_url
            url = f"{alt_url}/swap"
            payload = swap_request.to_dict()

            headers = {'Content-Type': 'application/json'}
            if settings.jupiter.api_key and alt_url == settings.jupiter.api_url:
                headers['x-api-key'] = settings.jupiter.api_key

            logger.debug(f"🔄 Fallback Swap запрос: {url}")

            async with self.session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Fallback swap transaction получена через {alt_url}")
                    return data.get('swapTransaction')
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Fallback Swap API тоже не работает: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка fallback транзакции обмена: {e}")
            return None

    async def get_price_info(self, token_address: str) -> Optional[Dict]:
        """Получение информации о цене токена через Jupiter Price API v2"""
        try:
            # Используем lite-api для Price API (бесплатный)
            url = f"{settings.jupiter.price_api_url}"
            params = {
                'ids': token_address,
                'vsToken': 'So11111111111111111111111111111111111111112'  # vs SOL
            }

            headers = {'Content-Type': 'application/json'}

            logger.debug(f"🔍 Price API запрос: {url} с параметрами: {params}")

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    try:
                        data = await response.json()

                        # Проверяем что data не None и имеет нужную структуру
                        if not data or not isinstance(data, dict):
                            logger.warning(f"⚠️ Price API вернул пустой или некорректный ответ")
                            return None

                        # Обрабатываем ответ от Price API v2
                        if 'data' in data and data['data'] and token_address in data['data']:
                            token_data = data['data'][token_address]

                            if not token_data or not isinstance(token_data, dict):
                                logger.warning(f"⚠️ Данные токена пусты или некорректны")
                                return None

                            price = float(token_data.get('price', 0))
                            logger.info(f"💰 Цена {token_address}: {price} SOL")

                            return {
                                'price': price,
                                'token_address': token_address,
                                'vs_token': 'So11111111111111111111111111111111111111112',
                                'source': 'jupiter_price_api_v2'
                            }
                        else:
                            logger.warning(f"⚠️ Токен {token_address} не найден в Price API v2")
                            return None

                    except Exception as json_error:
                        logger.error(f"❌ Ошибка парсинга JSON от Price API: {json_error}")
                        return None

                elif response.status == 404:
                    logger.warning(f"⚠️ Токен {token_address} не найден (404)")
                    return None
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Price API v2 error {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о цене токена: {e}")
            return None

    async def health_check(self) -> Dict:
        """Проверка здоровья Jupiter API - ИСПРАВЛЕНО для платного API"""
        test_url = "unknown"
        endpoint_type = "unknown"
        status_code = None

        try:
            # ✅ ПРАВИЛЬНАЯ логика для платного API
            if settings.jupiter.api_key and not settings.jupiter.use_lite_api:
                # Платный API - используем api.jup.ag
                test_url = f"{settings.jupiter.api_url}/quote"
                headers = {
                    'Content-Type': 'application/json',
                    'x-api-key': settings.jupiter.api_key
                }
                endpoint_type = "платный (api.jup.ag)"
            else:
                # Бесплатный API - используем lite-api.jup.ag
                test_url = f"{settings.jupiter.lite_api_url}/quote"
                headers = {
                    'Content-Type': 'application/json'
                }
                endpoint_type = "бесплатный (lite-api.jup.ag)"

            # Параметры для тестового quote
            params = {
                'inputMint': 'So11111111111111111111111111111111111111112',  # SOL
                'outputMint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
                'amount': '1000000',  # 0.001 SOL
                'slippageBps': '50'  # 0.5% slippage
            }

            logger.debug(f"🔍 Health check {endpoint_type}: {test_url}")

            async with self.session.get(test_url, params=params, headers=headers) as resp:
                status_code = resp.status
                jupiter_healthy = resp.status == 200

                if resp.status == 200:
                    response_data = await resp.json()
                    # Проверяем что ответ содержит ожидаемые поля
                    if 'inAmount' in response_data and 'outAmount' in response_data:
                        logger.success(f"✅ Jupiter {endpoint_type} работает корректно")
                    else:
                        logger.warning(f"⚠️ Jupiter API ответил, но без ожидаемых данных")
                        jupiter_healthy = False
                elif resp.status == 401:
                    error_text = await resp.text()
                    logger.error(f"❌ 401 Unauthorized - проверьте API ключ: {error_text}")
                    jupiter_healthy = False
                elif resp.status == 429:
                    error_text = await resp.text()
                    logger.warning(f"⚠️ 429 Rate Limit: {error_text}")
                    jupiter_healthy = False
                elif resp.status >= 500:
                    error_text = await resp.text()
                    logger.warning(f"⚠️ {resp.status} Серверная ошибка Jupiter: {error_text}")
                    jupiter_healthy = False
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ Jupiter API ошибка {resp.status}: {error_text}")
                    jupiter_healthy = False

            return {
                "jupiter_api": "healthy" if jupiter_healthy else "error",
                "jupiter_endpoint": test_url,
                "endpoint_type": endpoint_type,
                "api_key_configured": bool(settings.jupiter.api_key),
                "use_lite_api": settings.jupiter.use_lite_api,
                "cache_size": len(self.quote_cache),
                "status_code": status_code
            }

        except Exception as e:
            logger.error(f"❌ Ошибка health check Jupiter API: {e}")
            return {
                "jupiter_api": "error",
                "message": str(e),
                "jupiter_endpoint": test_url,
                "endpoint_type": endpoint_type,
                "status_code": status_code
            }

    def clear_cache(self):
        """Очистка кэша котировок"""
        self.quote_cache.clear()
        logger.debug("🧹 Кэш котировок очищен")

    def get_cache_stats(self) -> Dict:
        """Статистика кэша"""
        return {
            "cache_size": len(self.quote_cache),
            "cache_keys": list(self.quote_cache.keys())[:10]  # Первые 10 ключей для отладки
        }