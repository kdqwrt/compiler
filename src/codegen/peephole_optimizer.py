from __future__ import annotations

import math
import re


class PeepholeOptimizer:
    def __init__(self, window_size: int = 5) -> None:
        self.window_size = window_size

    def optimize(self, lines: list[str]) -> list[str]:
        previous = list(lines)

        while True:
            optimized = self._optimize_once(previous)
            if optimized == previous:
                return optimized
            previous = optimized

    def _optimize_once(self, lines: list[str]) -> list[str]:
        result: list[str] = []
        i = 0

        while i < len(lines):
            window = lines[i:i + self.window_size]

            folded, consumed = self._fold_constant_chain(window)
            if folded is not None:
                result.append(folded)
                i += consumed
                continue

            replacement = self._strength_reduce(window)
            if replacement is not None:
                result.extend(replacement)
                i += 1
                continue

            replacement = self._simplify_arithmetic_identity(window)
            if replacement is not None:
                result.extend(replacement)
                i += 1
                continue

            if self._is_redundant_move(window):
                i += 1
                continue

            replacement = self._collapse_move_chain(window)
            if replacement is not None:
                result.extend(replacement)
                i += 2
                continue

            replacement = self._fold_move_into_cmp(window)
            if replacement is not None:
                result.extend(replacement)
                i += 2
                continue

            replacement = self._fold_move_into_cmp_zero(window)
            if replacement is not None:
                result.extend(replacement)
                i += 2
                continue

            replacement = self._fold_two_moves_into_cmp(window)
            if replacement is not None:
                result.extend(replacement)
                i += 3
                continue

            replacement = self._fold_const_register_add(window)
            if replacement is not None:
                result.extend(replacement)
                i += 3
                continue

            if self._is_jump_to_next_label(window):
                i += 1
                continue

            if self._is_dead_after_unconditional_exit(lines, i):
                i += 1
                continue

            result.append(lines[i])
            i += 1

        return result

    def _is_label(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.endswith(":") and not stripped.startswith(";")

    def _is_instruction(self, line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and not stripped.startswith(";") and not self._is_label(line)

    def _is_unconditional_exit(self, line: str) -> bool:
        stripped = line.strip()
        return stripped == "ret" or stripped.startswith("jmp ")

    def _is_jump_to_next_label(self, window: list[str]) -> bool:
        if len(window) < 2:
            return False

        current = window[0].strip()
        next_line = window[1].strip()

        if not current.startswith("jmp "):
            return False

        target = current.removeprefix("jmp ").strip()
        return next_line == f"{target}:"

    def _is_dead_after_unconditional_exit(self, lines: list[str], index: int) -> bool:
        if index == 0:
            return False

        current = lines[index]
        previous = lines[index - 1]

        if self._is_label(current):
            return False

        if not self._is_instruction(current):
            return False

        return self._is_unconditional_exit(previous)

    def _is_redundant_move(self, window: list[str]) -> bool:
        if not window:
            return False

        line = window[0].strip()
        match = re.fullmatch(r"mov\s+([a-z0-9]+),\s*\1", line)
        return match is not None

    def _parse_mov_const(self, line: str):
        stripped = line.strip()
        match = re.fullmatch(
            r"mov\s+([a-z0-9]+),\s*(-?\d+)",
            stripped,
        )
        if match is None:
            return None

        return match.group(1), int(match.group(2))

    def _parse_arith_const(self, line: str, reg: str):
        stripped = line.strip()
        match = re.fullmatch(
            rf"(add|sub|imul)\s+{re.escape(reg)},\s*(-?\d+)",
            stripped,
        )
        if match is None:
            return None

        return match.group(1), int(match.group(2))

    def _fold_constant_chain(self, window: list[str]) -> tuple[str | None, int]:
        if not window:
            return None, 0

        parsed = self._parse_mov_const(window[0])
        if parsed is None:
            return None, 0

        reg, value = parsed
        consumed = 1

        for line in window[1:]:
            if self._is_label(line) or not self._is_instruction(line):
                break

            arith = self._parse_arith_const(line, reg)
            if arith is None:
                break

            op, right = arith

            if op == "add":
                value += right
            elif op == "sub":
                value -= right
            elif op == "imul":
                value *= right

            consumed += 1

        if consumed <= 1:
            return None, 0

        indent = window[0][: len(window[0]) - len(window[0].lstrip())]
        return f"{indent}mov {reg}, {value}", consumed

    def _simplify_arithmetic_identity(self, window: list[str]) -> list[str] | None:
        if not window:
            return None

        line = window[0]
        stripped = line.strip()

        if re.fullmatch(r"(add|sub)\s+[a-z0-9]+,\s*0", stripped):
            return []

        if re.fullmatch(r"imul\s+[a-z0-9]+,\s*1", stripped):
            return []

        match_zero = re.fullmatch(r"imul\s+([a-z0-9]+),\s*0", stripped)
        if match_zero is not None:
            reg = match_zero.group(1)
            indent = line[: len(line) - len(line.lstrip())]
            return [f"{indent}mov {reg}, 0"]

        return None

    def _strength_reduce(self, window: list[str]) -> list[str] | None:
        if not window:
            return None

        line = window[0]
        stripped = line.strip()

        match = re.fullmatch(r"imul\s+([a-z0-9]+),\s*(\d+)", stripped)
        if match is None:
            return None

        reg = match.group(1)
        value = int(match.group(2))

        if value <= 1:
            return None

        if value & (value - 1) != 0:
            return None

        shift = int(math.log2(value))
        indent = line[: len(line) - len(line.lstrip())]

        return [f"{indent}shl {reg}, {shift}"]

    def _collapse_move_chain(self, window: list[str]) -> list[str] | None:
        if len(window) < 2:
            return None

        first = window[0]
        second = window[1]

        reg_pattern = (
            r"(rax|rbx|rcx|rdx|rsi|rdi|r8|r9|r10|r11|r12|r13|r14|r15|"
            r"eax|ebx|ecx|edx|esi|edi|r8d|r9d|r10d|r11d|r12d|r13d|r14d|r15d|"
            r"al|bl|cl|dl|sil|dil|r8b|r9b|r10b|r11b|r12b|r13b|r14b|r15b)"
        )

        first_match = re.fullmatch(
            rf"\s*mov\s+{reg_pattern},\s*{reg_pattern}",
            first.strip(),
        )
        second_match = re.fullmatch(
            rf"\s*mov\s+{reg_pattern},\s*{reg_pattern}",
            second.strip(),
        )

        if first_match is None or second_match is None:
            return None

        mid_dest = first_match.group(1)
        source = first_match.group(2)

        final_dest = second_match.group(1)
        second_source = second_match.group(2)

        if second_source != mid_dest:
            return None

        if final_dest == source:
            return []

        indent = second[: len(second) - len(second.lstrip())]
        return [f"{indent}mov {final_dest}, {source}"]

    def _fold_move_into_cmp(self, window: list[str]) -> list[str] | None:
        if len(window) < 2:
            return None

        first = window[0]
        second = window[1]

        mov_match = re.fullmatch(
            r"\s*mov\s+(eax|rax|al),\s*(r[a-z0-9]+|e[a-z0-9]+)",
            first.strip(),
        )
        if mov_match is None:
            return None

        acc = mov_match.group(1)
        source = mov_match.group(2)

        cmp_match = re.fullmatch(
            rf"\s*cmp\s+{re.escape(acc)},\s*(.+)",
            second.strip(),
        )
        if cmp_match is None:
            return None

        rhs = cmp_match.group(1)


        indent = second[: len(second) - len(second.lstrip())]

        return [f"{indent}cmp {source}, {rhs}"]

    def _fold_move_into_cmp_zero(self, window: list[str]) -> list[str] | None:
        if len(window) < 2:
            return None

        first = window[0]
        second = window[1]

        mov_match = re.fullmatch(
            r"\s*mov\s+(r\d+d|r1[0-5]d|r[89]d|eax|ebx|ecx|edx|esi|edi),\s*"
            r"(r\d+d|r1[0-5]d|r[89]d|eax|ebx|ecx|edx|esi|edi)",
            first.strip(),
        )
        if mov_match is None:
            return None

        dest = mov_match.group(1)
        source = mov_match.group(2)

        cmp_match = re.fullmatch(
            rf"\s*cmp\s+{re.escape(dest)},\s*0",
            second.strip(),
        )
        if cmp_match is None:
            return None

        indent = second[: len(second) - len(second.lstrip())]
        return [f"{indent}cmp {source}, 0"]

    def _fold_const_register_add(self, window: list[str]) -> list[str] | None:
        if len(window) < 3:
            return None

        first = window[0]
        second = window[1]
        third = window[2]

        first_match = re.fullmatch(
            r"\s*mov\s+(r\d+d|r1[0-5]d|r[89]d|eax|ebx|ecx|edx|esi|edi),\s*(-?\d+)",
            first.strip(),
        )
        if first_match is None:
            return None

        const_reg = first_match.group(1)
        const_value = int(first_match.group(2))

        second_match = re.fullmatch(
            r"\s*mov\s+(eax|ebx|ecx|edx|esi|edi|r\d+d|r1[0-5]d|r[89]d),\s*(-?\d+)",
            second.strip(),
        )
        if second_match is None:
            return None

        target_reg = second_match.group(1)
        target_value = int(second_match.group(2))

        third_match = re.fullmatch(
            rf"\s*(add|sub)\s+{re.escape(target_reg)},\s*{re.escape(const_reg)}",
            third.strip(),
        )
        if third_match is None:
            return None

        op = third_match.group(1)

        if op == "add":
            result_value = target_value + const_value
        else:
            result_value = target_value - const_value

        indent = second[: len(second) - len(second.lstrip())]
        return [f"{indent}mov {target_reg}, {result_value}"]

    def _fold_two_moves_into_cmp(self, window: list[str]) -> list[str] | None:
        if len(window) < 3:
            return None

        first = window[0]
        second = window[1]
        third = window[2]

        reg = (
            r"(rax|rbx|rcx|rdx|rsi|rdi|r8|r9|r10|r11|r12|r13|r14|r15|"
            r"eax|ebx|ecx|edx|esi|edi|r8d|r9d|r10d|r11d|r12d|r13d|r14d|r15d|"
            r"al|bl|cl|dl|sil|dil|r8b|r9b|r10b|r11b|r12b|r13b|r14b|r15b)"
        )

        first_match = re.fullmatch(
            rf"\s*mov\s+{reg},\s*{reg}",
            first.strip(),
        )
        second_match = re.fullmatch(
            rf"\s*mov\s+{reg},\s*{reg}",
            second.strip(),
        )

        if first_match is None or second_match is None:
            return None

        left_temp = first_match.group(1)
        left_source = first_match.group(2)

        right_temp = second_match.group(1)
        right_source = second_match.group(2)

        cmp_match = re.fullmatch(
            rf"\s*cmp\s+{re.escape(left_temp)},\s*{re.escape(right_temp)}",
            third.strip(),
        )
        if cmp_match is None:
            return None

        indent = third[: len(third) - len(third.lstrip())]
        return [f"{indent}cmp {left_source}, {right_source}"]