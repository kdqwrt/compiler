from pathlib import Path
import subprocess
import sys


ROOT = Path("tests/golden")
INPUTS = ROOT / "inputs"
EXPECTED = ROOT / "expected"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        capture_output=True,
        text=True,
    )


def normalize_text(text: str) -> str:
    return (
        text
        .replace("\r\n", "\n")
        .replace("\\", "/")
        .strip()
    )


def test_golden_ir_snapshot():
    result = run_cli(
        str(INPUTS / "ir_basic.src"),
        "--ir",
        "--optimize",
    )

    assert result.returncode == 0
    actual = normalize_text(result.stdout)
    expected = normalize_text((EXPECTED / "ir_basic.ir").read_text(encoding="utf-8"))

    assert actual == expected


def test_golden_semantic_error_snapshot():
    result = run_cli(
        "check",
        "--input",
        str(INPUTS / "semantic_error.src"),
        "--error-format",
        "text",
    )

    assert result.returncode == 1
    actual = normalize_text(result.stderr)
    expected = normalize_text((EXPECTED / "semantic_error.txt").read_text(encoding="utf-8"))

    assert actual == expected


def test_golden_asm_debug_snapshot(tmp_path):
    asm = tmp_path / "asm_debug.asm"

    result = run_cli(
        str(INPUTS / "asm_debug.src"),
        "-S",
        "-o",
        str(asm),
    )

    assert result.returncode == 0

    actual = normalize_text(asm.read_text(encoding="utf-8"))
    expected = normalize_text((EXPECTED / "asm_debug.asm").read_text(encoding="utf-8"))

    assert actual == expected