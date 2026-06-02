import shutil
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        capture_output=True,
        text=True,
    )


def test_emit_assembly_mode(tmp_path):
    source = tmp_path / "main.src"
    asm = tmp_path / "main.asm"

    source.write_text(
        """
        fn main() -> int {
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-S", "-o", str(asm))

    assert result.returncode == 0
    assert asm.exists()
    assert "global main" in asm.read_text(encoding="utf-8")


def test_object_file_mode(tmp_path):
    if shutil.which("nasm") is None:
        return

    source = tmp_path / "main.src"
    obj = tmp_path / "main.o"

    source.write_text(
        """
        fn main() -> int {
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-c", "-o", str(obj))

    assert result.returncode == 0
    assert obj.exists()

    file_result = subprocess.run(
        ["file", str(obj)],
        capture_output=True,
        text=True,
    )

    assert "relocatable" in file_result.stdout


def test_executable_mode(tmp_path):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        return

    source = tmp_path / "main.src"
    exe = tmp_path / "main_program"

    source.write_text(
        """
        fn main() -> int {
            printf("ok=%d\\n", 1);
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-o", str(exe))

    assert result.returncode == 0
    assert exe.exists()

    run_result = subprocess.run(
        [str(exe)],
        capture_output=True,
        text=True,
    )

    assert run_result.returncode == 0
    assert "ok=1" in run_result.stdout


def test_link_with_math_library(tmp_path):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        return

    source = tmp_path / "pow.src"
    exe = tmp_path / "pow_program"

    source.write_text(
        """
        fn main() -> int {
            float x = pow(2.0, 3.0);
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-o", str(exe), "-l", "m")

    assert result.returncode == 0
    assert exe.exists()

    run_result = subprocess.run(
        [str(exe)],
        capture_output=True,
        text=True,
    )

    assert run_result.returncode == 0


def test_multiple_source_files_object_mode(tmp_path):
    if shutil.which("nasm") is None:
        return

    first = tmp_path / "first.src"
    second = tmp_path / "second.src"

    first.write_text(
        """
        fn main() -> int {
            return 0;
        }
        """,
        encoding="utf-8",
    )

    second.write_text(
        """
        fn helper() -> int {
            return 1;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(first), str(second), "-c")

    assert result.returncode == 0
    assert (tmp_path / "first.o").exists()
    assert (tmp_path / "second.o").exists()