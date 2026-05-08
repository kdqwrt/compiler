from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


ROOT_DIR = Path(__file__).resolve().parents[4]
RUNTIME_PATH = ROOT_DIR / "src" / "runtime" / "runtime.asm"


def compile_source_to_asm(source: str) -> str:
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


def run_full_pipeline(tmp_path: Path, source: str):
    asm = compile_source_to_asm(source)

    asm_path = tmp_path / "program.asm"
    obj_path = tmp_path / "program.o"
    runtime_obj_path = tmp_path / "runtime.o"
    exe_path = tmp_path / "program"

    asm_path.write_text(asm, encoding="utf-8")

    subprocess.run(
        ["nasm", "-f", "elf64", str(asm_path), "-o", str(obj_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        ["nasm", "-f", "elf64", str(RUNTIME_PATH), "-o", str(runtime_obj_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        ["ld", "-o", str(exe_path), str(runtime_obj_path), str(obj_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    return subprocess.run([str(exe_path)], capture_output=True, text=True), asm


pytestmark = pytest.mark.skipif(
    shutil.which("nasm") is None or shutil.which("ld") is None,
    reason="NASM and ld are required for ABI stack argument tests",
)


def test_function_call_with_seven_integer_arguments(tmp_path: Path):
    source = """
    fn sum7(int a, int b, int c, int d, int e, int f, int g) -> int {
        return a + b + c + d + e + f + g;
    }

    fn main() -> int {
        return sum7(1, 2, 3, 4, 5, 6, 7);
    }
    """

    result, asm = run_full_pipeline(tmp_path, source)

    assert "push rax" in asm
    assert "add rsp, 8" in asm
    assert "qword [rbp+16]" in asm
    assert result.returncode == 28