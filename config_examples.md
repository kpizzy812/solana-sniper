# 📋 Примеры конфигурации MORI Sniper Bot

## 🎯 Базовая конфигурация (рекомендуемая)

```env
# .env файл для начинающих
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_PRIVATE_KEY=your_base58_private_key_here

# Консервативная торговля
TRADE_AMOUNT_SOL=0.05
NUM_PURCHASES=1
SLIPPAGE_BPS=1000
PRIORITY_FEE=50000

# Безопасность
MIN_LIQUIDITY=10
MAX_PRICE_IMPACT=10.0

# Telegram мониторинг
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_1=@YourChannel
TELEGRAM_ADMIN_1=YourAdminUsername

# Логирование
LOG_LEVEL=INFO
```

## ⚡ Агрессивная конфигурация

```env
# Для опытных трейдеров с хорошим RPC
SOLANA_RPC_URL=https://your-premium-rpc-url.com
SOLANA_PRIVATE_KEY=your_base58_private_key_here

# Агрессивная торговля
TRADE_AMOUNT_SOL=0.2
NUM_PURCHASES=5
SLIPPAGE_BPS=500
PRIORITY_FEE=500000

# Менее строгая безопасность для скорости
MIN_LIQUIDITY=3
MAX_PRICE_IMPACT=20.0

# Все мониторы
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
WEBSITE_URL_1=https://yourtoken.com

# Детальное логирование
LOG_LEVEL=DEBUG
```

## 🏭 Продакшн конфигурация

```env
# Mainnet с максимальной безопасностью
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_mainnet_private_key

# Умеренная торговля
TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=3
SLIPPAGE_BPS=750
PRIORITY_FEE=200000

# Строгая безопасность
MIN_LIQUIDITY=20
MAX_PRICE_IMPACT=8.0
MAX_BUY_TAX=5
MAX_SELL_TAX=5

# Полный мониторинг
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_1=@OfficialChannel
TELEGRAM_GROUP_1=@OfficialGroup
TELEGRAM_ADMIN_1=OfficialAdmin

TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_USERNAME_1=OfficialTwitter

WEBSITE_URL_1=https://official-website.com

# AI анализ
OPENAI_API_KEY=your_openai_api_key

# Уведомления
TELEGRAM_ALERTS_CHAT_ID=your_alerts_chat_id

# Продакшн логирование
LOG_LEVEL=WARNING
```

## 💸 Крупные объемы

```env
# Для больших инвестиций
SOLANA_RPC_URL=https://premium-rpc-provider.com
SOLANA_PRIVATE_KEY=your_whale_private_key

# Большие объемы с умным распределением
TRADE_AMOUNT_SOL=1.0
NUM_PURCHASES=10
SLIPPAGE_BPS=300
PRIORITY_FEE=1000000

# Очень строгая безопасность
MIN_LIQUIDITY=100
MAX_PRICE_IMPACT=5.0
MAX_BUY_TAX=3
MAX_SELL_TAX=3
MIN_HOLDERS=50

# Максимальный мониторинг
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_1=@VIPChannel
TELEGRAM_GROUP_1=@VIPGroup
TELEGRAM_ADMIN_1=VIPAdmin

TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_USERNAME_1=VIPAccount

WEBSITE_URL_1=https://vip-signals.com

OPENAI_API_KEY=your_openai_api_key

LOG_LEVEL=INFO
```

## 🧪 Тестовая конфигурация

```env
# Для тестирования на devnet
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_PRIVATE_KEY=your_test_private_key

# Минимальные объемы для тестов
TRADE_AMOUNT_SOL=0.01
NUM_PURCHASES=1
SLIPPAGE_BPS=2000
PRIORITY_FEE=10000

# Мягкая безопасность для тестов
MIN_LIQUIDITY=1
MAX_PRICE_IMPACT=50.0

# Тестовый Telegram
TELEGRAM_BOT_TOKEN=your_test_bot_token
TELEGRAM_CHANNEL_1=@TestChannel

# Детальное логирование для отладки
LOG_LEVEL=DEBUG
```

