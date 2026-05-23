from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer


def analyze_source(source: str):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    return analyzer.get_errors()


def test_if_condition_rejects_invalid_type():
    source = """
    fn main() -> int {
        if ("hello") {
            return 1;
        }

        return 0;
    }
    """

    errors = analyze_source(source)

    assert errors != []


def test_while_condition_rejects_invalid_type():
    source = """
    fn main() -> int {
        while ("hello") {
            return 1;
        }

        return 0;
    }
    """

    errors = analyze_source(source)

    assert errors != []