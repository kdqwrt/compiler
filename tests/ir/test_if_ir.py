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
    program = ir_gen.generate(ast)
    return program


def test_if_else_ir():
    source = """
    fn main() -> int {
        int x = 5;
        if (x > 3) {
            return 1;
        } else {
            return 2;
        }
    }
    """

    program = generate_ir(source)
    text = program.to_text()
    func = program.functions[0]

    assert "CMP_GT" in text
    assert "JUMP_IF" in text
    assert "JUMP" in text
    assert "RETURN" in text

    assert len(func.blocks) >= 4

    labels = [block.label for block in func.blocks]
    assert "entry" in labels
    assert any(label.startswith("then") for label in labels)
    assert any(label.startswith("else") for label in labels)
    assert any(label.startswith("endif") for label in labels)


def test_if_without_else_ir():
    source = """
    fn main() -> int {
        int x = 5;
        if (x > 3) {
            x = x + 1;
        }
        return x;
    }
    """

    program = generate_ir(source)
    text = program.to_text()
    func = program.functions[0]

    assert "CMP_GT" in text
    assert "JUMP_IF" in text
    assert "JUMP" in text
    assert "ADD" in text
    assert "STORE" in text
    assert "RETURN" in text

    labels = [block.label for block in func.blocks]
    assert "entry" in labels
    assert any(label.startswith("then") for label in labels)
    assert any(label.startswith("endif") for label in labels)


def test_if_branch_blocks_have_control_flow():
    source = """
    fn main() -> int {
        int x = 1;
        if (x == 1) {
            x = 2;
        } else {
            x = 3;
        }
        return x;
    }
    """

    program = generate_ir(source)
    func = program.functions[0]

    assert len(func.blocks) >= 4

    entry_block = func.blocks[0]
    assert entry_block.label == "entry"
    assert any(instr.opcode.name in ("JUMP_IF", "JUMP_IF_NOT") for instr in entry_block.instructions)
    assert any(instr.opcode.name == "JUMP" for instr in entry_block.instructions)

    all_labels = {block.label for block in func.blocks}
    for block in func.blocks:
        for succ in block.successors:
            assert succ in all_labels