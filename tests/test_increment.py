import pytest
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast import (
    expr_to_str,
    ExprStmtNode, UnaryExprNode, IdentifierExprNode,
    AssignmentExprNode, BinaryExprNode,
    FunctionDeclNode, BlockStmtNode
)


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
    assert not errors, f"Errors: {errors}"

    assert len(program.declarations) == 1
    func = program.declarations[0]
    assert isinstance(func, FunctionDeclNode)

    body = func.body
    assert isinstance(body, BlockStmtNode)
    assert len(body.statements) >= 1

    return body.statements[0]


def test_increment_lexer():
    """Тест распознавания токенов ++ и --"""
    source = "i++ ++i i-- --i"
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    token_types = [t.type.name for t in tokens[:-1]]
    expected = [
        "IDENTIFIER", "INCREMENT",
        "INCREMENT", "IDENTIFIER",
        "IDENTIFIER", "DECREMENT",
        "DECREMENT", "IDENTIFIER"
    ]
    assert token_types == expected

    lexemes = [t.lexeme for t in tokens[:-1]]
    expected_lexemes = ["i", "++", "++", "i", "i", "--", "--", "i"]
    assert lexemes == expected_lexemes


def test_prefix_increment():
    stmt = parse_stmt("++i;")
    assert isinstance(stmt, ExprStmtNode)

    expr = stmt.expression
    assert isinstance(expr, UnaryExprNode)
    assert expr.operator.type.name == "INCREMENT"
    assert expr.operator.lexeme == "++"

    operand = expr.operand
    assert isinstance(operand, IdentifierExprNode)
    assert operand.name.lexeme == "i"

    assert expr_to_str(expr) == "(++i)"


def test_postfix_increment():
    stmt = parse_stmt("i++;")
    assert isinstance(stmt, ExprStmtNode)

    expr = stmt.expression
    assert isinstance(expr, UnaryExprNode)
    assert hasattr(expr, "is_postfix") and expr.is_postfix
    assert expr.operator.type.name == "INCREMENT"
    assert expr.operator.lexeme == "++"

    operand = expr.operand
    assert isinstance(operand, IdentifierExprNode)
    assert operand.name.lexeme == "i"

    assert expr_to_str(expr) == "(i++)"


def test_prefix_decrement():
    stmt = parse_stmt("--i;")
    expr = stmt.expression

    assert isinstance(expr, UnaryExprNode)
    assert expr.operator.type.name == "DECREMENT"
    assert expr.operator.lexeme == "--"
    assert expr_to_str(expr) == "(--i)"


def test_postfix_decrement():
    stmt = parse_stmt("i--;")
    expr = stmt.expression

    assert isinstance(expr, UnaryExprNode)
    assert hasattr(expr, "is_postfix") and expr.is_postfix
    assert expr.operator.type.name == "DECREMENT"
    assert expr.operator.lexeme == "--"
    assert expr_to_str(expr) == "(i--)"


def test_increment_in_expression():
    stmt = parse_stmt("x = ++i + j--;")
    expr = stmt.expression

    assert isinstance(expr, AssignmentExprNode)

    right = expr.value
    assert isinstance(right, BinaryExprNode)
    assert right.operator.lexeme == "+"

    left_add = right.left
    assert isinstance(left_add, UnaryExprNode)
    assert left_add.operator.lexeme == "++"
    assert left_add.operand.name.lexeme == "i"

    right_add = right.right
    assert isinstance(right_add, UnaryExprNode)
    assert right_add.operator.lexeme == "--"
    assert hasattr(right_add, "is_postfix") and right_add.is_postfix
    assert right_add.operand.name.lexeme == "j"

    assert expr_to_str(expr) == "(x = ((++i) + (j--)))"


def test_multiple_increments():
    stmt = parse_stmt("++++i;")
    expr = stmt.expression

    assert isinstance(expr, UnaryExprNode)
    assert expr.operator.lexeme == "++"

    inner = expr.operand
    assert isinstance(inner, UnaryExprNode)
    assert inner.operator.lexeme == "++"
    assert inner.operand.name.lexeme == "i"

    assert expr_to_str(expr) == "(++(++i))"