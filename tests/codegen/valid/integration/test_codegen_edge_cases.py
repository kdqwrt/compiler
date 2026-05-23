from pathlib import Path
import subprocess

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


def compile_source_to_asm(source: str, use_register_allocation: bool = False) -> str:
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


def run_full_pipeline(tmp_path: Path, source: str):
    asm = compile_source_to_asm(source)

    asm_file = tmp_path / "program.asm"
    obj_file = tmp_path / "program.o"
    runtime_obj = tmp_path / "runtime.o"
    exe_file = tmp_path / "program"

    asm_file.write_text(asm, encoding="utf-8")

    subprocess.run(["nasm", "-f", "elf64", str(asm_file), "-o", str(obj_file)], check=True)
    subprocess.run(["nasm", "-f", "elf64", "src/runtime/runtime.asm", "-o", str(runtime_obj)], check=True)
    subprocess.run(["ld", "-o", str(exe_file), str(runtime_obj), str(obj_file)], check=True)

    result = subprocess.run([str(exe_file)], capture_output=True, text=True)
    return result, asm


def test_direct_signed_conditional_jump_is_emitted():
    source = """
    fn main() -> int {
        if (5 > 3) {
            return 1;
        }
        return 0;
    }
    """

    asm = compile_source_to_asm(source)

    assert "cmp eax, 3" in asm
    assert "jle .main_endif" in asm or "jg .main_then" in asm
    assert "setg al" not in asm


def test_float_compare_uses_unsigned_jump_mnemonics():
    source = """
    fn main() -> int {
        if (1.5 < 2.5) {
            return 1;
        }
        return 0;
    }
    """

    asm = compile_source_to_asm(source)

    assert "ucomisd xmm0," in asm
    assert "jae .main_endif" in asm or "jb .main_then" in asm


def test_global_variable_program_executes(tmp_path: Path):
    source = """
    int g = 0;

    fn main() -> int {
        g = 7;
        return g;
    }
    """

    result, asm = run_full_pipeline(tmp_path, source)

    assert "section .data" in asm
    assert "g: dq 0" in asm
    assert "qword [rel g]" in asm or "dword [rel g]" in asm
    assert result.returncode == 7


def test_function_call_with_eight_integer_arguments(tmp_path: Path):
    source = """
    fn sum8(int a, int b, int c, int d, int e, int f, int g, int h) -> int {
        return a + b + c + d + e + f + g + h;
    }

    fn main() -> int {
        return sum8(1, 2, 3, 4, 5, 6, 7, 8);
    }
    """

    result, asm = run_full_pipeline(tmp_path, source)

    assert "push rax" in asm
    assert "add rsp, 16" in asm
    assert "qword [rbp+16]" in asm
    assert "qword [rbp+24]" in asm
    assert result.returncode == 36


def test_register_allocator_places_temporaries_in_registers():
    source = """
    fn main() -> int {
        return 2 + 3 * 4;
    }
    """

    asm = compile_source_to_asm(source, use_register_allocation=True)

    assert "r10d" in asm or "r11d" in asm or "r12d" in asm or "r13d" in asm