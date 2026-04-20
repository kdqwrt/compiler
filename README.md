# MiniCompiler

MiniCompiler — учебный компилятор для упрощённого C-подобного языка.  
На текущем этапе реализованы:

- препроцессинг
- лексический анализ
- синтаксический анализ
- построение AST
- вывод AST в форматах text, DOT и JSON
- семантический анализ
- таблица символов
- система типов
- набор модульных и golden-тестов

---

## Содержание

- [Реализованные возможности](#реализованные-возможности)
- [Технические характеристики](#технические-характеристики)
- [Структура проекта](#структура-проекта)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [CLI](#cli)
- [Формальная грамматика](#формальная-грамматика)
- [AST](#ast)
- [Тестирование](#тестирование)
- [Примеры](#примеры)


## Реализованные возможности

### Препроцессор
- удаление однострочных комментариев `// ...`
- удаление многострочных комментариев `/* ... */`
- поддержка директив `#define` и `#undef`
- сохранение содержимого строковых литералов

### Лексический анализатор
- ключевые слова: `fn`, `struct`, `if`, `else`, `while`, `for`, `return`
- базовые типы: `int`, `float`, `bool`, `string`, `void`
- литералы: `int`, `float`, `string`, `bool`, `null`
- идентификаторы
- арифметические, логические, сравнительные и присваивающие операторы
- операторы `++` и `--`
- отслеживание позиции токена: строка и колонка
- восстановление после части лексических ошибок

### Парсер
- построение AST из токенов
- базовое восстановление после синтаксических ошибок
- обработка:
  - объявлений переменных
  - объявлений функций
  - объявлений структур
  - блоков
  - `if / else`
  - `while`
  - `for`
  - `return`
  - выражений
  - вызовов функций
  - доступа к полям структуры

### Семантический анализатор
- иерархическая таблица символов (symbol table)
- области видимости: global, function, block и struct scope
- регистрация функций, параметров, переменных и структур
- проверка duplicate declaration (повторного объявления)
- проверка undeclared identifier (использования необъявленного идентификатора)
- проверка use before declaration (использования до объявления)
- проверка uninitialized variable (использования неинициализированной переменной)
- проверка type mismatch (несовпадения типов)
- проверка вызовов функций:
  - число аргументов
  - типы аргументов
  - соответствие return type
- проверка булевых условий в `if`, `while`, `for`
- проверка изменяемости целевого объекта для операций присваивания и `++/--`
- decorated AST:
  - `inferred_type` — выведенный тип выражения
  - `symbol` — ссылка на запись в таблице символов
  - `constant_value` — вычисленное значение константы (если возможно)
- формирование validation report (отчёта о проверке)
- вывод таблицы символов (symbol table dump)
- сводка по размещению в памяти (memory layout summary)

## AST

Абстрактное синтаксическое дерево (Abstract Syntax Tree, AST) используется как промежуточное представление программы.

Поддерживается:

- текстовый вывод (pretty-print)
- экспорт в JSON
- экспорт в Graphviz DOT
- обход дерева с помощью visitor pattern

## Тестирование

В проекте используются:

- модульные тесты (unit tests)
- golden tests (сравнение с эталонным выводом)
- интеграционные тесты CLI
- тесты производительности


## Технические характеристики

- **Язык реализации**: Python 3.12+
- **Интерфейс**: командная строка (CLI)
- **Кодировка исходных файлов**: UTF-8
- **Поддерживаемые платформы**: Windows, Linux
- **Система сборки**: pyproject.toml

### Парсер
- recursive descent parser
- построение AST из токенов
- базовое восстановление после синтаксических ошибок
- обработка:
  - объявлений переменных
  - объявлений функций
  - объявлений структур
  - блоков
  - `if / else`
  - `while`
  - `for`
  - `return`
  - выражений
  - вызовов функций
  - доступа к полям структуры

### AST
- текстовый pretty-print
- экспорт в Graphviz DOT
- экспорт в JSON
- visitor для обхода AST

## Структура проекта

```text
compiler-project/
├── src/
│   ├── lexer/
│   │   ├── scanner.py
│   │   └── tokens.py
│   ├── parser/
│   │   ├── ast.py
│   │   ├── grammar.txt
│   │   ├── parser.py
│   │   └── visitor.py
│   ├── preprocessor/
│   │   ├── macros.py
│   │   └── preprocessor.py
│   ├── semantic/
│   │   ├── analyzer.py
│   │   ├── errors.py
│   │   ├── symbol_table.py
│   │   └── type_system.py
│   ├── utils/
│   └── cli.py
├── tests/
│   ├── lexer/
│   ├── parser/
│   │   └── golden/
│   ├── semantic/
│   │   ├── invalid/
│   │   │   ├── expected/
│   │   │   └── samples/
│   │   └── valid/
│   │       ├── expected/
│   │       └── samples/
│   ├── test_cli.py
│   ├── test_golden_valid.py
│   ├── test_increment.py
│   ├── test_lexer.py
│   ├── test_p.py
│   ├── test_parser.py
│   ├── test_performance.py
│   ├── test_symbol_table.py
│   ├── test_type_system.py
│   └── test_runner.py
├── examples/
├── docs/
│   ├── language_spec.md
│   └── grammar.md
├── pyproject.toml
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

### CLI




### Быстрый старт

Создайте тестовый файл examples/hello.src:

```bash
fn main() -> void {
    int x = 42;
    string msg = "Hello";
    return;
}
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

### Лексический анализ
```bash
compiler lex --input examples/hello.src
```

### Построение AST в текстовом формате
```bash
compiler parse --input hello1.src --output ast.txt
```

### Построение AST в json
```bash
compiler parse --input hello1.src --format json --output ast.json
```

### Построение AST в dot
```bash
compiler parse --input hello1.src --format dot --output ast.dot
```

### Сохранение AST в .png
```bash
dot -Tpng ast.dot -o ast.png
```

### Запуск тестов
```bash
# Запуск модульных тестов (pytest)
pytest tests\ -v

pytest tests/test_p.py -v

pytest tests/test_lexer.py -v

pytest tests/test_cli.py -v
# Запуск интеграционных тестов
python tests/test_runner.py
```

## Формальная грамматика

#### Формальная грамматика языка находится в:
```text
src/parser/grammar.txt
```

Грамматика записана в EBNF.
Стартовый символ:
```text
Program ::= { TopLevelDecl } EOF
```

### Основные конструкции
```text
TopLevelDecl ::= FunctionDecl
               | StructDecl
               | VarDecl

FunctionDecl ::= "fn" Identifier "(" [ Parameters ] ")" [ "->" Type ] Block
StructDecl   ::= "struct" Identifier "{" { FieldDecl } "}"
VarDecl      ::= Type Identifier [ "=" Expression ] ";"
```
### Операторы и приоритеты

Приоритет операторов от большего к меньшему:

- Primary expressions

- Postfix expressions

- Unary operators

- Multiplicative

- Additive

- Relational

- Equality

- Logical AND

- Logical OR

- Assignment

### Ассоциативность:

- left-associative: `+ - * / % && ||`

- right-associative: `= += -= *= /=`

- non-associative: `== != < <= > >=`


### шпаргалка
```
compiler preprocess --input hello.src --output hello1.src

compiler lex --input hello1.src

compiler parse --input hello1.src

compiler parse --input hello1.src --output ast.txt

compiler parse --input hello1.src --format json --output ast.json

compiler parse --input hello1.src --format dot --output ast.dot

dot -Tpng ast.dot -o ast.png

compiler check --input hello1.src

compiler check --input hello1.src --show-types

compiler check --input hello1.src --show-ast

compiler check --input hello1.src --show-report

compiler symbols --input hello1.src

compiler ir --input hello.src

compiler ir --input hello.src --format dot --output cfg.dot

dot -Tpng cfg.dot -o cfg.png

compiler ir --input hello.src --stats

compiler ir --input hello.src --validate

```