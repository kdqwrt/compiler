from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


def generate_asm(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    ir_program = IRGenerator(analyzer.symbol_table).generate(ast)
    return X86Generator().generate(ir_program)


def test_codegen_add_expression():
    source = """
    fn main() -> int {
        return 2 + 3;
    }
    """

    asm = generate_asm(source)

    assert "mov eax, 5" in asm
    assert "ret" in asm