import argparse
import sys
import json
import os
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
from src.diagnostics.renderer import (
    DiagnosticRenderer,
    from_plain_error,
    from_semantic_error,
)
from src.diagnostics.renderer import Diagnostic, DiagnosticLevel
import subprocess
import tempfile


VERSION = "0.3.0"
SPEC_PATH = Path("docs/language_spec.md")

def load_config(path: str | None) -> dict:
    if path is None:
        env_path = os.environ.get("MYCC_CONFIG")
        path = env_path

    if path is None:
        return {}

    config_path = Path(path)

    if not config_path.exists():
        print(f"error: config file not found: {path}", file=sys.stderr)
        sys.exit(2)

    return json.loads(config_path.read_text(encoding="utf-8"))


def apply_config_defaults(args, config: dict):
    if not config:
        return args

    if not getattr(args, "optimize", False):
        args.optimize = bool(config.get("optimize", args.optimize))

    if getattr(args, "opt_level", 0) == 0:
        args.opt_level = int(config.get("opt_level", args.opt_level))

    args.target = config.get("target", args.target)
    args.error_format = config.get("error_format", args.error_format)
    args.max_errors = config.get("max_errors", args.max_errors)
    args.color = config.get("color", args.color)

    if not getattr(args, "libraries", None):
        args.libraries = config.get("libraries", [])

    return args


def use_color(color_mode: str) -> bool:
    if color_mode == "always":
        return True
    if color_mode == "never":
        return False
    return sys.stderr.isatty()

