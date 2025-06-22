# 🚨 АВАРИЙНЫЕ СКРИПТЫ ПОКУПКИ

Система аварийной покупки токенов на случай отказа основного мониторинга.

## 📋 ДОСТУПНЫЕ СКРИПТЫ

### 1. `emergency_buy.py` - Интерактивная аварийная покупка
**Использование:** `python emergency_buy.py`

- ✅ Интерактивный ввод контракта
- ✅ Подтверждение перед покупкой  
- ✅ Подробные результаты
- ✅ Поддержка всех форматов ввода
- ✅ Показ текущих настроек

### 2. `quick_buy.py` - Мгновенная покупка
**Использование:** `python quick_buy.py CONTRACT_ADDRESS`

- ⚡ Максимальная скорость
- ⚡ Без подтверждений
- ⚡ Командная строка
- ⚡ Компактные результаты

### 3. `check_balance.py` - Проверка балансов
**Использование:** `python check_balance.py`

- 💰 Показывает доступные средства
- 💰 Анализирует готовность к покупке
- 💰 Быстрый режим: `python check_balance.py --quick`

---

## 🎯 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Проверка баланса перед покупкой:
```bash
# Подробная проверка
python check_balance.py

# Быстрая проверка
python check_balance.py --quick
```

### Интерактивная покупка:
```bash
python emergency_buy.py
# Введите контракт: JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN
# Подтвердить покупку? [y/N]: y
```

### Мгновенная покупка:
```bash
# Прямой контракт
python quick_buy.py JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN

# Jupiter ссылка
python quick_buy.py "https://jup.ag/swap/So11111111111111111111111111111111111111112-JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"

# Dexscreener ссылка  
python quick_buy.py "https://dexscreener.com/solana/JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
```

---

## ⚙️ ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ ВВОДА

### Прямые контракты:
```
JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN
```

### Jupiter ссылки:
```
https://jup.ag/swap/So11111111111111111111111111111111111111112-JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN
jup.ag/swap/SOL-CONTRACT
```

### DEX ссылки:
```
https://dexscreener.com/solana/CONTRACT
https://raydium.io/swap/?inputMint=CONTRACT
https://birdeye.so/token/CONTRACT
```

### Произвольный текст:
```
"Новый токен JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN покупаем!"
```

---

## 🎭 РЕЖИМЫ РАБОТЫ

### Одиночный кошелек:
```env
USE_MULTI_WALLET=false
TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=3
```
**Результат:** 3 покупки по 0.1 SOL с одного кошелька

### Множественные кошельки - фиксированные суммы:
```env
USE_MULTI_WALLET=true
USE_MAX_AVAILABLE_BALANCE=false
TRADE_AMOUNT_SOL=0.1
NUM_PURCHASES=2
```
**Результат:** По 2 покупки по 0.1 SOL с каждого готового кошелька

### Множественные кошельки - весь баланс:
```env
USE_MULTI_WALLET=true
USE_MAX_AVAILABLE_BALANCE=true
```
**Результат:** Тратится весь доступный баланс с каждого кошелька

---

## 💡 СЦЕНАРИИ ИСПОЛЬЗОВАНИЯ

### 🔥 СРОЧНАЯ ПОКУПКА (секунды на счету):
```bash
# 1. Быстрая проверка баланса
python check_balance.py -q

# 2. Мгновенная покупка  
python quick_buy.py CONTRACT_HERE
```

### 🎯 ОБЫЧНАЯ АВАРИЙНАЯ ПОКУПКА:
```bash
# 1. Проверка баланса
python check_balance.py

# 2. Интерактивная покупка
python emergency_buy.py
```

### 📊 МОНИТОРИНГ ПЕРЕД ЛИСТИНГОМ:
```bash
# Проверяем готовность каждые 30 секунд
while true; do
    python check_balance.py -q
    echo "Готов к покупке. Ждем листинг..."
    sleep 30
done
```

---

## 🛡️ БЕЗОПАСНОСТЬ

