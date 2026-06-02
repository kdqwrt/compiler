import shutil
import subprocess
import sys


def test_nested_call_printf_strlen_regression(tmp_path):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        return

    source = tmp_path / "nested.src"
    asm = tmp_path / "nested.asm"
    obj = tmp_path / "nested.o"
    exe = tmp_path / "nested_program"

    source.write_text(
        """
        fn main() -> int {
            printf("len=%d\\n", strlen("hello"));
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "src.cli", str(source), "-S", "-o", str(asm)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    subprocess.run(["nasm", "-f", "elf64", str(asm), "-o", str(obj)], check=True)
    subprocess.run(["gcc", "-no-pie", str(obj), "-o", str(exe)], check=True)

    run = subprocess.run([str(exe)], capture_output=True, text=True)

    assert run.returncode == 0
    assert "len=5" in run.stdout