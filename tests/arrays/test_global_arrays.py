from tests.arrays.test_local_arrays import generate_asm, run_program


def test_global_array_codegen_uses_bss_resd():
    source = """
    int g[3];

    fn main() -> int {
        g[0] = 4;
        g[1] = 6;
        return g[0] + g[1];
    }
    """

    asm = generate_asm(source)

    assert "section .bss" in asm
    assert "global g" in asm
    assert "g: resd 3" in asm
    assert "lea r11, [rel g]" in asm


def test_global_array_executes(tmp_path):
    source = """
    int g[3];

    fn main() -> int {
        g[0] = 4;
        g[1] = 6;
        return g[0] + g[1];
    }
    """

    result = run_program(tmp_path, source)

    assert result.returncode == 10