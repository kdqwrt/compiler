from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.ir.validator import IRValidator


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


def test_validator_accepts_valid_if_else_ir():
    source = """
    fn main() -> int {
        int x = 0;
        if (1 < 2) {
            x = 10;
        } else {
            x = 20;
        }
        return x;
    }
    """

    program = generate_ir(source)
    result = IRValidator(program).validate()

    assert result.is_valid()
    assert result.errors == []


def test_validator_accepts_valid_while_ir():
    source = """
    fn main() -> int {
        int x = 0;
        while (x < 3) {
            x = x + 1;
        }
        return x;
    }
    """

    program = generate_ir(source)
    result = IRValidator(program).validate()

    assert result.is_valid()
    assert result.errors == []


def test_validator_accepts_valid_for_ir():
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
    result = IRValidator(program).validate()

    assert result.is_valid()
    assert result.errors == []


def test_validator_reports_unreachable_block():
    from src.ir.basic_block import IRProgram, IRFunction, BasicBlock
    from src.ir.ir_instructions import IRInstruction, IROpcode, IROperand, IROperandKind

    program = IRProgram()
    func = IRFunction(name="main", return_type="int")

    entry = BasicBlock("entry")
    entry.add_instruction(
        IRInstruction(
            opcode=IROpcode.JUMP,
            args=[IROperand(IROperandKind.LABEL, "exit")],
            comment="jump to exit",
        )
    )

    dead = BasicBlock("dead")
    dead.add_instruction(
        IRInstruction(
            opcode=IROpcode.RETURN,
            args=[IROperand(IROperandKind.LITERAL, 0, type_name="int")],
            comment="dead return",
        )
    )

    exit_block = BasicBlock("exit")
    exit_block.add_instruction(
        IRInstruction(
            opcode=IROpcode.RETURN,
            args=[IROperand(IROperandKind.LITERAL, 1, type_name="int")],
            comment="real return",
        )
    )

    func.add_block(entry)
    func.add_block(dead)
    func.add_block(exit_block)
    func.add_edge("entry", "exit")

    program.add_function(func)

    result = IRValidator(program).validate()

    assert not result.is_valid()
    assert any("unreachable basic block 'dead'" in str(err) for err in result.errors)