import shutil
import subprocess
import sys


def compile_and_run(tmp_path, source_text: str, optimize: bool):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        return None

    suffix = "opt" if optimize else "raw"

    source = tmp_path / f"program_{suffix}.src"
    asm = tmp_path / f"program_{suffix}.asm"
    obj = tmp_path / f"program_{suffix}.o"
    exe = tmp_path / f"program_{suffix}"

    source.write_text(source_text, encoding="utf-8")

    cmd = [sys.executable, "-m", "src.cli", str(source), "-S", "-o", str(asm)]
    if optimize:
        cmd.insert(-2, "--optimize")

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    subprocess.run(["nasm", "-f", "elf64", str(asm), "-o", str(obj)], check=True)
    subprocess.run(["gcc", "-no-pie", str(obj), "-o", str(exe)], check=True)

    return subprocess.run([str(exe)], capture_output=True, text=True)


def test_optimization_preserves_program_output(tmp_path):
    source = """
    fn main() -> int {
        int x = 2 + 3 * 4;
        int y = x + 1;
        printf("result=%d\\n", y);
        return 0;
    }
    """

    raw = compile_and_run(tmp_path, source, optimize=False)
    opt = compile_and_run(tmp_path, source, optimize=True)

    if raw is None or opt is None:
        return

    assert raw.returncode == opt.returncode
    assert raw.stdout == opt.stdout