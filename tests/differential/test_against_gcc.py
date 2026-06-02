import shutil
import subprocess
import sys


def run_cmd(cmd):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )


def compile_mycc(tmp_path, source_text: str):
    src = tmp_path / "program.src"
    exe = tmp_path / "program_mycc"

    src.write_text(source_text, encoding="utf-8")

    result = run_cmd(
        [
            sys.executable,
            "-m",
            "src.cli",
            str(src),
            "-o",
            str(exe),
        ]
    )

    assert result.returncode == 0, result.stderr

    run = run_cmd([str(exe)])
    return run


def compile_gcc(tmp_path, c_text: str):
    c_file = tmp_path / "program.c"
    exe = tmp_path / "program_gcc"

    c_file.write_text(c_text, encoding="utf-8")

    result = run_cmd(
        [
            "gcc",
            "-O0",
            "-no-pie",
            str(c_file),
            "-o",
            str(exe),
        ]
    )

    assert result.returncode == 0, result.stderr

    run = run_cmd([str(exe)])
    return run


def test_arithmetic_output_matches_gcc(tmp_path):
    if shutil.which("gcc") is None or shutil.which("nasm") is None:
        return

    mycc_source = """
    fn main() -> int {
        int x = 2 + 3 * 4;
        printf("result=%d\\n", x);
        return 0;
    }
    """

    gcc_source = """
    #include <stdio.h>

    int main(void) {
        int x = 2 + 3 * 4;
        printf("result=%d\\n", x);
        return 0;
    }
    """

    mycc_run = compile_mycc(tmp_path, mycc_source)
    gcc_run = compile_gcc(tmp_path, gcc_source)

    assert mycc_run.returncode == gcc_run.returncode
    assert mycc_run.stdout == gcc_run.stdout


def test_loop_output_matches_gcc(tmp_path):
    if shutil.which("gcc") is None or shutil.which("nasm") is None:
        return

    mycc_source = """
    fn main() -> int {
        int i = 0;
        int sum = 0;

        while (i < 5) {
            sum = sum + i;
            i = i + 1;
        }

        printf("sum=%d\\n", sum);
        return 0;
    }
    """

    gcc_source = """
    #include <stdio.h>

    int main(void) {
        int i = 0;
        int sum = 0;

        while (i < 5) {
            sum = sum + i;
            i = i + 1;
        }

        printf("sum=%d\\n", sum);
        return 0;
    }
    """

    mycc_run = compile_mycc(tmp_path, mycc_source)
    gcc_run = compile_gcc(tmp_path, gcc_source)

    assert mycc_run.returncode == gcc_run.returncode
    assert mycc_run.stdout == gcc_run.stdout


def test_recursion_output_matches_gcc(tmp_path):
    if shutil.which("gcc") is None or shutil.which("nasm") is None:
        return

    mycc_source = """
    fn fact(int n) -> int {
        if (n <= 1) {
            return 1;
        }

        return n * fact(n - 1);
    }

    fn main() -> int {
        int result = fact(5);
        printf("fact=%d\\n", result);
        return 0;
    }
    """

    gcc_source = """
    #include <stdio.h>

    int fact(int n) {
        if (n <= 1) {
            return 1;
        }

        return n * fact(n - 1);
    }

    int main(void) {
        int result = fact(5);
        printf("fact=%d\\n", result);
        return 0;
    }
    """

    mycc_run = compile_mycc(tmp_path, mycc_source)
    gcc_run = compile_gcc(tmp_path, gcc_source)

    assert mycc_run.returncode == gcc_run.returncode
    assert mycc_run.stdout == gcc_run.stdout