import shutil
import subprocess
import sys


def test_black_box_demo_execution(tmp_path):
    if shutil.which("nasm") is None or shutil.which("gcc") is None:
        return

    source = tmp_path / "demo.src"
    asm = tmp_path / "demo.asm"
    obj = tmp_path / "demo.o"
    exe = tmp_path / "demo_program"

    source.write_text(
        """
        fn factorial(int n) -> int {
            if (n <= 1) {
                return 1;
            }

            return n * factorial(n - 1);
        }

        fn main() -> int {
            int arr[3];
            int i = 0;
            int sum = 0;

            arr[0] = 1;
            arr[1] = 2;
            arr[2] = 3;

            while (i < 3) {
                sum = sum + arr[i];
                i = i + 1;
            }

            printf("sum=%d\\n", sum);
            printf("fact=%d\\n", factorial(3));

            return 0;
        }
        """,
        encoding="utf-8",
    )

    compile_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli",
            str(source),
            "-S",
            "-o",
            str(asm),
        ],
        capture_output=True,
        text=True,
    )

    assert compile_result.returncode == 0, compile_result.stderr

    subprocess.run(["nasm", "-f", "elf64", str(asm), "-o", str(obj)], check=True)
    subprocess.run(["gcc", "-no-pie", str(obj), "-o", str(exe)], check=True)

    run_result = subprocess.run(
        [str(exe)],
        capture_output=True,
        text=True,
    )

    assert run_result.returncode == 0
    assert "sum=6" in run_result.stdout
    assert "fact=6" in run_result.stdout