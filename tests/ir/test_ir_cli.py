import subprocess
import sys
from pathlib import Path


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_ir_text(tmp_path: Path):
    source_file = tmp_path / "simple.src"
    source_file.write_text(
        """
fn main() -> int {
    int x = 5;
    x = x + 2;
    return x;
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli("ir", "--input", str(source_file))

    assert result.returncode == 0
    assert "function main" in result.stdout
    assert "ALLOCA" in result.stdout
    assert "LOAD" in result.stdout
    assert "ADD" in result.stdout
    assert "STORE" in result.stdout
    assert "RETURN" in result.stdout


def test_cli_ir_output_file(tmp_path: Path):
    source_file = tmp_path / "simple.src"
    output_file = tmp_path / "simple.ir"

    source_file.write_text(
        """
fn main() -> int {
    return 2 + 3;
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli("ir", "--input", str(source_file), "--output", str(output_file))

    assert result.returncode == 0
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "function main" in content
    assert "ADD" in content
    assert "RETURN" in content


def test_cli_ir_dot_output(tmp_path: Path):
    source_file = tmp_path / "if_test.src"
    output_file = tmp_path / "cfg.dot"

    source_file.write_text(
        """
fn main() -> int {
    int x = 5;
    if (x > 3) {
        return 1;
    } else {
        return 2;
    }
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "ir",
        "--input",
        str(source_file),
        "--format",
        "dot",
        "--output",
        str(output_file),
    )

    assert result.returncode == 0
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "digraph CFG" in content
    assert "entry" in content
    assert "JUMP_IF" in content


def test_cli_ir_json_output(tmp_path: Path):
    source_file = tmp_path / "json_test.src"
    output_file = tmp_path / "ir.json"

    source_file.write_text(
        """
fn main() -> int {
    return 10;
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "ir",
        "--input",
        str(source_file),
        "--format",
        "json",
        "--output",
        str(output_file),
    )

    assert result.returncode == 0
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert '"functions"' in content
    assert '"name": "main"' in content