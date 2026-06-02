from pathlib import Path
import shutil
import subprocess

import pytest

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


def generate_asm(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    if analyzer.get_errors():
        raise AssertionError("\n".join(str(e) for e in analyzer.get_errors()))

    ir_generator = IRGenerator(analyzer.get_symbol_table())
    ir = ir_generator.generate(ast)

    return X86Generator().generate(ir)


def run_program(tmp_path: Path, source: str):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        pytest.skip("NASM/GCC are required for execution test")

    asm = generate_asm(source)

    asm_file = tmp_path / "program.asm"
    obj_file = tmp_path / "program.o"
    runtime_obj = tmp_path / "runtime.o"
    exe_file = tmp_path / "program"

    asm_file.write_text(asm, encoding="utf-8")

    subprocess.run(["nasm", "-f", "elf64", str(asm_file), "-o", str(obj_file)], check=True)
    subprocess.run(["nasm", "-f", "elf64", "src/runtime/runtime.asm", "-o", str(runtime_obj)], check=True)
    subprocess.run(
        [
            "gcc",
            "-no-pie",
            "-nostartfiles",
            str(runtime_obj),
            str(obj_file),
            "-o",
            str(exe_file),
        ],
        check=True,
    )

    return subprocess.run([str(exe_file)])


def test_local_array_generates_gep_load_store():
    source = """
    fn main() -> int {
        int arr[3];
        arr[0] = 5;
        return arr[0];
    }
    """

    asm = generate_asm(source)

    assert "call malloc" in asm
    assert "mov r11, qword [rbp-" in asm
    assert "add r11, r10" in asm
    assert "mov dword [r11], 5" in asm
    assert "mov eax, dword [r11]" in asm


def test_local_array_literal_indices_execute(tmp_path):
    source = """
    fn main() -> int {
        int arr[3];

        arr[0] = 5;
        arr[1] = 7;
        arr[2] = arr[0] + arr[1];

        return arr[2];
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 12


def test_local_array_variable_index_executes(tmp_path):
    source = """
    fn main() -> int {
        int arr[3];
        int i = 1;

        arr[i] = 9;

        return arr[i];
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 9


def test_local_array_in_loop_executes(tmp_path):
    source = """
    fn main() -> int {
        int arr[3];
        int i = 0;
        int sum = 0;

        while (i < 3) {
            arr[i] = i + 1;
            sum = sum + arr[i];
            i = i + 1;
        }

        return sum;
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 6



def test_array_runtime_bounds_check_returns_255(tmp_path):
    source = """
    fn main() -> int {
        int arr[3];
        int i = 5;
        arr[i] = 10;
        return 1;
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 255


def test_array_parameter_executes(tmp_path):
    source = """
    fn sum(int arr[3]) -> int {
        return arr[0] + arr[1] + arr[2];
    }

    fn main() -> int {
        int a[3];

        a[0] = 1;
        a[1] = 2;
        a[2] = 3;

        return sum(a);
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 6

def test_multidimensional_local_array_executes(tmp_path):
    source = """
    fn main() -> int {
        int m[2][3];

        m[1][2] = 9;

        return m[1][2];
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 9


def test_array_copy_executes(tmp_path):
    source = """
    fn main() -> int {
        int a[3];
        int b[3];

        a[0] = 1;
        a[1] = 2;
        a[2] = 3;

        b = a;

        return b[0] + b[1] + b[2];
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 6


def test_array_copy_generates_memcpy():
    source = """
    fn main() -> int {
        int a[3];
        int b[3];

        b = a;

        return 0;
    }
    """

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    if analyzer.get_errors():
        raise AssertionError("\\n".join(str(e) for e in analyzer.get_errors()))

    ir_generator = IRGenerator(analyzer.get_symbol_table())
    ir = ir_generator.generate(ast)

    ir_text = str(ir)

    assert "MEMCPY" in ir_text