def link_objects(object_paths: list[str], output_path: str, libraries: list[str] | None = None):
    libraries = libraries or []

    gcc_args = ["gcc", "-no-pie", *object_paths]

    for library in libraries:
        gcc_args.append(f"-l{library}")

    gcc_args.extend(["-o", output_path])

    result = subprocess.run(
        gcc_args,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Linker failed.", file=sys.stderr)

        if result.stdout:
            print(result.stdout, file=sys.stderr)

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        sys.exit(result.returncode)

def compile_source_to_object(
    source_file: str,
    obj_path: str,
    optimize: bool = False,
    use_register_allocation: bool = False,
    error_format: str = "text",
    max_errors: int | None = None,
    Wall: bool = False,
    Werror: bool = False,
):
    with tempfile.NamedTemporaryFile(
        suffix=".asm",
        delete=False,
    ) as tmp:
        asm_path = tmp.name

    compile_args = argparse.Namespace(
        input=source_file,
        output=asm_path,
        use_register_allocation=use_register_allocation,
        optimize=optimize,
        error_format=error_format,
        max_errors=max_errors,
        Wall=Wall,
        Werror=Werror,
    )

    run_compile(compile_args)

    assemble_to_object(
        asm_path=asm_path,
        obj_path=obj_path,
    )

    Path(asm_path).unlink(missing_ok=True)

def assemble_to_object(asm_path: str, obj_path: str):
    result = subprocess.run(
        [
            "nasm",
            "-f",
            "elf64",
            "-g",
            "-F",
            "dwarf",
            asm_path,
            "-o",
            obj_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Assembler failed.", file=sys.stderr)

        if result.stdout:
            print(result.stdout, file=sys.stderr)

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        sys.exit(result.returncode)


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def print_errors(errors, category: str = "ERROR", file_name: str = "<input>"):
    if not errors:
        return False

    renderer = DiagnosticRenderer(use_color=False)
    diagnostics = [
        from_plain_error(error, category=category, file_name=file_name)
        for error in errors
    ]

    print(renderer.render_many(diagnostics), file=sys.stderr)
    return True

def print_semantic_errors(
    errors,
    error_format: str = "text",
    max_errors: int | None = None,
    color: str = "auto",
):
    if not errors:
        return False

    selected_errors = errors[:max_errors] if max_errors else errors

    renderer = DiagnosticRenderer(use_color=use_color(color))
    diagnostics = [from_semantic_error(error) for error in selected_errors]

    if error_format == "json":
        print(renderer.render_json_many(diagnostics), file=sys.stderr)
    else:
        print(renderer.render_many(diagnostics), file=sys.stderr)

        if max_errors and len(errors) > max_errors:
            print(
                f"\nerror: stopped after {max_errors} errors "
                f"({len(errors)} total)",
                file=sys.stderr,
            )

    return True

def print_warnings(
    warnings,
    enabled: bool = False,
    as_errors: bool = False,
):
    if not enabled or not warnings:
        return False

    renderer = DiagnosticRenderer(use_color=False)

    diagnostics = []

    for warning in warnings:
        diagnostics.append(
            Diagnostic(
                level=(
                    DiagnosticLevel.ERROR
                    if as_errors
                    else DiagnosticLevel.WARNING
                ),
                category=warning["category"],
                message=warning["message"],
                line=warning["line"],
                column=warning["column"],
                context=warning.get("context"),
            )
        )

    print(renderer.render_many(diagnostics), file=sys.stderr)

    return as_errors


def diagnostic_options(args):
    return {
        "error_format": getattr(args, "error_format", "text"),
        "max_errors": getattr(args, "max_errors", None),
        "color": getattr(args, "color", "auto"),
    }

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
    semantic_warnings = analyzer.get_warnings()

    if semantic_errors:
        print("Check failed: semantic errors found.", file=sys.stderr)
        print_semantic_errors(semantic_errors, **diagnostic_options(args))
        sys.exit(1)

    warnings_are_errors = print_warnings(
        semantic_warnings,
        enabled=args.Wall,
        as_errors=args.Werror,
    )

    if warnings_are_errors:
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
        print_semantic_errors(semantic_errors, **diagnostic_options(args))
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
        print_semantic_errors(semantic_errors, **diagnostic_options(args))
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
        print_semantic_errors(semantic_errors, **diagnostic_options(args))
        sys.exit(1)

    ir_program = IRGenerator(
        analyzer.get_symbol_table()
    ).generate(ast)

    if getattr(args, "optimize", False):
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
    print("Sprint: 8")


def run_spec():
    if not SPEC_PATH.exists():
        print("Specification not found.", file=sys.stderr)
        sys.exit(1)

    content = SPEC_PATH.read_text(encoding="utf-8")
    sys.stdout.buffer.write(content.encode("utf-8"))


def run_unix_style(args):
    source_files = args.sourcefiles

    if args.version:
        print(f"MiniCompiler {VERSION}")
        return

    if not source_files:
        print("error: source file is required", file=sys.stderr)
        sys.exit(2)

    if len(source_files) > 1 and (args.E or args.ast or args.ir or args.S):
        print(
            "error: -E, --ast, --ir and -S support only one source file",
            file=sys.stderr,
        )
        sys.exit(2)

    source_file = source_files[0]

    if args.E:
        pp_args = argparse.Namespace(
            input=source_file,
            output=args.output,
            defines=[],
            show=args.output is None,
        )
        run_preprocess(pp_args)
        return

    if args.ast:
        parse_args = argparse.Namespace(
            input=source_file,
            output=args.output,
            format=args.ast_format,
            verbose=args.verbose,
            fail_fast=False,
        )
        run_parse(parse_args)
        return

    if args.ir:
        ir_args = argparse.Namespace(
            input=source_file,
            output=args.output,
            format="text",
            stats=args.verbose,
            optimize=args.optimize or args.opt_level > 0,
            validate=False,
            error_format=args.error_format,
            max_errors=args.max_errors,
            Wall=args.Wall,
            Werror=args.Werror,
        )
        run_ir(ir_args)
        return

    if args.S:
        compile_args = argparse.Namespace(
            input=source_file,
            output=args.output,
            use_register_allocation=args.use_register_allocation,
            optimize=args.optimize or args.opt_level > 0,
            error_format=args.error_format,
            max_errors=args.max_errors,
            Wall=args.Wall,
            Werror=args.Werror,
        )

        run_compile(compile_args)
        return

    if args.c:
        if len(source_files) == 1:
            output_path = args.output or Path(source_file).with_suffix(".o")
            compile_source_to_object(
                source_file=source_file,
                obj_path=str(output_path),
                optimize=args.optimize or args.opt_level > 0,
                use_register_allocation=args.use_register_allocation,
                error_format=args.error_format,
                max_errors=args.max_errors,
                Wall=args.Wall,
                Werror=args.Werror,
            )
            return

        if args.output:
            print(
                "error: -o with -c and multiple source files is not supported",
                file=sys.stderr,
            )
            sys.exit(2)

        for src in source_files:
            obj_path = Path(src).with_suffix(".o")
            compile_source_to_object(
                source_file=src,
                obj_path=str(obj_path),
                optimize=args.optimize or args.opt_level > 0,
                use_register_allocation=args.use_register_allocation,
                error_format=args.error_format,
                max_errors=args.max_errors,
                Wall=args.Wall,
                Werror=args.Werror,
            )

        return

    output_path = args.output or "a.out"
    object_paths = []

    try:
        for src in source_files:
            with tempfile.NamedTemporaryFile(
                suffix=".o",
                delete=False,
            ) as tmp:
                obj_path = tmp.name

            compile_source_to_object(
                source_file=src,
                obj_path=obj_path,
                optimize=args.optimize or args.opt_level > 0,
                use_register_allocation=args.use_register_allocation,
                error_format=args.error_format,
                max_errors=args.max_errors,
                Wall=args.Wall,
                Werror=args.Werror,
            )

            object_paths.append(obj_path)

        link_objects(
            object_paths=object_paths,
            output_path=str(output_path),
            libraries=args.libraries,
        )

    finally:
        for obj_path in object_paths:
            Path(obj_path).unlink(missing_ok=True)

    # output_path = args.output or Path(source_file).with_suffix("").name
    #
    # with tempfile.NamedTemporaryFile(
    #         suffix=".asm",
    #         delete=False,
    # ) as tmp:
    #     asm_path = tmp.name
    #
    # obj_path = str(Path(asm_path).with_suffix(".o"))
    #
    # compile_args = argparse.Namespace(
    #     input=source_file,
    #     output=asm_path,
    #     use_register_allocation=False,
    #     optimize=args.optimize or args.opt_level > 0,
    #     error_format=args.error_format,
    #     max_errors=args.max_errors,
    #     Wall=args.Wall,
    #     Werror=args.Werror,
    # )
    #
    # run_compile(compile_args)
    #
    # assemble_to_object(
    #     asm_path=asm_path,
    #     obj_path=obj_path,
    # )
    #
    # link_objects(
    #     object_paths=[obj_path],
    #     output_path=str(output_path),
    #     libraries=args.libraries,
    # )
    #
    # Path(asm_path).unlink(missing_ok=True)
    # Path(obj_path).unlink(missing_ok=True)


def main():
    legacy_commands = {
        "preprocess",
        "lex",
        "parse",
        "full",
        "check",
        "symbols",
        "ir",
        "compile",
        "info",
        "spec",
    }

    # Новый Unix-style режим:
    # python -m src.cli examples/file.src --ir
    # python -m src.cli examples/file.src -S -o out.asm
    if len(sys.argv) > 1 and sys.argv[1] not in legacy_commands:
        parser = argparse.ArgumentParser(
            prog="mycc",
            description="MiniCompiler Unix-style command line interface",
        )

        parser.add_argument("sourcefiles", nargs="*", help="Source files to compile")
        parser.add_argument("-o", "--output", help="Output file")
        parser.add_argument("-S", action="store_true", help="Emit assembly")
        parser.add_argument("-c", action="store_true", help="Compile to object file mode")
        parser.add_argument("-E", action="store_true", help="Run preprocessor only")
        parser.add_argument("--ast", action="store_true", help="Print AST")
        parser.add_argument(
            "--ast-format",
            choices=["text", "dot", "json"],
            default="text",
            help="AST output format",
        )
        parser.add_argument("--ir", action="store_true", help="Print IR")
        parser.add_argument("--optimize", action="store_true", help="Enable optimizations")
        parser.add_argument(
            "--use-register-allocation",
            action="store_true",
            help="Enable register allocation",
        )
        parser.add_argument(
            "-O",
            dest="opt_level",
            type=int,
            choices=[0, 1, 2, 3],
            default=0,
            help="Optimization level",
        )
        parser.add_argument("-O0", dest="opt_level", action="store_const", const=0)
        parser.add_argument("-O1", dest="opt_level", action="store_const", const=1)
        parser.add_argument("-O2", dest="opt_level", action="store_const", const=2)
        parser.add_argument("-O3", dest="opt_level", action="store_const", const=3)
        parser.add_argument("--target", default="x86_64-linux", help="Compilation target")
        parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
        parser.add_argument("--version", action="store_true", help="Show version")

        parser.add_argument("--config", help="Path to JSON configuration file")
        parser.add_argument(
            "--color",
            choices=["auto", "always", "never"],
            default="auto",
            help="Diagnostic color mode",
        )

        parser.add_argument(
            "--error-format",
            choices=["text", "json"],
            default="text",
            help="Diagnostic output format",
        )
        parser.add_argument(
            "--max-errors",
            type=int,
            default=None,
            help="Stop after N errors",
        )
        parser.add_argument("-Wall", action="store_true", help="Enable all warnings")
        parser.add_argument("-Werror", action="store_true", help="Treat warnings as errors")

        parser.add_argument(
            "-l",
            "--library",
            dest="libraries",
            action="append",
            default=[],
            help="Link with library, for example: -l m",
        )

        args = parser.parse_args()
        args = apply_config_defaults(args, load_config(args.config))
        run_unix_style(args)
        return

    # Старый subcommand режим:
    # python -m src.cli compile --input file.src --output out.asm
    parser = argparse.ArgumentParser(
        prog="mycc",
        description="MiniCompiler command line interface",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("preprocess")
    pp.add_argument("--input", required=True)
    pp.add_argument("--output")
    pp.add_argument("--defines", nargs="*")
    pp.add_argument("--show", action="store_true")
    pp.set_defaults(func=run_preprocess)

    lex = sub.add_parser("lex")
    lex.add_argument("--input", required=True)
    lex.add_argument("--output")
    lex.add_argument("--quiet", action="store_true")
    lex.add_argument("--fail-fast", action="store_true")
    lex.set_defaults(func=run_lex)

    parse = sub.add_parser("parse", help="Parse source file and output AST")
    parse.add_argument("--input", required=True)
    parse.add_argument("--output", "--output-file", dest="output")
    parse.add_argument(
        "--format",
        "--ast-format",
        dest="format",
        choices=["text", "dot", "json"],
        default="text",
    )
    parse.add_argument("--verbose", action="store_true")
    parse.add_argument("--fail-fast", action="store_true")
    parse.set_defaults(func=run_parse)

    full = sub.add_parser("full")
    full.add_argument("--input", required=True)
    full.add_argument("--defines", nargs="*")
    full.set_defaults(func=run_full)

    check = sub.add_parser("check", help="Run full semantic analysis")
    check.add_argument("--input", required=True)
    check.add_argument("--verbose", action="store_true")
    check.add_argument("--show-types", action="store_true")
    check.add_argument("--show-ast", action="store_true")
    check.add_argument("--show-report", action="store_true")
    check.add_argument("--error-format", choices=["text", "json"], default="text")
    check.add_argument("--max-errors", type=int, default=None)
    check.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
    )
    check.add_argument("-Wall", action="store_true")
    check.add_argument("-Werror", action="store_true")
    check.set_defaults(func=run_check)


    symbols = sub.add_parser("symbols", help="Dump symbol table")
    symbols.add_argument("--input", required=True)
    symbols.add_argument("--output")
    symbols.add_argument("--error-format", choices=["text", "json"], default="text")
    symbols.add_argument("--max-errors", type=int, default=None)
    symbols.add_argument("-Wall", action="store_true")
    symbols.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
    )
    symbols.add_argument("-Werror", action="store_true")
    symbols.set_defaults(func=run_symbols)

    ir = sub.add_parser("ir", help="Generate IR")
    ir.add_argument("--input", required=True)
    ir.add_argument("--output")
    ir.add_argument(
        "--format",
        choices=["text", "dot", "json"],
        default="text",
    )
    ir.add_argument("--stats", action="store_true")
    ir.add_argument("--optimize", action="store_true")
    ir.add_argument("--validate", action="store_true")
    ir.add_argument("--error-format", choices=["text", "json"], default="text")
    ir.add_argument("--max-errors", type=int, default=None)
    ir.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
    )
    ir.add_argument("-Wall", action="store_true")
    ir.add_argument("-Werror", action="store_true")
    ir.set_defaults(func=run_ir)

    compile_cmd = sub.add_parser("compile", help="Compile source to x86-64 assembly")
    compile_cmd.add_argument("--input", required=True)
    compile_cmd.add_argument("--output")
    compile_cmd.add_argument("--optimize", action="store_true")
    compile_cmd.add_argument("--use-register-allocation", action="store_true")
    compile_cmd.add_argument("--error-format", choices=["text", "json"], default="text")
    compile_cmd.add_argument("--max-errors", type=int, default=None)
    compile_cmd.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
    )
    compile_cmd.add_argument("-Wall", action="store_true")
    compile_cmd.add_argument("-Werror", action="store_true")
    compile_cmd.set_defaults(func=run_compile)

    info = sub.add_parser("info")
    info.set_defaults(func=lambda args: run_info())

    spec = sub.add_parser("spec")
    spec.set_defaults(func=lambda args: run_spec())

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()