from __future__ import annotations

import argparse
import random
from pathlib import Path


OPS = ["+", "*"]


def make_program(seed: int) -> str:
    rng = random.Random(seed)

    a = rng.randint(1, 20)
    b = rng.randint(1, 20)
    c = rng.randint(1, 10)
    op1 = rng.choice(OPS)
    op2 = rng.choice(OPS)

    return f"""fn main() -> int {{
    int a = {a};
    int b = {b};
    int c = {c};

    int result = a {op1} b {op2} c;

    printf("result=%d\\n", result);

    return result;
}}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--count", type=int, default=10)
    parser.add_argument("-o", "--out-dir", default="generated_programs")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(args.count):
        program = make_program(args.seed + i)
        path = out_dir / f"generated_{i:03}.src"
        path.write_text(program, encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()