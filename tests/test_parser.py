import pytest

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast import *


def parse(code):
    tokens = Scanner(code).scan_tokens()
    parser = Parser(tokens)
    return parser.parse(), parser.get_errors()


def parse_stmt(stmt_source: str):
    code = f"""
    fn main() -> void {{
        {stmt_source}
    }}
    """
    program, errors = parse(code)
    return program, errors


def first_stmt(program):
    func = program.declarations[0]
    assert isinstance(func, FunctionDeclNode)
    assert isinstance(func.body, BlockStmtNode)
    assert len(func.body.statements) > 0
    return func.body.statements[0]


# =====================================
# expressions
# =====================================

def test_operator_precedence():
    program, errors = parse_stmt("1 + 2 * 3;")
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    expr = stmt.expression
    assert isinstance(expr, BinaryExprNode)
    assert expr.operator.lexeme == "+"
    assert isinstance(expr.right, BinaryExprNode)
    assert expr.right.operator.lexeme == "*"


def test_parentheses_precedence():
    program, errors = parse_stmt("(1 + 2) * 3;")
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    expr = stmt.expression
    assert isinstance(expr, BinaryExprNode)
    assert expr.operator.lexeme == "*"


def test_logical_precedence():
    program, errors = parse_stmt("a || b && c;")
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    expr = stmt.expression
    assert isinstance(expr, BinaryExprNode)
    assert expr.operator.lexeme == "||"
    assert isinstance(expr.right, BinaryExprNode)
    assert expr.right.operator.lexeme == "&&"


# =====================================
# statements
# =====================================

def test_if_statement():
    code = """
    fn main() -> void {
        if (x > 0) {
            x = x - 1;
        }
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    assert isinstance(stmt, IfStmtNode)


def test_if_else():
    code = """
    fn main() -> void {
        if (x) {
            y = 1;
        } else {
            y = 2;
        }
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    assert isinstance(stmt, IfStmtNode)
    assert stmt.else_branch is not None


def test_while_loop():
    code = """
    fn main() -> void {
        while (x > 0) {
            x = x - 1;
        }
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    assert isinstance(stmt, WhileStmtNode)


def test_for_loop():
    code = """
    fn main() -> void {
        for (int i = 0; i < 10; i = i + 1) {
            x = x + i;
        }
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    stmt = first_stmt(program)
    assert isinstance(stmt, ForStmtNode)


# =====================================
# declarations
# =====================================

def test_variable_declaration():
    program, errors = parse("int x = 5;")
    assert not errors, f"Parser errors: {errors}"

    decl = program.declarations[0]
    assert isinstance(decl, VarDeclStmtNode)
    assert decl.name.lexeme == "x"


def test_function_declaration():
    code = """
    fn main() -> void {
        return;
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    decl = program.declarations[0]
    assert isinstance(decl, FunctionDeclNode)
    assert decl.name.lexeme == "main"


def test_function_parameters():
    code = """
    fn add(int a, int b) -> int {
        return a + b;
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    decl = program.declarations[0]
    assert len(decl.parameters) == 2


def test_struct_declaration():
    code = """
    struct Point {
        int x;
        int y;
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    decl = program.declarations[0]
    assert isinstance(decl, StructDeclNode)
    assert decl.name.lexeme == "Point"


# =====================================
# full program
# =====================================

def test_factorial_program():
    code = """
    fn factorial(int n) -> int {
        int result = 1;
        while (n > 1) {
            result = result * n;
            n = n - 1;
        }
        return result;
    }
    """
    program, errors = parse(code)
    assert not errors, f"Parser errors: {errors}"

    assert len(program.declarations) == 1
    func = program.declarations[0]
    assert isinstance(func, FunctionDeclNode)
    assert func.name.lexeme == "factorial"


# =====================================
# syntax errors
# =====================================

def test_missing_semicolon():
    code = "int x = 5"
    tokens = Scanner(code).scan_tokens()
    parser = Parser(tokens)
    parser.parse()

    errors = parser.get_errors()
    assert len(errors) > 0
    assert any("Expected ';'" in e for e in errors)


def test_missing_parenthesis():
    code = """
    fn main() -> void {
        if (x > 0 {
            x = 1;
        }
    }
    """
    tokens = Scanner(code).scan_tokens()
    parser = Parser(tokens)
    parser.parse()

    errors = parser.get_errors()
    assert len(errors) > 0
    assert any("Expected ')'" in e for e in errors), f"No 'Expected )' error in {errors}"


def test_unexpected_token():
    code = "int x = @42;"
    scanner = Scanner(code)
    tokens = scanner.scan_tokens()

    lex_errors = scanner.get_errors()

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()

    assert len(lex_errors) + len(parse_errors) > 0
    assert ast is not None


def test_error_recovery():
    code = """
    int x = ;
    int y = 42;
    fn main() -> void {
        return y;
    }
    """
    tokens = Scanner(code).scan_tokens()
    parser = Parser(tokens)
    ast = parser.parse()

    errors = parser.get_errors()
    assert len(errors) > 0

    assert len(ast.declarations) >= 2
    assert any(isinstance(decl, FunctionDeclNode) for decl in ast.declarations)