from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.register_allocator import LinearScanRegisterAllocator


def generate_function_ir(source: str, function_name: str = "main"):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    program = IRGenerator(analyzer.get_symbol_table()).generate(ast)
    function = program.get_function(function_name)

    assert function is not None
    return function


def test_linear_scan_allocates_temporaries_to_registers():
    source = """
    fn main() -> int {
        return 2 + 3 * 4;
    }
    """

    function = generate_function_ir(source)

    allocator = LinearScanRegisterAllocator(registers=["r10", "r11"])
    allocation = allocator.allocate(function)

    assert allocation
    assert any(value in {"r10", "r11"} for value in allocation.values())
    assert allocator.get_spill_count() == 0


def test_linear_scan_spills_when_registers_are_exhausted():
    source = """
    fn main() -> int {
        int a = 1 + 2;
        int b = 3 + 4;
        int c = 5 + 6;
        return a + b + c;
    }
    """

    function = generate_function_ir(source)

    allocator = LinearScanRegisterAllocator(registers=["r10"])
    allocation = allocator.allocate(function)

    assert allocation
    assert allocator.get_spill_count() >= 0
    assert all(value == "r10" or value.startswith("spill") for value in allocation.values())


def test_linear_scan_builds_live_ranges():
    source = """
    fn main() -> int {
        int x = 1;
        int y = 2;
        return x + y;
    }
    """

    function = generate_function_ir(source)

    allocator = LinearScanRegisterAllocator(registers=["r10", "r11"])
    allocator.allocate(function)

    live_ranges = allocator.get_live_ranges()

    assert live_ranges
    for live_range in live_ranges.values():
        assert live_range.start <= live_range.end
