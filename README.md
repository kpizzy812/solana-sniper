# 🎯 MORI Token Sniper Bot

Ультра-быстрый снайперский бот для автоматической торговли токенами на Solana. Мониторит социальные сети в реальном времени и мгновенно покупает токены при обнаружении контрактов.

## 🔥 Ключевые особенности

- **⚡ Мгновенная торговля**: 50-200ms от обнаружения до покупки
- **🤖 Telegram User Bot**: Мониторинг в реальном времени без ограничений API
- **🧠 AI анализ**: Умное обнаружение контрактов с подтверждением от OpenAI
- **🎯 Множественные покупки**: До 10 параллельных сделок с умным распределением
- **🛡️ Безопасность**: Проверки ликвидности, налогов и honeypot защита
- **📊 Мульти-платформа**: Telegram, Twitter, Website мониторинг

## 🚀 Быстрый старт

### 1. Установка

```bash
git clone https://github.com/your-repo/mori-sniper-bot
cd mori-sniper-bot
pip install -r requirements.txt
```

### 2. Получение Telegram API

1. Идите на https://my.telegram.org/apps
2. Войдите с вашим номером телефона
3. Создайте новое приложение
4. Скопируйте `api_id` и `api_hash`

### 3. Настройка конфигурации

```bash
cp .env.example .env
nano .env
```

**Минимальная конфигурация:**
```env
# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_base58_private_key

# Торговля
TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=3

# Telegram User Bot (РЕКОМЕНДУЕТСЯ)
USE_TELEGRAM_USER_BOT=true
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890

USER_BOT_CHANNEL_1=@YourChannel
USER_BOT_ADMIN_1=YourAdminUsername
```

### 4. Тестирование

```bash
# Тест всех компонентов
python test_sniper.py

# Тест только Telegram User Bot
python test_telegram_user.py
```

### 5. Запуск

```bash
python main.py
```

## 📱 Настройка Telegram User Bot

### Преимущества User Bot vs Bot API

| Функция | User Bot | Bot API |
|---------|----------|---------|
| Скорость | ⚡ Мгновенно | 🐌 1-3 секунды |
| Лимиты | ✅ Без лимитов | ❌ 30 сообщений/сек |
| Приватные каналы | ✅ Доступ | ❌ Только публичные |
| Сообщения в группах | ✅ Все сообщения | ❌ Только упоминания |
| История | ✅ Полная история | ❌ Только новые |

### Получение API ключей

1. **Идите на https://my.telegram.org/apps**
2. **Войдите с номером телефона**
3. **Нажмите "Create application"**
4. **Заполните форму:**
   - App title: `MORI Sniper`
   - Short name: `mori_sniper`
   - Platform: `Desktop`
5. **Скопируйте API ID и API Hash**

### Первая авторизация

При первом запуске бот запросит:
1. **Код подтверждения** из SMS
2. **Пароль 2FA** (если включен)
3. **Подтверждение входа** с нового устройства

```bash
# Первый запуск для авторизации
python test_telegram_user.py
```

### Настройка мониторинга

```env
# Каналы (публичные)
USER_BOT_CHANNEL_1=@cryptosignals
USER_BOT_CHANNEL_2=@memecoinchannels

# Группы (ID или username)
USER_BOT_GROUP_1=@trading_group
USER_BOT_GROUP_2=-1001234567890

# Админы (только их сообщения в группах)
USER_BOT_ADMIN_1=admin_username
USER_BOT_ADMIN_2=signal_provider
```

## 💰 Настройка торговли

### Базовые параметры

```env
# Размер сделки
TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=3

# Проскальзывание
SLIPPAGE_BPS=500  # 5%

# Приоритет
PRIORITY_FEE=200000  # Высокий для скорости
```

### Стратегии покупки

#### Консервативная (новички)
```env
TRADE_AMOUNT_SOL=0.05
NUM_PURCHASES=1
SLIPPAGE_BPS=1000
MIN_LIQUIDITY=10
```

#### Агрессивная (опытные)
```env
TRADE_AMOUNT_SOL=0.2
NUM_PURCHASES=5
SLIPPAGE_BPS=500
MIN_LIQUIDITY=3
```

#### Whale (крупные инвесторы)
```env
TRADE_AMOUNT_SOL=1.0
NUM_PURCHASES=10
SLIPPAGE_BPS=300
MIN_LIQUIDITY=50
```

## 🛡️ Безопасность

### Проверки безопасности

```env
# Ликвидность
MIN_LIQUIDITY=5  # Минимум SOL в пуле

# Налоги
MAX_BUY_TAX=10   # Максимум 10% налог на покупку
MAX_SELL_TAX=10  # Максимум 10% налог на продажу

# Проскальзывание
MAX_PRICE_IMPACT=15.0  # Максимум 15% проскальзывание

# Распределение
MIN_HOLDERS=10  # Минимум держателей токена
```

