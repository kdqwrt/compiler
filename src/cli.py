import argparse
import sys
from pathlib import Path

from src.lexer.scanner import Scanner
from src.preprocessor.preprocessor import Preprocessor
from src.preprocessor.macros import MacroProcessor


VERSION = "0.1.0"
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
    scanner.scan_tokens()
    errors = scanner.get_errors()

    if errors:
        print("Syntax check failed.")
        print_errors(errors)
        sys.exit(1)

    print("No lexical errors detected.")



def run_info():
    print("MiniCompiler")
    print(f"Version: {VERSION}")
    print("Language: Simplified C-like")
    print("Sprint: 1 (Lexer + Preprocessor)")


def run_spec():
    if SPEC_PATH.exists():
        print(SPEC_PATH.read_text(encoding="utf-8"))
    else:
        print("Specification not found.")




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

    # full
    full = sub.add_parser("full")
    full.add_argument("--input", required=True)
    full.add_argument("--defines", nargs="*")
    full.set_defaults(func=run_full)

    # check
    check = sub.add_parser("check")
    check.add_argument("--input", required=True)
    check.set_defaults(func=run_check)

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
