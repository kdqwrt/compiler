import random
import string
import subprocess
import sys


def random_source(length: int) -> str:
    alphabet = string.ascii_letters + string.digits + "{}();+-*/=&|!<>[]\"'\n "
    return "".join(random.choice(alphabet) for _ in range(length))


def test_random_invalid_inputs_do_not_crash(tmp_path):
    random.seed(42)

    for i in range(30):
        source = tmp_path / f"fuzz_{i}.src"
        source.write_text(random_source(80), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "check", "--input", str(source)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode in {0, 1}
        assert "Traceback" not in result.stderr