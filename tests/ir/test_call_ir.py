from src.lexer.scanner import Scanner
from src.parser.parser import Parser
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
    return ir_gen.generate(ast)


def test_function_call_ir():
    source = """
        fn foo(int x) -> int {
            return x + 1;
        }

        fn main() -> int {
            int y = 5;
            return foo(y);
        }
        """

    program = generate_ir(source)
    text = program.to_text()

    assert "PARAM" in text
    assert "CALL" in text
    assert "RETURN" in text