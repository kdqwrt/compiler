import argparse
import sys
from pathlib import Path

from src.lexer.scanner import Scanner
from src.preprocessor.preprocessor import Preprocessor
from src.preprocessor.macros import MacroProcessor
from src.parser.parser import Parser
from src.parser.ast import generate_dot, pretty_print, ast_to_json
from src.semantic.analyzer import SemanticAnalyzer
from src.ir.ir_generator import IRGenerator
from src.ir.validator import IRValidator
from src.codegen.x86_generator import X86Generator
from src.optimization.constant_folding import ConstantFoldingPass
from src.optimization.constant_propagation import ConstantPropagationPass
from src.optimization.dead_code_elimination import DeadCodeEliminationPass
from src.optimization.dead_store_elimination import DeadStoreEliminationPass


VERSION = "0.3.0"
SPEC_PATH = Path("docs/language_spec.md")


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def print_errors(errors):
    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        return True
    return False


def run_preprocess(args):
    source = read_file(args.input)

    pp = Preprocessor(source)
    cleaned = pp.process()

    mp = MacroProcessor()

    if args.defines:
        for define in args.defines:
            if "=" in define:
                name, value = define.split("=", 1)
            else:
                name, value = define, ""
            mp.define(name, value)

    result = mp.process_directives(cleaned)

    errors = pp.get_errors() + mp.get_errors()

    if args.show:
        print(result)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")

    if print_errors(errors):
        sys.exit(1)


def run_lex(args):
    source = read_file(args.input)

    scanner = Scanner(source)

    tokens = []
    while True:
        token = scanner.next_token()
        tokens.append(str(token))
        if token.type.name == "EOF":
            break

    errors = scanner.get_errors()

    if not args.quiet:
        output = "\n".join(tokens)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            print(output)

    if args.fail_fast and errors:
        print_errors(errors)
        sys.exit(1)

    if not args.quiet:
        print_errors(errors)


def run_parse(args):
    source = read_file(args.input)

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()

    lex_errors = scanner.get_errors()
    if lex_errors:
        print_errors(lex_errors)
        if args.fail_fast:
            sys.exit(1)

    parser = Parser(tokens)
    ast = parser.parse()

    parse_errors = parser.get_errors()
    if parse_errors:
        print_errors(parse_errors)
        if args.fail_fast:
            sys.exit(1)

    output = None
    if args.format == "text":
        from src.parser.visitor import ASTPrettyPrinter
        printer = ASTPrettyPrinter()
        printer.visit(ast)
        output = printer.get_result()
    elif args.format == "dot":
        output = generate_dot(ast)
    elif args.format == "json":
        output = ast_to_json(ast)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        if args.verbose:
            print(f"AST saved to {args.output}", file=sys.stderr)
    else:
        print(output)

    if args.verbose:
        print("\nStatistics:", file=sys.stderr)
        print(f"  Tokens: {len(tokens)}", file=sys.stderr)
        print(f"  Lexical errors: {len(lex_errors)}", file=sys.stderr)
        print(f"  Parse errors: {len(parse_errors)}", file=sys.stderr)
        print(
            f"  AST nodes: {ast.count_nodes() if hasattr(ast, 'count_nodes') else 'N/A'}",
            file=sys.stderr,
        )


def run_full(args):
    source = read_file(args.input)

    pp = Preprocessor(source)
    cleaned = pp.process()

    mp = MacroProcessor()

    if args.defines:
        for define in args.defines:
            if "=" in define:
                name, value = define.split("=", 1)
            else:
                name, value = define, ""
            mp.define(name, value)

    processed = mp.process_directives(cleaned)

    pp_errors = pp.get_errors()
    mp_errors = mp.get_errors()

    if pp_errors or mp_errors:
        print_errors(pp_errors + mp_errors)
        sys.exit(1)

    scanner = Scanner(processed)
    tokens = []

    while True:
        token = scanner.next_token()
        tokens.append(str(token))
        if token.type.name == "EOF":
            break

    errors = scanner.get_errors()

    print("\n".join(tokens))
    if print_errors(errors):
        sys.exit(1)


def run_check(args):
    source = read_file(args.input)

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    lex_errors = scanner.get_errors()

    if lex_errors:
        print("Check failed: lexical errors found.", file=sys.stderr)
        print_errors(lex_errors)
        sys.exit(1)

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()

    if parse_errors:
        print("Check failed: syntax errors found.", file=sys.stderr)
        print_errors(parse_errors)
        sys.exit(1)

    analyzer = SemanticAnalyzer(args.input)
    analyzer.analyze(ast)
    semantic_errors = analyzer.get_errors()

    if semantic_errors:
        print("Check failed: semantic errors found.", file=sys.stderr)
        for error in semantic_errors:
            print(error.format(), file=sys.stderr)
            print(file=sys.stderr)
        sys.exit(1)

    print("Semantic check passed successfully.")

    if getattr(args, "show_types", False):
        print("\nType Inference Report:")
        print(analyzer.format_type_report())

    if getattr(args, "show_ast", False):
        print("\nDecorated AST:")
        print(analyzer.format_decorated_ast())

    if getattr(args, "show_report", False):
        print("\nValidation Report:")
        print(analyzer.format_validation_report())

    if getattr(args, "verbose", False):
        print("\nStatistics:", file=sys.stderr)
        print(f"  Tokens: {len(tokens)}", file=sys.stderr)
        print(f"  Lexical errors: {len(lex_errors)}", file=sys.stderr)
        print(f"  Parse errors: {len(parse_errors)}", file=sys.stderr)
        print(f"  Semantic errors: {len(semantic_errors)}", file=sys.stderr)
        print(
            f"  AST nodes: {ast.count_nodes() if hasattr(ast, 'count_nodes') else 'N/A'}",
            file=sys.stderr,
        )


