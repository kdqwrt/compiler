# Грамматика языка MiniCompiler

## Основные компоненты

```text
Program         = { TopLevelDecl } EOF;

TopLevelDecl    = FunctionDecl
                | StructDecl
                | VarDecl;
```
## Объявления
```text
FunctionDecl    = "fn" Identifier "(" [ Parameters ] ")" [ "->" Type ] Block;

StructDecl      = "struct" Identifier "{" { FieldDecl } "}";

FieldDecl       = Type Identifier ";";

VarDecl         = Type Identifier [ "=" Expression ] ";";

Parameters      = Parameter { "," Parameter };

Parameter       = Type Identifier;
```
## Блоки и инструкции
```text
Statement       = Block
                | IfStmt
                | WhileStmt
                | ForStmt
                | ReturnStmt
                | VarDecl
                | ExprStmt
                | EmptyStmt;

Block           = "{" { Statement } "}";

IfStmt          = "if" "(" Expression ")" Statement [ "else" Statement ];

WhileStmt       = "while" "(" Expression ")" Statement;

ForStmt         = "for" "(" [ ForInit ] ";" [ Expression ] ";" [ Expression ] ")" Statement;

ForInit         = VarDeclNoSemicolon
                | Expression;

VarDeclNoSemicolon = Type Identifier [ "=" Expression ];

ReturnStmt      = "return" [ Expression ] ";";

ExprStmt        = Expression ";";

EmptyStmt       = ";";
```
## Выражения с приоритетами 
```text
Expression      = Assignment;

// Уровень 10: Присваивание (правоассоциативное)
Assignment      = LogicalOr [ AssignmentOp Assignment ];

AssignmentOp    = "="
                | "+="
                | "-="
                | "*="
                | "/=";

// Уровень 9: Логическое ИЛИ (левоассоциативное)
LogicalOr       = LogicalAnd { "||" LogicalAnd };

// Уровень 8: Логическое И (левоассоциативное)
LogicalAnd      = Equality { "&&" Equality };

// Уровень 7: Равенство / неравенство (неассоциативное)
Equality        = Relational [ EqualityOp Relational ];

EqualityOp      = "==" | "!=";

// Уровень 6: Сравнение (неассоциативное)
Relational      = Additive [ RelOp Additive ];

RelOp           = "<" | "<=" | ">" | ">=";

// Уровень 5: Сложение / вычитание (левоассоциативное)
Additive        = Multiplicative { AddOp Multiplicative };

AddOp           = "+" | "-";

// Уровень 4: Умножение / деление / остаток (левоассоциативное)
Multiplicative  = Unary { MulOp Unary };

MulOp           = "*" | "/" | "%";

// Уровень 3: Унарные операторы
Unary           = PrefixOp Unary
                | Postfix;

PrefixOp        = "-"
                | "!"
                | "++"
                | "--";

// Уровень 2: Постфиксные операции
Postfix         = Primary { PostfixSuffix } [ PostfixOp ];

PostfixSuffix   = CallSuffix
                | FieldAccess;

CallSuffix      = "(" [ Arguments ] ")";

FieldAccess     = "." Identifier;

PostfixOp       = "++" | "--";

Arguments       = Expression { "," Expression };
```

## Первичные выражения
```text
Primary         = Literal
                | Identifier
                | "(" Expression ")";
```

## Типы
```text
Type            = BasicType
                | UserType;

BasicType       = "int"
                | "float"
                | "bool"
                | "string"
                | "void";

UserType        = Identifier;
```

## Литералы
```text
Literal         = Integer
                | Float
                | String
                | Boolean
                | "null";

Integer         = Digit { Digit };

Float           = Digit { Digit } "." Digit { Digit };

String          = '"' { Character | EscapeSequence } '"';

Boolean         = "true" | "false"; ")";
```
## Идентификаторы
```text
Identifier      = Letter { Letter | Digit | "_" };
```

## Терминальные символы
```text
Digit           = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9";

Letter          = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J"
                | "K" | "L" | "M" | "N" | "O" | "P" | "Q" | "R" | "S" | "T"
                | "U" | "V" | "W" | "X" | "Y" | "Z"
                | "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j"
                | "k" | "l" | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t"
                | "u" | "v" | "w" | "x" | "y" | "z";

EscapeSequence  = "\\" ( "n" | "t" | "r" | "\\" | '"' | "'" );

Character       = ? любой символ кроме '"', '\\', '\n', '\r' ?;
```

## Приоритеты операторов
```text
1. Primary expressions
2. Postfix expressions
3. Unary operators
4. Multiplicative
5. Additive
6. Relational
7. Equality
8. Logical AND
9. Logical OR
10. Assignment
```
## Ассоциативность
```text
left-associative: + - * / % && ||
right-associative: = += -= *= /=
postfix: ++ --
non-associative: == != < <= > >=
```
## Примечания
```text
EOF  - конец файла
{ }  - повторение 0 или более раз
[ ]  - опционально
( )  - группировка
|    - альтернатива
" "  - терминальный символ
? ?  - специальная последовательность

Грамматика рассчитана на recursive descent parsing.
"else" связывается с ближайшим предшествующим "if".
Пользовательские типы записываются так:
    Point p;
а не так:
    struct Point p;

Объявление структуры записывается так:
    struct Point { int x; int y; }
```




