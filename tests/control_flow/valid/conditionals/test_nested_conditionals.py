from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


def generate_asm(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    ir_program = IRGenerator(analyzer.get_symbol_table()).generate(ast)
    return X86Generator().generate(ir_program)


def test_nested_if_else_codegen():
    source = """
    fn main() -> int {
        int x = 5;
        int y = 0;

        if (x > 0) {
            if (x > 3) {
                y = 10;
            } else {
                y = 20;
            }
        } else {
            y = 30;
        }

        return y;
    }
    """

    asm = generate_asm(source)

    assert ".main_then" in asm
    assert ".main_else" in asm
    assert ".main_endif" in asm
    assert "cmp eax," in asm
    assert "ret" in asm