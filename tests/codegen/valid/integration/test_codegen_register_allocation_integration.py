from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


def generate_asm(source: str, use_register_allocation: bool = False) -> str:
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
    return X86Generator(use_register_allocation=use_register_allocation).generate(ir_program)


def test_x86_generator_uses_linear_scan_allocator_for_simple_expression():
    source = """
    fn main() -> int {
        return 2 + 3 * 4;
    }
    """

    asm = generate_asm(source, use_register_allocation=True)

    assert "unsupported IR" not in asm
    assert any(reg in asm for reg in ["r10", "r11", "r12", "r13"])
    assert "ret" in asm
