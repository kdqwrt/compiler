from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def generate_ir_text(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer("<test>")
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    program = IRGenerator(analyzer.get_symbol_table()).generate(ast)
    return program.to_text()


def test_ir_sequence_for_nested_strlen_printf():
    source = """
    fn main() -> int {
        printf("len=%d\\n", strlen("hello"));
        return 0;
    }
    """

    ir = generate_ir_text(source)
    lines = [line.strip() for line in ir.splitlines()]

    expected_order = [
        "PARAM 0, hello",
        "t1 = CALL strlen",
        "PARAM 0, len=%d",
        "PARAM 1, t1",
        "t2 = CALL printf",
        "RETURN 0",
    ]

    current_index = 0

    for expected in expected_order:
        found = False

        while current_index < len(lines):
            if expected in lines[current_index]:
                found = True
                current_index += 1
                break
            current_index += 1

        assert found, f"Expected IR line not found in order: {expected}"


def test_ir_sequence_for_pointer_store_and_load():
    source = """
    fn main() -> int {
        int x = 5;
        int* p = &x;
        *p = 7;
        return *p;
    }
    """

    ir = generate_ir_text(source)
    lines = [line.strip() for line in ir.splitlines()]

    expected_order = [
        "x = ALLOCA 4",
        "STORE x, 5",
        "p = ALLOCA 8",
        "ADDR_OF x",
        "STORE p",
        "LOAD p",
        "STORE [",
        "LOAD p",
        "LOAD [",
        "RETURN",
    ]

    current_index = 0

    for expected in expected_order:
        found = False

        while current_index < len(lines):
            if expected in lines[current_index]:
                found = True
                current_index += 1
                break
            current_index += 1

        assert found, f"Expected IR line not found in order: {expected}"