### Все скрипты используют настройки из `.env`:
- ✅ Лимиты проскальзывания
- ✅ Проверки ликвидности  
- ✅ Максимальные суммы сделок
- ✅ Фильтры безопасности

### Встроенные защиты:
- 🛡️ Проверка валидности контракта
- 🛡️ Фильтрация Wrapped SOL
- 🛡️ Проверка достаточности баланса
- 🛡️ Все проверки безопасности Jupiter

### Резервы газа:
- 💨 Автоматический резерв на газ
- 💨 Проверка минимального баланса
- 💨 Защита от полного опустошения кошелька

---

## 📝 ЛОГИРОВАНИЕ

### Файлы логов:
- `logs/sniper.log` - Подробные логи
- Консоль - Важные события

### Уровни логирования:
```env
LOG_LEVEL=INFO    # Основная информация
LOG_LEVEL=DEBUG   # Детальная отладка  
LOG_LEVEL=ERROR   # Только ошибки
```

---

## ❌ РЕШЕНИЕ ПРОБЛЕМ

### "Контракт не найден":
```bash
# Попробуйте разные форматы:
python quick_buy.py JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN
python quick_buy.py "jup.ag/swap/So11111111111111111111111111111111111111112-JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
```

### "Недостаточно средств":
```bash
# Проверьте баланс
python check_balance.py

# Пополните кошельки или уменьшите TRADE_AMOUNT_SOL
```

### "Торговая система не запускается":
```bash
# Проверьте настройки в .env:
# - SOLANA_RPC_URL
# - SOLANA_PRIVATE_KEY или SOLANA_SEED_PHRASE  
# - Jupiter API настройки
```

### "Множественные кошельки не работают":
```bash
# Проверьте:
# USE_MULTI_WALLET=true
# MULTI_WALLET_PRIVATE_KEYS=key1,key2,key3

# Или отключите:
# USE_MULTI_WALLET=false
```

---

## ⚡ ОПТИМИЗАЦИЯ СКОРОСТИ

### Максимальная скорость:
1. Используйте `quick_buy.py`
2. Подготовьте контракт заранее
3. Отключите лишние проверки безопасности
4. Используйте быстрый RPC провайдер

### Подготовка команд:
```bash
# Подготовьте команду заранее
CONTRACT="JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
python quick_buy.py $CONTRACT
```

### Алиасы для быстроты:
```bash
# В .bashrc или .zshrc:
alias emergency="python emergency_buy.py"
alias quickbuy="python quick_buy.py"  
alias balance="python check_balance.py -q"

# Использование:
balance
quickbuy CONTRACT_HERE
```

---

## 📈 МОНИТОРИНГ РЕЗУЛЬТАТОВ

### Подписи транзакций:
Все успешные покупки выводят подписи транзакций для отслеживания в Solana Explorer.

### Пример вывода:
```
✅ ГОТОВО: 3/3 успешно
💰 Потрачено: 0.300000 SOL  
🪙 Куплено: 750,000 токенов
⏱️ Время: 2.1s
📝 Подписи:
   1. 5J7X8k9...signature1
   2. 3M2N9f1...signature2  
   3. 8K5L2h3...signature3
```

---

## 🔧 ИНТЕГРАЦИЯ С ОСНОВНЫМ БОТОМ

### Аварийные скрипты полностью совместимы:
- ✅ Используют ту же конфигурацию
- ✅ Те же настройки безопасности
- ✅ Ту же торговую систему
- ✅ Те же кошельки

### Можно запускать одновременно:
- Основной бот мониторит каналы
- Аварийный скрипт для ручной покупки
- Конфликтов нет

---

## 🎯 БЫСТРЫЙ СТАРТ

1. **Проверьте настройки:**
   ```bash
   python check_balance.py
   ```

2. **Тест с безопасным токеном (JUP):**
   ```bash
   python quick_buy.py JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN
   ```

3. **Готово к боевому применению!** 🚀