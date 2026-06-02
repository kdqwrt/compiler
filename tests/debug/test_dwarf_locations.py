import shutil
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        capture_output=True,
        text=True,
    )


def test_assembly_contains_nasm_line_directives(tmp_path):
    source = tmp_path / "main.src"
    asm = tmp_path / "main.asm"

    source.write_text(
        """
        fn main() -> int {
            int x = 5;
            return x;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(str(source), "-S", "-o", str(asm))

    assert result.returncode == 0, result.stderr
    assert asm.exists()

    content = asm.read_text(encoding="utf-8")

    assert "%line" in content


def test_object_contains_dwarf_debug_line_section(tmp_path):
    if shutil.which("nasm") is None or shutil.which("readelf") is None:
        return

    source = tmp_path / "main.src"
    obj = tmp_path / "main.o"

    source.write_text(
        """
        fn main() -> int {
            int x = 5;
            return x;
        }
        """,
        encoding="utf-8",
    )

    compile_result = run_cli(str(source), "-c", "-o", str(obj))

    assert compile_result.returncode == 0, compile_result.stderr
    assert obj.exists()

    readelf_result = subprocess.run(
        ["readelf", "--debug-dump=decodedline", str(obj)],
        capture_output=True,
        text=True,
    )

    assert readelf_result.returncode == 0
    assert "Contents of the .debug_line section" in readelf_result.stdout