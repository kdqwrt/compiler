from src.codegen.x86_generator import X86Generator
from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from pathlib import Path
import shutil
import subprocess
import pytest

def generate_asm(source: str):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    if analyzer.get_errors():
        raise AssertionError(analyzer.get_errors())

    ir = IRGenerator(analyzer.get_symbol_table()).generate(ast)
    return X86Generator().generate(ir)


def test_printf_declared_as_extern():
    source = """
    fn main() -> int {
        printf("sum=%d", 6);
        return 0;
    }
    """

    asm = generate_asm(source)

    assert "extern printf" in asm
    assert "call printf" in asm

def run_gcc_program(tmp_path: Path, source: str):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        pytest.skip("NASM/GCC are required for printf execution test")

    asm = generate_asm(source)

    asm_file = tmp_path / "program.asm"
    obj_file = tmp_path / "program.o"
    exe_file = tmp_path / "program"

    asm_file.write_text(asm, encoding="utf-8")

    subprocess.run(["nasm", "-f", "elf64", str(asm_file), "-o", str(obj_file)], check=True)
    subprocess.run(["gcc", "-no-pie", str(obj_file), "-o", str(exe_file)], check=True)

    return subprocess.run([str(exe_file)], capture_output=True, text=True)


def test_printf_executes(tmp_path):
    source = """
    fn main() -> int {
        printf("sum=%d\\n", 6);
        return 0;
    }
    """

    result = run_gcc_program(tmp_path, source)

    assert result.returncode == 0
    assert result.stdout == "sum=6\n"