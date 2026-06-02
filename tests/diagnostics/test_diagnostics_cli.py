import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        capture_output=True,
        text=True,
    )


def test_semantic_error_text_format(tmp_path):
    source = tmp_path / "error.src"
    source.write_text(
        """
        fn main() -> int {
            int x;
            return x;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli("check", "--input", str(source))

    assert result.returncode == 1
    assert "error[SEMANTIC]" in result.stderr
    assert "may be used before initialization" in result.stderr
    assert "Initialize the variable before reading it." in result.stderr


def test_semantic_error_json_format(tmp_path):
    source = tmp_path / "error.src"
    source.write_text(
        """
        fn main() -> int {
            int x;
            return x;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(
        "check",
        "--input",
        str(source),
        "--error-format",
        "json",
    )

    assert result.returncode == 1
    assert '"level": "error"' in result.stderr
    assert '"category": "SEMANTIC"' in result.stderr
    assert "may be used before initialization" in result.stderr


def test_max_errors_limits_output(tmp_path):
    source = tmp_path / "many_errors.src"
    source.write_text(
        """
        fn main() -> int {
            int a;
            int b;
            return a + b;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli(
        "check",
        "--input",
        str(source),
        "--max-errors",
        "1",
    )

    assert result.returncode == 1
    assert "variable 'a' may be used before initialization" in result.stderr
    assert "variable 'b' may be used before initialization" not in result.stderr
    assert "stopped after 1 errors" in result.stderr


def test_wall_reports_unused_variable(tmp_path):
    source = tmp_path / "warning.src"
    source.write_text(
        """
        fn main() -> int {
            int unused = 5;
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli("check", "--input", str(source), "-Wall")

    assert result.returncode == 0
    assert "warning[UNUSED_VARIABLE]" in result.stderr
    assert "unused variable 'unused'" in result.stderr


def test_werror_turns_warning_into_error(tmp_path):
    source = tmp_path / "warning.src"
    source.write_text(
        """
        fn main() -> int {
            int unused = 5;
            return 0;
        }
        """,
        encoding="utf-8",
    )

    result = run_cli("check", "--input", str(source), "-Wall", "-Werror")

    assert result.returncode == 1
    assert "error[UNUSED_VARIABLE]" in result.stderr
    assert "unused variable 'unused'" in result.stderr