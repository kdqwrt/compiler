import pytest

from src.parser.parser import Parser
from src.lexer.scanner import Scanner
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def generate_ir(source: str):
    # Лексер
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    # Парсер
    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    # Семантика
    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    # IR
    ir_gen = IRGenerator(analyzer.symbol_table)
    program = ir_gen.generate(ast)

    return program


def test_simple_arithmetic_ir():
    source = """
    fn main() -> int {
        return 2 + 3;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "ADD" in text
    assert "RETURN" in text
    assert "2" in text
    assert "3" in text


def test_variable_declaration_ir():
    source = """
    fn main() -> int {
        int x = 5;
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "ALLOCA" in text
    assert "STORE" in text
    assert "LOAD" in text
    assert "RETURN" in text


def test_assignment_ir():
    source = """
    fn main() -> int {
        int x = 5;
        x = x + 2;
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "ADD" in text
    assert "STORE" in text
    assert "LOAD" in text


def test_unary_ir():
    source = """
    fn main() -> int {
        int x = 5;
        x = -x;
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "NEG" in text
    assert "STORE" in text


def test_increment_ir():
    source = """
    fn main() -> int {
        int x = 1;
        ++x;
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "ADD" in text
    assert "STORE" in text
    assert "LOAD" in text