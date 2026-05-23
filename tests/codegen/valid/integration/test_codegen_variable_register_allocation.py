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


def test_local_variables_are_allocated_to_registers_when_enabled():
    source = """
    fn main() -> int {
        int x = 5;
        int y = 10;
        x = x + y;
        return x;
    }
    """

    asm = generate_asm(source, use_register_allocation=True)

    assert "r12d" in asm
    assert "r13d" in asm

    assert "mov qword [rbp-" in asm
    assert "mov r12, qword [rbp-" in asm
    assert "mov r13, qword [rbp-" in asm


def test_register_allocation_can_be_disabled():
    source = """
    fn main() -> int {
        int x = 5;
        int y = 10;
        x = x + y;
        return x;
    }
    """

    asm = generate_asm(source, use_register_allocation=False)

    assert "dword [rbp-" in asm
    assert "r12d" not in asm
    assert "r13d" not in asm