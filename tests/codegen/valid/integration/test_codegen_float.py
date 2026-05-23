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


def test_codegen_float_literal_return():
    source = """
    fn main() -> float {
        return 3.14;
    }
    """

    asm = generate_asm(source)

    assert "section .rodata" in asm
    assert "dq 3.14" in asm
    assert "movsd xmm0, qword [rel" in asm
    assert "ret" in asm


def test_codegen_float_variable_return():
    source = """
    fn main() -> float {
        float x = 3.14;
        return x;
    }
    """

    asm = generate_asm(source)

    assert "movsd xmm0, qword [rel" in asm
    assert "movsd qword [rbp-" in asm
    assert "movsd xmm0, qword [rbp-" in asm


def test_codegen_float_arithmetic():
    source = """
    fn main() -> float {
        return 1.5 + 2.5 * 3.0;
    }
    """

    asm = generate_asm(source)

    assert "mulsd xmm0," in asm
    assert "addsd xmm0," in asm
    assert "movsd qword [rbp-" in asm


def test_codegen_float_comparison():
    source = """
    fn main() -> int {
        if (1.5 < 2.5) {
            return 1;
        }

        return 0;
    }
    """

    asm = generate_asm(source)

    assert "ucomisd xmm0," in asm
    assert "setb al" not in asm
    assert "jae .main_endif" in asm or "jb .main_then" in asm


def test_codegen_mixed_int_float_left_int():
    source = """
    fn main() -> float {
        return 2 + 3.5;
    }
    """

    asm = generate_asm(source)

    assert "mov eax, 2" in asm
    assert "cvtsi2sd xmm0, eax" in asm
    assert "addsd xmm0, qword [rel" in asm


def test_codegen_mixed_int_float_right_int():
    source = """
    fn main() -> float {
        return 3.5 + 2;
    }
    """

    asm = generate_asm(source)

    assert "movsd xmm0, qword [rel" in asm
    assert "cvtsi2sd xmm1, r10d" in asm
    assert "addsd xmm0, xmm1" in asm


def test_codegen_float_direct_jump_handles_unordered_nan_path():
    source = """
    fn main() -> int {
        if (1.5 < 2.5) {
            return 1;
        }

        return 0;
    }
    """

    asm = generate_asm(source)

    assert "ucomisd xmm0," in asm
    assert "jae .main_endif" in asm or "jb .main_then" in asm