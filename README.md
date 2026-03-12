# MiniCompiler

MiniCompiler — учебный компилятор для упрощённого C-подобного языка.  
На текущем этапе реализованы:

- препроцессинг
- лексический анализ
- синтаксический анализ
- построение AST
- вывод AST в форматах text, DOT и JSON
- набор модульных и golden-тестов

---

## Содержание

- [Реализованные возможности](#реализованные-возможности)
- [Технические характеристики](#технические-характеристики)
- [Структура проекта](#структура-проекта)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [CLI](#cli)
- [Команда parse](#команда-parse)
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
│   ├── utils/
│   └── cli.py
├── tests/
│   ├── lexer/
│   ├── parser/
│   │   └── golden/
│   ├── test_cli.py
│   ├── test_lexer.py
│   ├── test_parser.py
│   ├── test_p.py
│   ├── test_performance.py
│   └── test_runner.py
├── examples/
├── docs/
│   └── language_spec.md
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

### Быстрый старт

Создайте тестовый файл examples/hello.src:

```bash
fn main() {
    int x = 42;
    string msg = "Hello";
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
```