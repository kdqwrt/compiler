from src.codegen.peephole_optimizer import PeepholeOptimizer


def test_peephole_removes_jump_to_next_label():
    lines = [
        "    mov eax, 1",
        "    jmp .L1",
        ".L1:",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    jmp .L1" not in optimized
    assert ".L1:" in optimized


def test_peephole_removes_dead_code_after_ret():
    lines = [
        "    mov eax, 1",
        "    ret",
        "    mov eax, 999",
        ".L1:",
        "    mov eax, 2",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 999" not in optimized
    assert "    mov eax, 2" in optimized


def test_peephole_removes_dead_code_after_jmp_until_label():
    lines = [
        "    mov eax, 1",
        "    jmp .L1",
        "    mov eax, 999",
        ".L1:",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 999" not in optimized
    assert ".L1:" in optimized


def test_peephole_constant_folds_add():
    lines = [
        "    mov eax, 2",
        "    add eax, 3",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 5" in optimized
    assert "    add eax, 3" not in optimized


def test_peephole_constant_folds_sub():
    lines = [
        "    mov eax, 10",
        "    sub eax, 4",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 6" in optimized
    assert "    sub eax, 4" not in optimized


def test_peephole_constant_folds_mul():
    lines = [
        "    mov eax, 3",
        "    imul eax, 4",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 12" in optimized
    assert "    imul eax, 4" not in optimized


def test_peephole_uses_window_of_five_for_long_pattern():
    lines = [
        "    mov eax, 2",
        "    add eax, 3",
        "    sub eax, 1",
        "    imul eax, 4",
        "    add eax, 2",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 18" in optimized


def test_peephole_removes_redundant_move():
    lines = [
        "    mov eax, eax",
        "    mov r12d, r12d",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, eax" not in optimized
    assert "    mov r12d, r12d" not in optimized
    assert "    ret" in optimized


def test_peephole_removes_arithmetic_identities():
    lines = [
        "    mov eax, 10",
        "    add eax, 0",
        "    sub eax, 0",
        "    imul eax, 1",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    add eax, 0" not in optimized
    assert "    sub eax, 0" not in optimized
    assert "    imul eax, 1" not in optimized


def test_peephole_multiplies_by_zero_to_mov_zero():
    lines = [
        "    mov eax, 10",
        "    imul eax, 0",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    mov eax, 0" in optimized
    assert "    imul eax, 0" not in optimized


def test_peephole_strength_reduces_power_of_two_multiply():
    lines = [
        "    mov eax, dword [rbp-8]",
        "    imul eax, 8",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    shl eax, 3" in optimized
    assert "    imul eax, 8" not in optimized


def test_peephole_keeps_non_power_of_two_multiply():
    lines = [
        "    mov eax, dword [rbp-8]",
        "    imul eax, 6",
        "    ret",
    ]

    optimized = PeepholeOptimizer(window_size=5).optimize(lines)

    assert "    imul eax, 6" in optimized