

import subprocess
import tempfile
import os
import time
import sys
import pytest


def create_temp_file(content, suffix='.src'):
    fd, path = tempfile.mkstemp(suffix=suffix, text=True)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

def safe_unlink(path):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.unlink(path)
            return
        except (PermissionError, OSError):
            time.sleep(0.1)


def test_cli_lex_basic():

    source = "fn main() { int x = 42; }"
    expected_tokens = [
        "1:1 KW_FN \"fn\"",
        "1:4 IDENTIFIER \"main\"",
        "1:8 LPAREN \"(\"",
        "1:9 RPAREN \")\"",
        "1:11 LBRACE \"{\"",
        "1:13 KW_INT \"int\"",
        "1:17 IDENTIFIER \"x\"",
        "1:19 ASSIGN \"=\"",
        "1:21 INT_LITERAL \"42\" 42",
        "1:23 SEMICOLON \";\"",
        "1:25 RBRACE \"}\"",
        "1:26 EOF \"\""
    ]

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "lex", "--input", path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'  # Игнорировать ошибки кодировки
        )

        assert result.returncode == 0
        output_lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        assert len(output_lines) == len(expected_tokens)
        for i, line in enumerate(output_lines):
            assert line == expected_tokens[i]
    finally:
        safe_unlink(path)

def test_cli_lex_with_output():
    source = "int x = 42;"

    in_path = create_temp_file(source)
    out_fd, out_path = tempfile.mkstemp(suffix='.txt', text=True)
    os.close(out_fd)

    try:
        result = subprocess.run(
            ["compiler", "lex", "--input", in_path, "--output", out_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout == ""

        # Проверяем содержимое выходного файла
        if os.path.exists(out_path):
            with open(out_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                assert "INT_LITERAL" in content
    finally:
        safe_unlink(in_path)
        safe_unlink(out_path)

def test_cli_lex_quiet():
    source = "int x = 42;"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "lex", "--input", path, "--quiet"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout == ""
    finally:
        safe_unlink(path)


def test_cli_lex_fail_fast():
    source = "@ & |"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "lex", "--input", path, "--fail-fast"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'  # Меняем с 'replace' на 'ignore'
        )

        assert result.returncode == 1


        stderr_lower = result.stderr.lower() if result.stderr else ""
        assert any(word in stderr_lower for word in ["символ", "unknown", "invalid", "@"])


        assert len(result.stderr or "") > 0
    finally:
        safe_unlink(path)

def test_cli_lex_file_not_found():
    result = subprocess.run(
        ["compiler", "lex", "--input", "nonexistent.src"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    assert result.returncode != 0
    if result.stderr:
        assert "No such file" in result.stderr or "not found" in result.stderr


def test_cli_preprocess_basic():
    source = "#define MAX 100\nint x = MAX; // комментарий\n"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "preprocess", "--input", path, "--show"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout is not None
        assert "MAX" not in result.stdout
        assert "100" in result.stdout
        assert "//" not in result.stdout
    finally:
        safe_unlink(path)

def test_cli_preprocess_with_defines():
    source = "int x = VERSION;\n#ifdef DEBUG\nint y = 42;\n#endif\n"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "preprocess", "--input", path, "--defines", "DEBUG", "VERSION=100", "--show"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout is not None
        assert "VERSION" not in result.stdout
        assert "100" in result.stdout
        assert "int y = 42" in result.stdout
    finally:
        safe_unlink(path)

def test_cli_preprocess_output_file():
    source = "int x = 42; // comment"

    in_path = create_temp_file(source)
    out_fd, out_path = tempfile.mkstemp(suffix='.txt', text=True)
    os.close(out_fd)

    try:
        result = subprocess.run(
            ["compiler", "preprocess", "--input", in_path, "--output", out_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0

        if os.path.exists(out_path):
            with open(out_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                assert "//" not in content
                assert "42" in content
    finally:
        safe_unlink(in_path)
        safe_unlink(out_path)


def test_cli_full_pipeline():
    source = "#define MAX 100\nint x = MAX; // test\n"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "full", "--input", path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout is not None
        assert "KW_INT" in result.stdout
        assert "INT_LITERAL" in result.stdout
        assert "MAX" not in result.stdout
    finally:
        safe_unlink(path)

def test_cli_full_with_defines():
    source = "#ifdef DEBUG\nint x = 42;\n#endif\n"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "full", "--input", path, "--defines", "DEBUG"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout is not None
        assert "KW_INT" in result.stdout
        assert "x" in result.stdout
    finally:
        safe_unlink(path)



def test_cli_check_valid():
    source = "fn main() { int x = 42; }"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "check", "--input", path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        assert result.returncode == 0
        assert result.stdout is not None
        assert "No lexical errors" in result.stdout
    finally:
        safe_unlink(path)


def test_cli_check_invalid():
    source = "int x = @42;"

    path = create_temp_file(source)
    try:
        result = subprocess.run(
            ["compiler", "check", "--input", path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )

        assert result.returncode == 1
        assert result.stdout is not None
        assert "Syntax check failed" in result.stdout

        # Проверяем наличие ошибки
        if result.stderr:
            stderr_lower = result.stderr.lower()
            assert any(word in stderr_lower for word in ["символ", "unknown", "invalid", "@"])
    finally:
        safe_unlink(path)



def test_cli_info():
    result = subprocess.run(
        ["compiler", "info"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    assert result.returncode == 0
    assert result.stdout is not None
    assert "MiniCompiler" in result.stdout
    assert "Version:" in result.stdout
    assert "Sprint: 1" in result.stdout

@pytest.mark.skipif(sys.platform == 'win32', reason="Проблемы с кодировкой в Windows")
def test_cli_spec():
    result = subprocess.run(
        ["compiler", "spec"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    assert result.returncode == 0
    assert result.stdout is not None
    assert "# Спецификация языка" in result.stdout