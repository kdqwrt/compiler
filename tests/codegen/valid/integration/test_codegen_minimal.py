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

    ir_program = IRGenerator(analyzer.symbol_table).generate(ast)
    asm = X86Generator().generate(ir_program)
    return asm


def test_codegen_return_literal():
    source = """
    fn main() -> int {
        return 5;
    }
    """

    asm = generate_asm(source)

    assert "section .text" in asm
    assert "global main" in asm
    assert "main:" in asm
    assert "push rbp" in asm
    assert "mov rbp, rsp" in asm
    assert "mov eax, 5" in asm
    assert "ret" in asm