import os
from pathlib import Path

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def generate_ir_from_source(source: str):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    ir_gen = IRGenerator(analyzer.symbol_table)
    return ir_gen.generate(ast)


def generate_ir_text_from_file(src_path: Path) -> str:
    source = src_path.read_text(encoding="utf-8")
    program = generate_ir_from_source(source)
    return program.to_text().strip()


def should_update_golden() -> bool:
    return os.getenv("UPDATE_GOLDEN") == "1"


def assert_golden_ir(src_path: Path, expected_path: Path):
    actual = generate_ir_text_from_file(src_path)

    if should_update_golden():
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(actual + "\n", encoding="utf-8")
        return

    assert expected_path.exists(), (
        f"Expected file not found: {expected_path}\n"
        f"Run with UPDATE_GOLDEN=1 to create/update it."
    )

    expected = expected_path.read_text(encoding="utf-8").strip()
    assert actual == expected, f"Golden IR mismatch for {src_path.name}"