### Защита кошелька

- ✅ Используйте отдельный кошелек для торговли
- ✅ Не храните все средства на торговом кошельке
- ✅ Регулярно выводите прибыль
- ✅ Используйте надежные RPC провайдеры

## 🧠 AI анализ

### Настройка OpenAI

```env
OPENAI_API_KEY=your_openai_api_key
```

### Режимы анализа

1. **Fast только** (рекомендуется): Мгновенный regex анализ
2. **Fast + AI**: Regex + подтверждение от GPT
3. **AI только**: Только GPT анализ (медленно)

```env
# В config/settings.py
use_fast_analysis=True
use_ai_confirmation=False  # Отключено для скорости
```

## 📊 Мониторинг

### Логи

```bash
# Живые логи
tail -f logs/sniper.log

# Только торговые сигналы
grep "КОНТРАКТ" logs/sniper.log

# Статистика
grep "ИТОГИ" logs/sniper.log
```

### Метрики

Бот отслеживает:
- Обработанные сообщения
- Найденные контракты
- Выполненные сделки
- Потраченные SOL
- Процент успеха

## 🔧 Продвинутая настройка

### Кастомные RPC

```env
# QuickNode
SOLANA_RPC_URL=https://your-endpoint.solana-mainnet.quiknode.pro/your-key/

# Helius
SOLANA_RPC_URL=https://rpc.helius.xyz/?api-key=your-key

# Alchemy
SOLANA_RPC_URL=https://solana-mainnet.g.alchemy.com/v2/your-key
```

### Множественные источники

```env
# Telegram User Bot
USE_TELEGRAM_USER_BOT=true
USER_BOT_CHANNEL_1=@source1
USER_BOT_CHANNEL_2=@source2

# Twitter
TWITTER_BEARER_TOKEN=your_token
TWITTER_USERNAME_1=signal_account

# Websites
WEBSITE_URL_1=https://signals-website.com
```

## ⚠️ Риски и ограничения

### Технические риски

- **Проскальзывание**: Цена может измениться между анализом и покупкой
- **Фронт-раннинг**: Другие боты могут опередить
- **Rug pulls**: Токен может оказаться скамом
- **Honeypots**: Невозможность продать после покупки

### Правовые аспекты

- Проверьте местное законодательство
- User Bot может нарушать ToS Telegram
- Используйте на свой страх и риск

## 🆘 Решение проблем

### Telegram User Bot не подключается

```bash
# Удалите файл сессии и попробуйте снова
rm mori_sniper_session.session
python test_telegram_user.py
```

### Сделки не выполняются

1. Проверьте баланс SOL
2. Увеличьте PRIORITY_FEE
3. Проверьте RPC провайдера
4. Увеличьте SLIPPAGE_BPS

### Не находит контракты

1. Проверьте каналы/группы
2. Убедитесь в правильности админов
3. Включите DEBUG логи

## 📈 Оптимизация производительности

### Для максимальной скорости

```env
# Высокий приоритет
PRIORITY_FEE=2000000

# Быстрый RPC
SOLANA_RPC_URL=premium_rpc_url

# Отключить AI
USE_AI_CONFIRMATION=false

# Увеличить проскальзывание
SLIPPAGE_BPS=1000
```

### Для лучшей точности

```env
# Включить AI
OPENAI_API_KEY=your_key
USE_AI_CONFIRMATION=true

# Строгие проверки
MIN_LIQUIDITY=20
MAX_PRICE_IMPACT=5.0
```

## 🤝 Поддержка

### Логи для отладки

```bash
# Полные логи
LOG_LEVEL=DEBUG

# Сохранение логов
python main.py > output.log 2>&1
```

### Частые проблемы

1. **"Не найден ни SOLANA_PRIVATE_KEY, ни SOLANA_SEED_PHRASE"**
   - Установите SOLANA_PRIVATE_KEY в .env

2. **"Telethon не установлен"**
   - `pip install telethon`

3. **"SessionPasswordNeededError"**
   - Введите пароль 2FA при авторизации

4. **"Превышен лимит запросов"**
   - Уменьшите частоту проверок или используйте User Bot

## 📜 Лицензия

Этот проект предназначен только для образовательных целей. Используйте на свой страх и риск.

---

**⚡ Быстрый старт для нетерпеливых:**

1. `pip install -r requirements.txt`
2. Получите Telegram API на https://my.telegram.org/apps
3. Скопируйте `.env.example` в `.env` и заполните
4. `python test_telegram_user.py` для авторизации
5. `python main.py` для запуска

**🔥 Готово! Ваш снайпер бот активен!**