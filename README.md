# MiniCompiler




## Реализованные возможности

**Лексический анализатор (Lexer)**
- Распознавание всех ключевых слов языка (if, else, while, for, int, float, bool, return, true, false, struct, fn)
- Идентификаторы с проверкой длины 
- Литералы: целые, вещественные, строковые, булевы
- Операторы
- Разделители и обработка EOF
- Отслеживание позиции (строка, колонка) с поддержкой Windows (\r\n) и Unix (\n) окончаний строк
- Восстановление после ошибок с выводом диагностических сообщений

**Препроцессор (Preprocessor)**
- Удаление однострочных (//) и многострочных (/* */) комментариев
- Сохранение комментариев внутри строковых литералов
- Обработка макросов: #define, #undef

## Технические характеристики

- **Язык реализации**: Python 3.12+
- **Интерфейс**: командная строка (CLI)
- **Кодировка исходных файлов**: UTF-8
- **Поддерживаемые платформы**: Windows, Linux
- **Система сборки**: pyproject.toml


## Структура проекта
```
compiler-project/
├── src/
│ ├── lexer/
│ │ ├── init.py
│ │ ├── scanner.py # Основная логика сканера
│ │ └── tokens.py # Определения типов токенов
│ ├── preprocessor/
│ │ ├── init.py
│ │ ├── macros.py # Обработка директив макросов
│ │ └── preprocessor.py # Удаление комментариев
│ └── utils/
│ └── cli.py # Интерфейс командной строки
├── tests/
│ ├── lexer/
│ │ ├── valid/ # Позитивные тесты (.src + .expected)
│ │ └── invalid/ # Негативные тесты (.src + .expected)
│ ├── test_p.py # Модульные тесты (pytest)
│ └── test_runner.py # Интеграционный тест-раннер
├── examples/ # Примеры исходного кода
├── docs/
│ └── language_spec.md # Формальная спецификация языка
├── pyproject.toml # Конфигурация проекта и entry points
└── README.md
```

## Установка и сборка

### Требования
- Python 3.12 или выше
- pip (менеджер пакетов Python)

### Установка проекта

```bash
# Клонирование репозитория
git clone <url-репозитория>
cd compiler-project

# Установка в режиме разработки (режим editable)
pip install -e .

# Установка с зависимостями для разработки
pip install -e ".[dev]"
```

### Быстрый старт

Создайте тестовый файл examples/hello.src:

```bash
fn main() {
    int x = 42;
    string msg = "Hello";
}
Запустите лексический анализ:
```
```bash
compiler lex --input examples/hello.src
```


### Препроцессор
```bash
# Обработка комментариев и макросов
compiler preprocess --input <файл>
```

```bash
# Просмотр результата в консоли
compiler preprocess --input <файл> --show
```


### Запуск тестов
```bash
# Запуск модульных тестов (pytest)
pytest tests/test_p.py -v

pytest tests/test_lexer.py -v

pytest tests/test_cli.py -v
# Запуск интеграционных тестов
python tests/test_runner.py

