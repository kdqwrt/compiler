from pathlib import Path

from src.cli import run_compile


class Args:
    def __init__(self, input_path: str, output_path: str):
        self.input = input_path
        self.output = output_path


def test_compile_cli_writes_asm(tmp_path: Path):
    source_file = tmp_path / "program.src"
    output_file = tmp_path / "program.asm"

    source_file.write_text(
        """
        fn main() -> int {
            return 5;
        }
        """,
        encoding="utf-8",
    )

    args = Args(str(source_file), str(output_file))
    run_compile(args)

    assert output_file.exists()
    asm = output_file.read_text(encoding="utf-8")

    assert "section .text" in asm
    assert "global main" in asm
    assert "main:" in asm
    assert "mov eax, 5" in asm
    assert "ret" in asm