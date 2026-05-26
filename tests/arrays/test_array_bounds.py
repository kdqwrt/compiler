from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer


def analyze_source(source: str):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    return analyzer.get_errors()


def test_array_literal_index_inside_bounds_passes():
    source = """
    fn main() -> int {
        int arr[3];
        arr[2] = 5;
        return arr[2];
    }
    """

    errors = analyze_source(source)

    assert errors == []


def test_array_literal_index_equal_size_fails():
    source = """
    fn main() -> int {
        int arr[3];
        arr[3] = 5;
        return 0;
    }
    """

    errors = analyze_source(source)

    assert any("array index out of bounds" in str(error) for error in errors)


def test_array_literal_index_too_large_fails():
    source = """
    fn main() -> int {
        int arr[3];
        return arr[10];
    }
    """

    errors = analyze_source(source)

    assert any("array index out of bounds" in str(error) for error in errors)