## 📱 Только Telegram мониторинг

```env
# Минимальная настройка для Telegram
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_private_key

TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=2
SLIPPAGE_BPS=500

# Только Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_1=@MainChannel
TELEGRAM_CHANNEL_2=@BackupChannel
TELEGRAM_GROUP_1=@MainGroup
TELEGRAM_ADMIN_1=MainAdmin
TELEGRAM_ADMIN_2=BackupAdmin

LOG_LEVEL=INFO
```

## 🐦 Только Twitter мониторинг

```env
# Минимальная настройка для Twitter
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_private_key

TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=2
SLIPPAGE_BPS=500

# Только Twitter
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_USERNAME_1=MainAccount
TWITTER_USERNAME_2=BackupAccount

LOG_LEVEL=INFO
```

## 🌐 Только мониторинг сайтов

```env
# Минимальная настройка для сайтов
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_private_key

TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=1
SLIPPAGE_BPS=500

# Только сайты
WEBSITE_URL_1=https://main-site.com
WEBSITE_URL_2=https://backup-site.com

LOG_LEVEL=INFO
```

## 🔧 Продвинутые настройки

### Кастомные RPC провайдеры

```env
# QuickNode
SOLANA_RPC_URL=https://your-endpoint.solana-mainnet.quiknode.pro/your-key/

# Helius
SOLANA_RPC_URL=https://rpc.helius.xyz/?api-key=your-key

# Alchemy
SOLANA_RPC_URL=https://solana-mainnet.g.alchemy.com/v2/your-key
```

### Производительность

```env
# Максимальная скорость (осторожно с rate limits)
TELEGRAM_INTERVAL=0.5
TWITTER_INTERVAL=1.0
WEBSITE_INTERVAL=2.0

# Больше параллельных запросов
MAX_CONCURRENT_REQUESTS=50

# Высокий приоритет
PRIORITY_FEE=2000000
```

### Безопасность

```env
# Максимальная безопасность
MIN_LIQUIDITY=50
MAX_PRICE_IMPACT=3.0
MAX_BUY_TAX=1
MAX_SELL_TAX=1
MIN_HOLDERS=100

# Blacklist токенов (добавить в settings.py)
BLACKLISTED_TOKENS=token1,token2,token3
```

## ⚙️ Настройка по типам проектов

### Мем-коины
```env
# Быстрая торговля мем-коинами
SLIPPAGE_BPS=1500
PRIORITY_FEE=1000000
MIN_LIQUIDITY=2
MAX_PRICE_IMPACT=25.0
NUM_PURCHASES=5
```

### Серьезные проекты
```env
# Консервативная торговля
SLIPPAGE_BPS=300
PRIORITY_FEE=100000
MIN_LIQUIDITY=50
MAX_PRICE_IMPACT=5.0
NUM_PURCHASES=1
```

### Новые листинги
```env
# Агрессивная торговля новых листингов
SLIPPAGE_BPS=2000
PRIORITY_FEE=2000000
MIN_LIQUIDITY=1
MAX_PRICE_IMPACT=50.0
NUM_PURCHASES=10
```

## 🚨 Важные замечания

1. **Всегда тестируйте на devnet** перед использованием на mainnet
2. **Начинайте с малых сумм** для проверки настроек
3. **Мониторьте логи** для выявления проблем
4. **Регулярно проверяйте баланс** кошелька
5. **Обновляйте RPC endpoints** при проблемах

## 🔍 Отладка конфигурации

Используйте тестовый скрипт для проверки:
```bash
python test_sniper.py
```

Проверка отдельных компонентов:
```python
# В Python консоли
from config.settings import settings
print(settings.solana.rpc_url)
print(settings.trading.trade_amount_sol)
```