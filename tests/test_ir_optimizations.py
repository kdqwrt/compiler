from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.optimization.constant_propagation import ConstantPropagationPass
from src.optimization.constant_folding import ConstantFoldingPass
from src.optimization.dead_code_elimination import DeadCodeEliminationPass
from src.optimization.dead_store_elimination import DeadStoreEliminationPass


def optimize_ir(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)

    if analyzer.get_errors():
        raise AssertionError(analyzer.get_errors())

    program = IRGenerator(analyzer.get_symbol_table()).generate(ast)

    program = ConstantPropagationPass().run(program)
    program = ConstantFoldingPass().run(program)
    program = DeadCodeEliminationPass().run(program)
    program = DeadStoreEliminationPass().run(program)

    return program.to_text()


def test_constant_folding():
    source = """
    fn main() -> int {
        return 2 + 3 * 4;
    }
    """

    ir = optimize_ir(source)

    assert "RETURN 14" in ir


def test_constant_propagation():
    source = """
    fn main() -> int {
        int a = 5;
        return a + 2;
    }
    """

    ir = optimize_ir(source)

    assert "RETURN 7" in ir


def test_dead_code_elimination():
    source = """
    fn main() -> int {
        return 1;
        int x = 5;
    }
    """

    ir = optimize_ir(source)

    assert "RETURN 1" in ir
    assert "STORE x, 5" not in ir


def test_dead_store_elimination():
    source = """
    fn main() -> int {
        int x = 1;
        x = 2;
        return x;
    }
    """

    ir = optimize_ir(source)

    assert "RETURN 2" in ir
    assert "STORE x, 1" not in ir