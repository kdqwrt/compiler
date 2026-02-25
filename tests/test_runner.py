import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.lexer.scanner import Scanner


VALID_DIR = ROOT / "tests" / "lexer" / "valid"
INVALID_DIR = ROOT / "tests" / "lexer" / "invalid"


def collect_tokens(scanner):
    tokens = []
    while True:
        t = scanner.next_token()
        tokens.append(str(t))
        if t.type.name == "EOF":
            break
    return "\n".join(tokens)


def run_test(src_path, expect_errors=False):
    expected_path = src_path.with_suffix(".expected")

    # Убираем завершающий перевод строки, чтобы EOF был на той же строке, что и последний токен (как в .expected)
    source = src_path.read_text(encoding="utf-8").rstrip("\n\r")
    expected = expected_path.read_text(encoding="utf-8").strip()

    scanner = Scanner(source)
    actual = collect_tokens(scanner).strip()

    success = True

    if actual != expected:
        print(f"\n[FAIL] {src_path.name} (token mismatch)")
        print("----- EXPECTED -----")
        print(expected)
        print("----- ACTUAL -------")
        print(actual)
        success = False

    errors = scanner.get_errors()

    if expect_errors and not errors:
        print(f"\n[FAIL] {src_path.name} (expected errors, got none)")
        success = False

    if not expect_errors and errors:
        print(f"\n[FAIL] {src_path.name} (unexpected errors)")
        print("\n".join(errors))
        success = False

    if success:
        print(f"[OK] {src_path.name}")

    return success


def run_directory(path, expect_errors):
    results = []
    for file in sorted(path.glob("*.src")):
        results.append(run_test(file, expect_errors))
    return results


def main():
    print("=== VALID TESTS ===")
    valid = run_directory(VALID_DIR, expect_errors=False)

    print("\n=== INVALID TESTS ===")
    invalid = run_directory(INVALID_DIR, expect_errors=True)

    total = len(valid) + len(invalid)
    passed = sum(valid) + sum(invalid)

    print(f"\nRESULT: {passed}/{total} tests passed")

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
