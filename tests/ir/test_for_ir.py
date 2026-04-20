from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator


def generate_ir(source: str):
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


def test_for_ir():
    source = """
    fn main() -> int {
        int x = 0;
        int i = 0;
        for (i = 0; i < 3; i = i + 1) {
            x = x + i;
        }
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()
    func = program.functions[0]

    assert "CMP_LT" in text
    assert "JUMP_IF" in text
    assert "JUMP" in text
    assert "ADD" in text
    assert "STORE" in text
    assert "RETURN" in text

    labels = [block.label for block in func.blocks]
    assert "entry" in labels
    assert any(label.startswith("for_cond") for label in labels)
    assert any(label.startswith("for_body") for label in labels)
    assert any(label.startswith("for_exit") for label in labels)


def test_for_blocks_have_valid_edges():
    source = """
    fn main() -> int {
        int i = 0;
        for (i = 0; i < 2; i = i + 1) {
            i = i + 1;
        }
        return i;
    }
    """

    program = generate_ir(source)
    func = program.functions[0]

    all_labels = {block.label for block in func.blocks}
    for block in func.blocks:
        for succ in block.successors:
            assert succ in all_labels