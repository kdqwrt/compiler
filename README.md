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

## Compilation Pipeline

Компиляция программы выполняется по следующему конвейеру:

```text
Source
  ↓
Preprocessor
  ↓
Lexer
  ↓
Parser
  ↓
AST
  ↓
Semantic Analysis
  ↓
IR Generation
  ↓
IR Optimization
  ↓
Register Allocation
  ↓
Assembly Generation
  ↓
Peephole Optimization
  ↓
NASM
  ↓
ELF Object
  ↓
Linker
  ↓
Executable
```

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


## Intermediate Representation (IR)

Компилятор использует собственное промежуточное представление (IR).

Основные инструкции:

```text
MOVE
ADD
SUB
MUL
DIV

LOAD
STORE

GEP

PARAM
CALL
RETURN

CMP_EQ
CMP_NE
CMP_LT
CMP_LE
CMP_GT
CMP_GE

JUMP
JUMP_IF
```

Пример:

```text
t1 = MUL 3, 4
t2 = ADD 2, t1
RETURN t2
```



## Control Flow Generation

Реализована генерация управления потоком выполнения:

### Conditionals
- `if`
- `if / else`
- nested conditionals

### Loops
- `while`
- `for`

### Short-circuit logic
- `&&`
- `||`

Для short-circuit правая часть вычисляется только при необходимости.

Пример:

```c
if (a != 0 && b / a > 2)
```

Сначала проверяется `a != 0`.  
Если условие ложно — деление не выполняется.

---

## Direct Conditional Jumps

Ранее boolean-условие материализовывалось через `setcc`.

Было:

```asm
cmp eax, 3
setg al
cmp al, 0
je .endif
```

Теперь реализованы direct jumps:

```asm
cmp eax, 3
jle .endif
```

Используются:
- `jg`
- `jl`
- `jge`
- `jle`
- `je`
- `jne`
- `ja`
- `jb`
- `jae`
- `jbe`

Это уменьшает число инструкций и убирает лишнюю materialization boolean.

---

## Register Allocation (Linear Scan)

Добавлен  linear scan register allocation.

При запуске:

```bash
--use-register-allocation
```

локальные переменные размещаются в регистрах.

Было:

```asm
mov dword [rbp-8], 4
mov dword [rbp-16], 2
```

Стало:

```asm
mov r12d, 4
mov r13d, 2
```

Используются:
- `r12/r13` — локальные переменные
- `r10/r11` — временные значения

### ABI Safety

Так как `r12/r13` являются callee-saved, реализовано сохранение:

```asm
mov qword [rbp-56], r12
mov qword [rbp-64], r13
```

и восстановление:

```asm
mov r12, qword [rbp-56]
mov r13, qword [rbp-64]
```



---

## Global Variables

Поддерживаются глобальные переменные.

Пример:

```c
int g = 0;

fn main() -> int {
    g = 7;
    return g;
}
```

ASM:

```asm
section .data
global g
g: dq 0
```

---

## Float Support

Поддерживаются:
- float literals
- float return
- float variables
- float arithmetic
- float comparison
- int → float conversion

Константы выносятся в `.rodata`:

```asm
section .rodata
__float_const_0: dq 3.14
```

Используются SSE инструкции:
- `movsd`
- `addsd`
- `subsd`
- `mulsd`
- `divsd`
- `ucomisd`
- `cvtsi2sd`

---

## Peephole Optimization

После генерации ASM запускается peephole optimizer.

Используется окно:

```python
window_size = 5
```

Оптимизатор анализирует локальные группы инструкций и выполняет несколько проходов.

---

## Реализованные оптимизации

### 1. Constant Folding (ASM-level)

Свёртка арифметики с константами.

Было:

```asm
mov eax, 10
add eax, 5
```

Стало:

```asm
mov eax, 15
```

Поддерживается:
- сложение
- вычитание
- умножение

---

### 2. Strength Reduction

Умножение на степень двойки заменяется на сдвиг.

Было:

```asm
imul eax, 4
```

Стало:

```asm
shl eax, 2
```

---

### 3. Arithmetic Identity Elimination

Удаляются:
- `add eax, 0`
- `sub eax, 0`
- `imul eax, 1`

Замена:

```asm
imul eax, 0
```

на:

```asm
mov eax, 0
```

---

### 4. Redundant Move Elimination

Удаляется:

```asm
mov eax, eax
```

---

### 5. Move Chain Collapse

Было:

```asm
mov eax, r11d
mov r10d, eax
```

Стало:

```asm
mov r10d, r11d
```

---

### 6. Dead Code Elimination

Удаляется код после:
- `ret`
- `jmp`

Пример:

```asm
ret
mov eax, 5
```

→ удаляется.

---

### 7. Jump Cleanup

Удаляется:

```asm
jmp .L1
.L1:
```


## Runtime and External Functions

Поддерживаются вызовы внешних функций:

```text
printf
scanf
malloc
free
strlen
pow
```

Вызовы выполняются согласно System V AMD64 ABI.

Аргументы передаются через:

```text
rdi
rsi
rdx
rcx
r8
r9
```

Результат возвращается через:

```text
rax
```

## Arrays

Поддерживаются одномерные массивы.

Особенности реализации:

- массивы выделяются через malloc
- размер вычисляется как sizeof(type) * count
- на стеке хранится указатель на массив
- доступ выполняется через GEP
- поддерживается bounds checking
- для константных индексов bounds check может быть удалён на этапе компиляции

## Optimization Pipeline

Оптимизации выполняются в следующем порядке:

1. Constant Folding
2. Constant Propagation
3. Dead Code Elimination
4. Dead Store Elimination
5. Control Flow Simplification
6. Register Allocation
7. Peephole Optimization
```


---


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
cd compiler

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


## CLI: NASM Build (Linux / Ubuntu)

Сборка ASM:

```bash
nasm -f elf64 hello.asm -o hello.o
nasm -f elf64 src/runtime/runtime.asm -o runtime.o
ld -o hello_program runtime.o hello.o
```

Запуск:

```bash
./hello_program
echo $?
```

---
## Testing Strategy

Используются:

- Unit Tests
- Golden Tests
- Integration Tests
- Regression Tests
- Differential Tests
- Property-Based Tests
- Fuzz Tests

Проверяются все этапы компиляции:

```text
Lexer
Parser
Semantic
IR
Optimizer
Codegen
CLI
Executable
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