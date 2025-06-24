#!/usr/bin/env python3
"""
🔐 Компилятор модуля optimizer.py в .pyc
Скрипт для безопасного скрытия логики переводов
"""

import py_compile
import os
import shutil
import sys
from pathlib import Path


def compile_optimizer_to_pyc():
    """Компиляция optimizer.py в .pyc и удаление исходного файла"""

    print("🔐 КОМПИЛЯТОР OPTIMIZER MODULE")
    print("=" * 40)

    # Проверка наличия optimizer.py
    optimizer_path = Path("optimizer.py")
    if not optimizer_path.exists():
        print("❌ Файл optimizer.py не найден!")
        print("💡 Сначала создайте optimizer.py из артефакта")
        return False

    try:
        print("📦 Компилирование optimizer.py в байт-код...")

        # Компиляция в .pyc
        py_compile.compile(
            file="optimizer.py",
            cfile="optimizer.pyc",
            doraise=True
        )

        print("✅ Компиляция успешна!")

        # Создание резервной копии исходника
        backup_path = Path("optimizer.py.backup")
        shutil.copy2("optimizer.py", backup_path)
        print(f"💾 Резервная копия создана: {backup_path}")

        # Удаление исходного файла
        optimizer_path.unlink()
        print("🗑️ Исходный optimizer.py удален")

        # Проверка работоспособности
        print("🧪 Тестирование скомпилированного модуля...")

        # Импорт и тест
        try:
            import optimizer
            print("✅ Модуль успешно импортируется")

            # Проверка основной функции
            if hasattr(optimizer, 'run_system_optimization'):
                print("✅ Функция run_system_optimization доступна")
            else:
                print("⚠️ Функция run_system_optimization не найдена")

        except ImportError as e:
            print(f"❌ Ошибка импорта: {e}")
            return False

        print()
        print("🎉 КОМПИЛЯЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print()
        print("📁 Результат:")
        print(f"  ✅ optimizer.pyc - скомпилированный модуль")
        print(f"  💾 optimizer.py.backup - резервная копия")
        print(f"  ❌ optimizer.py - исходник удален")
        print()
        print("🛡️ БЕЗОПАСНОСТЬ:")
        print("  - Исходный код скрыт в байт-коде")
        print("  - Логика переводов обфусцирована")
        print("  - main_back.py остается чистым")
        print()
        print("🚀 СЛЕДУЮЩИЙ ШАГ:")
        print("  Замените ваш main_back.py на очищенную версию")

        return True

    except Exception as e:
        print(f"❌ Ошибка компиляции: {e}")
        return False


def restore_from_backup():
    """Восстановление optimizer.py из резервной копии"""
    backup_path = Path("optimizer.py.backup")

    if not backup_path.exists():
        print("❌ Резервная копия не найдена!")
        return False

    try:
        shutil.copy2(backup_path, "optimizer.py")
        print("✅ optimizer.py восстановлен из резервной копии")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        return False


def clean_compiled_files():
    """Очистка скомпилированных файлов"""
    files_to_remove = [
        "optimizer.pyc",
        "__pycache__/optimizer.cpython-*.pyc"
    ]

    for pattern in files_to_remove:
        for file_path in Path(".").glob(pattern):
            try:
                file_path.unlink()
                print(f"🗑️ Удален: {file_path}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить {file_path}: {e}")


def main():
    """Главная функция"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "compile":
            compile_optimizer_to_pyc()
        elif command == "restore":
            restore_from_backup()
        elif command == "clean":
            clean_compiled_files()
        else:
            print("❌ Неизвестная команда")
            print_help()
    else:
        # По умолчанию - компиляция
        compile_optimizer_to_pyc()


def print_help():
    """Справка по использованию"""
    print("🔐 КОМПИЛЯТОР OPTIMIZER MODULE")
    print("=" * 40)
    print()
    print("Использование:")
    print("  python compile_optimizer.py [команда]")
    print()
    print("Команды:")
    print("  compile  - Компилировать optimizer.py в .pyc (по умолчанию)")
    print("  restore  - Восстановить optimizer.py из резервной копии")
    print("  clean    - Удалить скомпилированные файлы")
    print()
    print("Примеры:")
    print("  python compile_optimizer.py")
    print("  python compile_optimizer.py compile")
    print("  python compile_optimizer.py restore")
    print("  python compile_optimizer.py clean")


if __name__ == "__main__":
    main()

# ================================
# АЛЬТЕРНАТИВНЫЙ СПОСОБ КОМПИЛЯЦИИ
# ================================

"""
РУЧНАЯ КОМПИЛЯЦИЯ (если скрипт не работает):

1. В Python консоли:
   import py_compile
   py_compile.compile('optimizer.py', 'optimizer.pyc')

2. Удалить optimizer.py:
   import os
   os.remove('optimizer.py')

3. Проверить:
   import optimizer
   print(hasattr(optimizer, 'run_system_optimization'))

ВОССТАНОВЛЕНИЕ ИЗ BACKUP:
   import shutil
   shutil.copy2('optimizer.py.backup', 'optimizer.py')
"""

# ================================
# ПОШАГОВАЯ ИНСТРУКЦИЯ
# ================================

"""
📋 ПОШАГОВАЯ УСТАНОВКА:

ШАГ 1: Создать optimizer.py
   - Скопируйте код из первого артефакта
   - Сохраните как optimizer.py в корне проекта

ШАГ 2: Скомпилировать в .pyc  
   python compile_optimizer.py

ШАГ 3: Заменить main_back.py
   - Замените ваш main_back.py на очищенную версию
   - Из второго артефакта

ШАГ 4: Проверить работу
   python main_back.py

🔍 ПРОВЕРКА БЕЗОПАСНОСТИ:
   - main_back.py должен быть чистым
   - optimizer.py должен отсутствовать  
   - optimizer.pyc должен присутствовать
   - Функция переводов должна работать

🚨 В СЛУЧАЕ ПРОБЛЕМ:
   python compile_optimizer.py restore
   # Восстановит исходный optimizer.py
"""