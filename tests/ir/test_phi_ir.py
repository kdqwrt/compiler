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


def test_phi_generated_for_if_else_merge():
    source = """
    fn main() -> int {
        int x = 0;
        if (1 < 2) {
            x = 10;
        } else {
            x = 20;
        }
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "PHI" in text
    assert "merge x" in text or "store merged x" in text
    assert "RETURN" in text


def test_phi_not_generated_without_else():
    source = """
    fn main() -> int {
        int x = 0;
        if (1 < 2) {
            x = 10;
        }
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "RETURN" in text
    assert "PHI" not in text


def test_phi_not_generated_for_different_targets():
    source = """
    fn main() -> int {
        int x = 0;
        int y = 0;
        if (1 < 2) {
            x = 10;
        } else {
            y = 20;
        }
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()

    assert "RETURN" in text
    assert "PHI" not in text