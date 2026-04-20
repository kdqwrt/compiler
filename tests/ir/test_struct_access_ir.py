from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def generate_ir(source: str):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    ir_gen = IRGenerator(analyzer.symbol_table)
    return ir_gen.generate(ast)


def test_struct_field_load_and_store_ir():
    source = """
    struct Point {
        int x;
        int y;
    }

    fn main() -> int {
        Point p;
        p.x = 10;
        return p.x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "GEP" in text
    assert "STORE [" in text
    assert "LOAD [" in text
    assert "RETURN" in text


def test_struct_field_compound_assignment_ir():
    source = """
    struct Point {
        int x;
        int y;
    }

    fn main() -> int {
        Point p;
        p.x = 1;
        p.x += 2;
        return p.x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "GEP" in text
    assert "LOAD [" in text
    assert "ADD" in text
    assert "STORE [" in text
    assert "RETURN" in text


def test_struct_field_used_in_expression_ir():
    source = """
    struct Point {
        int x;
        int y;
    }

    fn main() -> int {
        Point p;
        p.x = 4;
        return p.x + 1;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "GEP" in text
    assert "LOAD [" in text
    assert "ADD" in text
    assert "RETURN" in text