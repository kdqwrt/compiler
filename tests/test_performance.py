import pytest
import time
from src.lexer.scanner import Scanner
from src.parser.parser import Parser


def generate_large_program(n_vars=1000):
    """Генерация большой программы для тестирования производительности"""
    lines = []
    lines.append("fn main() -> int {")

    # Генерируем много переменных
    for i in range(n_vars):
        lines.append(f"    int var{i} = {i};")

    # Генерируем сложное выражение
    expr = " + ".join(f"var{i}" for i in range(min(100, n_vars)))
    lines.append(f"    int result = {expr};")
    lines.append("    return result;")
    lines.append("}")

    return "\n".join(lines)


@pytest.mark.performance
def test_parser_performance():
    """Тест производительности парсера"""
    source = generate_large_program(500)

    start_time = time.time()

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    end_time = time.time()

    elapsed = end_time - start_time
    print(f"\nParsing time for 500 variables: {elapsed:.3f} seconds")

    # Проверяем, что парсинг не слишком медленный
    assert elapsed < 2.0, f"Parsing too slow: {elapsed:.3f}s"


@pytest.mark.performance
def test_parser_memory_usage():
    """Тест использования памяти (приблизительный)"""
    import tracemalloc

    source = generate_large_program(1000)

    tracemalloc.start()
    start_snapshot = tracemalloc.take_snapshot()

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    parser = Parser(tokens)
    ast = parser.parse()

    end_snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Сравниваем использование памяти
    stats = end_snapshot.compare_to(start_snapshot, 'lineno')
    total_memory = sum(stat.size for stat in stats) / 1024  # в KB

    print(f"\nApproximate memory usage: {total_memory:.2f} KB")

    # Проверяем, что память не слишком велика
    assert total_memory < 50000, f"Memory usage too high: {total_memory:.2f} KB"