def run_symbols(args):
    source = read_file(args.input)

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    lex_errors = scanner.get_errors()

    if lex_errors:
        print("Cannot dump symbols: lexical errors found.", file=sys.stderr)
        print_errors(lex_errors)
        sys.exit(1)

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()

    if parse_errors:
        print("Cannot dump symbols: syntax errors found.", file=sys.stderr)
        print_errors(parse_errors)
        sys.exit(1)

    analyzer = SemanticAnalyzer(args.input)
    analyzer.analyze(ast)
    semantic_errors = analyzer.get_errors()

    if semantic_errors:
        print("Cannot dump symbols: semantic errors found.", file=sys.stderr)
        for error in semantic_errors:
            print(error.format(), file=sys.stderr)
            print(file=sys.stderr)
        sys.exit(1)

    output = analyzer.get_symbol_table().dump()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


def run_ir(args):
    source = read_file(args.input)

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    lex_errors = scanner.get_errors()

    if lex_errors:
        print("Cannot generate IR: lexical errors found.", file=sys.stderr)
        print_errors(lex_errors)
        sys.exit(1)

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()

    if parse_errors:
        print("Cannot generate IR: syntax errors found.", file=sys.stderr)
        print_errors(parse_errors)
        sys.exit(1)

    analyzer = SemanticAnalyzer(args.input)
    analyzer.analyze(ast)
    semantic_errors = analyzer.get_errors()

    if semantic_errors:
        print("Cannot generate IR: semantic errors found.", file=sys.stderr)
        for error in semantic_errors:
            print(error.format(), file=sys.stderr)
            print(file=sys.stderr)
        sys.exit(1)

    ir_gen = IRGenerator(analyzer.get_symbol_table())
    program = ir_gen.generate(ast)
    if getattr(args, "optimize", False):
        program = ConstantPropagationPass().run(program)
        program = ConstantFoldingPass().run(program)
        program = DeadCodeEliminationPass().run(program)
        program = DeadStoreEliminationPass().run(program)


    if getattr(args, "validate", False):
        validation = IRValidator(program).validate()
        if not validation.is_valid():
            print("IR validation failed.", file=sys.stderr)
            for error in validation.errors:
                print(error, file=sys.stderr)
            sys.exit(1)

    if args.format == "text":
        output = program.to_text()

    elif args.format == "json":
        output = __import__("json").dumps(program.to_json(), ensure_ascii=False, indent=2)


    elif args.format == "dot":

        lines = [

            "digraph CFG {",

            '  rankdir=TB;',

            '  node [shape=box, style="rounded,filled", fontname="Consolas"];'

        ]

        for func in program.functions:

            for block in func.blocks:

                label_lines = [block.label]

                for instr in block.instructions:
                    label_lines.append(instr.to_text().replace('"', '\\"'))

                node_label = "\\l".join(label_lines) + "\\l"

                node_name = f"{func.name}_{block.label}"

                if block.label == "entry":

                    fill = "lightgreen"

                elif "exit" in block.label:

                    fill = "lightcoral"

                elif block.label.startswith("then"):

                    fill = "lightblue"

                elif block.label.startswith("else"):

                    fill = "lightyellow"

                elif "endif" in block.label:

                    fill = "plum"

                elif "while_cond" in block.label or "for_cond" in block.label:

                    fill = "khaki"

                elif "while_body" in block.label or "for_body" in block.label:

                    fill = "lightsalmon"

                else:

                    fill = "white"

                lines.append(

                    f'  "{node_name}" [label="{node_label}", fillcolor="{fill}"];'

                )

            for block in func.blocks:

                from_node = f"{func.name}_{block.label}"

                for succ in block.successors:
                    to_node = f"{func.name}_{succ}"

                    lines.append(f'  "{from_node}" -> "{to_node}";')

        lines.append("}")

        output = "\n".join(lines)

    else:
        print(f"Unsupported IR format: {args.format}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)

    if getattr(args, "stats", False):
        stats = program.get_statistics()
        print("\nIR Statistics:", file=sys.stderr)
        print(f"  Functions: {stats['functions']}", file=sys.stderr)
        print(f"  Basic blocks: {stats['basic_blocks']}", file=sys.stderr)
        print(f"  Instructions: {stats['instructions']}", file=sys.stderr)
        print(f"  Temporaries used: {stats['temporaries']}", file=sys.stderr)



def run_compile(args):
    source = read_file(args.input)

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    lex_errors = scanner.get_errors()

    if lex_errors:
        print("Cannot compile: lexical errors found.", file=sys.stderr)
        print_errors(lex_errors)
        sys.exit(1)

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()

    if parse_errors:
        print("Cannot compile: syntax errors found.", file=sys.stderr)
        print_errors(parse_errors)
        sys.exit(1)

    analyzer = SemanticAnalyzer(args.input)
    analyzer.analyze(ast)
    semantic_errors = analyzer.get_errors()

    if semantic_errors:
        print("Cannot compile: semantic errors found.", file=sys.stderr)
        for error in semantic_errors:
            print(error.format(), file=sys.stderr)
            print(file=sys.stderr)
        sys.exit(1)

    ir_program = IRGenerator(
        analyzer.get_symbol_table()
    ).generate(ast)

    ir_program = ConstantPropagationPass().run(ir_program)
    ir_program = ConstantFoldingPass().run(ir_program)
    ir_program = DeadCodeEliminationPass().run(ir_program)
    ir_program = DeadStoreEliminationPass().run(ir_program)
    asm = X86Generator(
        use_register_allocation=getattr(args, "use_register_allocation", False)
    ).generate(ir_program)

    if args.output:
        Path(args.output).write_text(asm, encoding="utf-8")
    else:
        print(asm)



def run_info():
    print("MiniCompiler")
    print(f"Version: {VERSION}")
    print("Language: Simplified C-like")
    print("Sprint: 5")


def run_spec():
    if not SPEC_PATH.exists():
        print("Specification not found.", file=sys.stderr)
        sys.exit(1)

    content = SPEC_PATH.read_text(encoding="utf-8")
    sys.stdout.buffer.write(content.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(prog="compiler")
    sub = parser.add_subparsers(dest="command", required=True)

    # preprocess
    pp = sub.add_parser("preprocess")
    pp.add_argument("--input", required=True)
    pp.add_argument("--output")
    pp.add_argument("--defines", nargs="*")
    pp.add_argument("--show", action="store_true")
    pp.set_defaults(func=run_preprocess)

    # lex
    lex = sub.add_parser("lex")
    lex.add_argument("--input", required=True)
    lex.add_argument("--output")
    lex.add_argument("--quiet", action="store_true")
    lex.add_argument("--fail-fast", action="store_true")
    lex.set_defaults(func=run_lex)

    # parse
    parse = sub.add_parser("parse", help="Parse source file and output AST")
    parse.add_argument("--input", required=True)
    parse.add_argument(
        "--output", "--output-file",
        dest="output",
        help="Output file (default: stdout)"
    )
    parse.add_argument(
        "--format", "--ast-format",
        dest="format",
        choices=["text", "dot", "json"],
        default="text",
        help="AST output format"
    )
    parse.add_argument("--verbose", action="store_true", help="Show parsing statistics")
    parse.add_argument("--fail-fast", action="store_true", help="Stop on first error")
    parse.set_defaults(func=run_parse)

    # full
    full = sub.add_parser("full")
    full.add_argument("--input", required=True)
    full.add_argument("--defines", nargs="*")
    full.set_defaults(func=run_full)

    # check
    check = sub.add_parser("check", help="Run full semantic analysis")
    check.add_argument("--input", required=True)
    check.add_argument("--verbose", action="store_true", help="Show analysis statistics")
    check.add_argument("--show-types", action="store_true", help="Show inferred types")
    check.add_argument("--show-ast", action="store_true", help="Show decorated AST")
    check.add_argument("--show-report", action="store_true", help="Show semantic validation report")
    check.set_defaults(func=run_check)

    # symbols
    symbols = sub.add_parser("symbols", help="Dump symbol table after semantic analysis")
    symbols.add_argument("--input", required=True)
    symbols.add_argument("--output", help="Output file (default: stdout)")
    symbols.set_defaults(func=run_symbols)

    # ir
    ir = sub.add_parser("ir", help="Generate intermediate representation (IR)")
    ir.add_argument("--input", required=True)
    ir.add_argument("--output", help="Output file (default: stdout)")
    ir.add_argument(
        "--format",
        choices=["text", "dot", "json"],
        default="text",
        help="IR output format"
    )
    ir.add_argument("--stats", action="store_true", help="Show IR statistics")
    ir.add_argument("--optimize", action="store_true", help="Apply IR optimization passes")
    ir.set_defaults(func=run_ir)
    ir.add_argument("--validate", action="store_true", help="Validate generated IR")

    # compile
    compile_cmd = sub.add_parser(
        "compile",
        help="Compile source to x86-64 assembly"
    )

    compile_cmd.add_argument("--input", required=True)

    compile_cmd.add_argument(
        "--output",
        help="Output assembly file (default: stdout)"
    )

    compile_cmd.add_argument(
        "--use-register-allocation",
        action="store_true",
        help="Enable experimental linear scan register allocation"
    )

    compile_cmd.set_defaults(func=run_compile)

    # info
    info = sub.add_parser("info")
    info.set_defaults(func=lambda args: run_info())

    # spec
    spec = sub.add_parser("spec")
    spec.set_defaults(func=lambda args: run_spec())

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()