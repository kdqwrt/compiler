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
    return X86Generator().generate(ir_program)


def test_codegen_function_call_two_args():
    source = """
    fn add(int a, int b) -> int {
        return a + b;
    }

    fn main() -> int {
        return add(2, 3);
    }
    """

    asm = generate_asm(source)

    assert "global add" in asm
    assert "add:" in asm
    assert "global main" in asm
    assert "main:" in asm

    assert "mov qword [rbp-" in asm
    assert "mov rdi, 2" in asm
    assert "mov rsi, 3" in asm
    assert "call add" in asm
    assert "ret" in asm