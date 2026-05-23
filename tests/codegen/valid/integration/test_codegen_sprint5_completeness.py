from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.codegen.x86_generator import X86Generator


def generate_asm(source: str) -> str:
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    assert scanner.get_errors() == []

    parser = Parser(tokens)
    ast = parser.parse()
    assert parser.get_errors() == []

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    assert analyzer.get_errors() == []

    ir_program = IRGenerator(analyzer.get_symbol_table()).generate(ast)
    return X86Generator().generate(ir_program)


def test_codegen_div_mod_and_or_not_instructions():
    div_source = """
    fn main() -> int {
        return 10 / 2;
    }
    """

    mod_source = """
    fn main() -> int {
        return 10 % 3;
    }
    """

    and_source = """
    fn main() -> bool {
        return (5 > 3) && (2 < 10);
    }
    """

    or_source = """
    fn main() -> bool {
        return (5 > 10) || (2 < 10);
    }
    """

    not_source = """
    fn main() -> bool {
        return !(5 > 3);
    }
    """

    div_asm = generate_asm(div_source)
    mod_asm = generate_asm(mod_source)
    and_asm = generate_asm(and_source)
    or_asm = generate_asm(or_source)
    not_asm = generate_asm(not_source)

    assert "idiv r10" in div_asm
    assert "idiv r10" in mod_asm
    assert "mov eax, edx" in mod_asm

    assert "and al," not in and_asm
    assert ".main_and_rhs" in and_asm
    assert ".main_and_false" in and_asm
    assert ".main_and_true" in and_asm
    assert ".main_and_end" in and_asm
    assert "&&" not in and_asm or "short-circuit" in and_asm

    assert "or al," not in or_asm
    assert ".main_or_rhs" in or_asm
    assert ".main_or_false" in or_asm
    assert ".main_or_true" in or_asm
    assert ".main_or_end" in or_asm

    assert "cmp rax, 0" in not_asm
    assert "sete al" in not_asm

    assert "unsupported IR" not in div_asm
    assert "unsupported IR" not in mod_asm
    assert "unsupported IR" not in and_asm
    assert "unsupported IR" not in or_asm
    assert "unsupported IR" not in not_asm


def test_codegen_declares_runtime_externs():
    source = """
    fn main() -> int {
        print_int(123);
        return 0;
    }
    """

    asm = generate_asm(source)

    assert "extern print_int" in asm
    assert "extern print_string" in asm
    assert "extern read_int" in asm
    assert "call print_int" in asm
    assert "unsupported IR" not in asm


def test_codegen_does_not_emit_unsupported_ir_for_common_sprint5_program():
    source = """
    fn add(int a, int b) -> int {
        return a + b;
    }

    fn main() -> int {
        int x = 0;

        if (2 < 3) {
            x = add(2, 5);
        } else {
            x = 9;
        }

        while (x < 10) {
            x = x + 1;
        }

        print_int(x);
        return x;
    }
    """

    asm = generate_asm(source)

    assert "unsupported IR" not in asm
    assert "call add" in asm
    assert "call print_int" in asm
    assert ".main_then" in asm
    assert ".main_else" in asm
    assert ".main_while_cond" in asm
    assert "ret" in asm