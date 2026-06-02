import subprocess
import sys
from pathlib import Path


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        capture_output=True,
        text=True,
    )


def test_unix_cli_version():
    result = run_cli("--version")

    assert result.returncode == 0
    assert "MiniCompiler" in result.stdout


def test_unix_cli_ast(tmp_path):
    source = tmp_path / "main.src"
    source.write_text(
        """
        fn main() -> int {
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "--ast")

    assert result.returncode == 0
    assert "FunctionDecl: main" in result.stdout


def test_unix_cli_ir(tmp_path):
    source = tmp_path / "main.src"
    source.write_text(
        """
        fn main() -> int {
            return 2 + 3;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "--ir")

    assert result.returncode == 0
    assert "function main" in result.stdout
    assert "ADD" in result.stdout


def test_unix_cli_ir_optimize(tmp_path):
    source = tmp_path / "main.src"
    source.write_text(
        """
        fn main() -> int {
            return 2 + 3;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "--ir", "--optimize")

    assert result.returncode == 0
    assert "RETURN 5" in result.stdout


def test_unix_cli_emit_assembly_to_file(tmp_path):
    source = tmp_path / "main.src"
    output = tmp_path / "main.asm"

    source.write_text(
        """
        fn main() -> int {
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-S", "-o", str(output))

    assert result.returncode == 0
    assert output.exists()
    assert "global main" in output.read_text(encoding="utf-8")


def test_unix_cli_o2_emit_assembly_to_file(tmp_path):
    source = tmp_path / "main.src"
    output = tmp_path / "main.asm"

    source.write_text(
        """
        fn main() -> int {
            return 2 + 3;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-O2", "-S", "-o", str(output))

    assert result.returncode == 0
    assert output.exists()
    assert "mov eax, 5" in output.read_text(encoding="utf-8")


def test_legacy_compile_command_still_works(tmp_path):
    source = tmp_path / "main.src"
    output = tmp_path / "main.asm"

    source.write_text(
        """
        fn main() -> int {
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli("compile", "--input", str(source), "--output", str(output))

    assert result.returncode == 0
    assert output.exists()
    assert "global main" in output.read_text(encoding="utf-8")