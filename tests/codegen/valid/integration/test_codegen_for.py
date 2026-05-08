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


def test_codegen_for_loop():
    source = """
    fn main() -> int {
        int i = 0;
        for (i = 0; i < 3; i = i + 1) {
            i = i + 1;
        }
        return i;
    }
    """

    asm = generate_asm(source)

    assert ".main_for_cond" in asm
    assert ".main_for_body" in asm
    assert ".main_for_exit" in asm
    assert "cmp rax," in asm
    assert "je .main_for_exit" in asm or "jne .main_for_body" in asm
    assert "jmp .main_for_cond" in asm
    assert "ret" in asm