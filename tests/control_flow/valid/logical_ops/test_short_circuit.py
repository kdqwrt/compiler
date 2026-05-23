from pathlib import Path
import subprocess

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


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

    asm_file = tmp_path / "program.asm"
    obj_file = tmp_path / "program.o"
    runtime_obj = tmp_path / "runtime.o"
    exe_file = tmp_path / "program"

    asm_file.write_text(asm, encoding="utf-8")

    subprocess.run(
        ["nasm", "-f", "elf64", str(asm_file), "-o", str(obj_file)],
        check=True,
    )

    subprocess.run(
        ["nasm", "-f", "elf64", "src/runtime/runtime.asm", "-o", str(runtime_obj)],
        check=True,
    )

    subprocess.run(
        ["ld", "-o", str(exe_file), str(runtime_obj), str(obj_file)],
        check=True,
    )

    result = subprocess.run([str(exe_file)], capture_output=True, text=True)
    return result, asm


def test_and_short_circuit_skips_division_by_zero(tmp_path: Path):
    source = """
    fn main() -> int {
        int a = 0;
        int b = 10;

        if (a != 0 && b / a > 2) {
            return 1;
        }

        return 0;
    }
    """

    result, asm = run_full_pipeline(tmp_path, source)

    assert result.returncode == 0
    assert ".main_and_rhs" in asm
    assert ".main_and_rhs" in asm
    assert "idiv" in asm
    assert "mov r10b, 1" not in asm
    assert "mov r10b, 0" not in asm
    assert "and al," not in asm


def test_or_short_circuit_skips_division_by_zero(tmp_path: Path):
    source = """
    fn main() -> int {
        int a = 0;
        int b = 10;

        if (a == 0 || b / a > 2) {
            return 7;
        }

        return 1;
    }
    """

    result, asm = run_full_pipeline(tmp_path, source)

    assert result.returncode == 7
    assert ".main_or_rhs" in asm
    assert ".main_or_rhs" in asm
    assert "idiv" in asm
    assert "mov r10b, 1" not in asm
    assert "mov r10b, 0" not in asm
    assert "or al," not in asm