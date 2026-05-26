from pathlib import Path
import shutil
import subprocess
import pytest

from src.codegen.x86_generator import X86Generator
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def generate_asm(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    if analyzer.get_errors():
        raise AssertionError(analyzer.get_errors())

    program = IRGenerator(analyzer.get_symbol_table()).generate(ast)
    return X86Generator().generate(program)


def run_gcc_program(tmp_path: Path, source: str, input_text: str = "", extra_libs=None):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        pytest.skip("NASM/GCC are required for libc execution test")

    extra_libs = extra_libs or []

    asm = generate_asm(source)

    asm_file = tmp_path / "program.asm"
    obj_file = tmp_path / "program.o"
    exe_file = tmp_path / "program"

    asm_file.write_text(asm, encoding="utf-8")

    subprocess.run(["nasm", "-f", "elf64", str(asm_file), "-o", str(obj_file)], check=True)
    subprocess.run(["gcc", "-no-pie", str(obj_file), *extra_libs, "-o", str(exe_file)], check=True)

    return subprocess.run(
        [str(exe_file)],
        input=input_text,
        capture_output=True,
        text=True,
    )


def test_strlen_executes(tmp_path):
    source = """
    fn main() -> int {
        return strlen("hello");
    }
    """

    result = run_gcc_program(tmp_path, source)

    assert result.returncode == 5


def test_malloc_executes(tmp_path):
    source = """
    fn main() -> int {
        int* p = malloc(4);
        *p = 7;
        return *p;
    }
    """

    result = run_gcc_program(tmp_path, source)

    assert result.returncode == 7


def test_pow_codegen_uses_xmm_registers():
    source = """
    fn main() -> int {
        float x = pow(2.0, 3.0);
        return 0;
    }
    """

    asm = generate_asm(source)

    assert "extern pow" in asm
    assert "movsd xmm0" in asm
    assert "movsd xmm1" in asm
    assert "call pow" in asm


def test_pow_executes(tmp_path):
    source = """
    fn main() -> int {
        float x = pow(2.0, 3.0);
        return 0;
    }
    """

    result = run_gcc_program(tmp_path, source, extra_libs=["-lm"])

    assert result.returncode == 0


def test_free_executes(tmp_path):
    source = """
    fn main() -> int {
        int* p = malloc(4);
        *p = 7;
        free(p);
        return 0;
    }
    """

    result = run_gcc_program(tmp_path, source)

    assert result.returncode == 0