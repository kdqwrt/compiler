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

    result = subprocess.run(
        [str(exe_path)],
        capture_output=True,
        text=True,
    )

    return result, asm


pytestmark = pytest.mark.skipif(
    shutil.which("nasm") is None or shutil.which("ld") is None,
    reason="NASM and ld are required for execution pipeline tests",
)


@pytest.mark.parametrize(
    ("source", "expected_return_code"),
    [
        (
            """
            fn main() -> int {
                return 2 + 3 * 4;
            }
            """,
            14,
        ),
        (
            """
            fn main() -> int {
                return 10 / 2;
            }
            """,
            5,
        ),
        (
            """
            fn main() -> int {
                return 10 % 3;
            }
            """,
            1,
        ),
        (
            """
            fn add(int a, int b) -> int {
                return a + b;
            }

            fn main() -> int {
                return add(2, 3);
            }
            """,
            5,
        ),
        (
            """
            fn main() -> int {
                int x = 0;
                if (2 < 3) {
                    x = 7;
                } else {
                    x = 9;
                }
                return x;
            }
            """,
            7,
        ),
        (
            """
            fn main() -> int {
                int x = 0;
                while (x < 3) {
                    x = x + 1;
                }
                return x;
            }
            """,
            3,
        ),
    ],
)
def test_execution_pipeline_return_codes(tmp_path: Path, source: str, expected_return_code: int):
    result, asm = run_full_pipeline(tmp_path, source)

    assert "unsupported IR" not in asm
    assert result.returncode == expected_return_code


def test_execution_pipeline_print_int(tmp_path: Path):
    source = """
    fn main() -> int {
        print_int(123);
        return 0;
    }
    """

    result, asm = run_full_pipeline(tmp_path, source)

    assert "unsupported IR" not in asm
    assert result.stdout.strip() == "123"
    assert result.returncode == 0