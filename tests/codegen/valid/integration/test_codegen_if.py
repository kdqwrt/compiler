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


def test_codegen_if_else():
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

    asm = generate_asm(source)

    assert "cmp rax, 2" in asm or "cmp rax, qword" in asm
    assert "setl al" in asm
    assert "je .main_else" in asm or "je .main_else3" in asm
    assert "jmp .main_then" in asm or "jmp .main_then1" in asm
    assert ".main_then" in asm or ".main_then1" in asm
    assert ".main_else" in asm or ".main_else3" in asm
    assert "ret" in asm