from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set

from src.ir.ir_instructions import IROpcode, IROperandKind
from src.ir.basic_block import IRProgram, IRFunction, BasicBlock
from src.ir.control_flow import find_unreachable_blocks

@dataclass
class IRValidationError:
    message: str
    function_name: str
    block_label: str

    def __str__(self) -> str:
        return f"[IR validation] {self.function_name}:{self.block_label}: {self.message}"


@dataclass
class IRValidationResult:
    errors: List[IRValidationError] = field(default_factory=list)

    def add(self, message: str, function_name: str, block_label: str) -> None:
        self.errors.append(IRValidationError(message, function_name, block_label))

    def is_valid(self) -> bool:
        return len(self.errors) == 0


class IRValidator:
    TERMINATORS = {
        IROpcode.JUMP,
        IROpcode.JUMP_IF,
        IROpcode.JUMP_IF_NOT,
        IROpcode.RETURN,
    }

    def __init__(self, program: IRProgram):
        self.program = program
        self.result = IRValidationResult()

    def validate(self) -> IRValidationResult:
        for function in self.program.functions:
            self._validate_function(function)
        return self.result

    def _validate_function(self, function: IRFunction) -> None:
        block_labels = {block.label for block in function.blocks}

        for block in function.blocks:
            self._validate_block_termination(function, block)
            self._validate_jump_targets(function, block, block_labels)
            self._validate_temporaries(function, block)
            self._validate_reachability(function)

    def _validate_block_termination(self, function: IRFunction, block: BasicBlock) -> None:
        if not block.instructions:
            self.result.add("empty basic block", function.name, block.label)
            return

        last_instr = block.instructions[-1]
        if last_instr.opcode not in self.TERMINATORS:
            self.result.add(
                f"basic block does not end with control flow or return (found {last_instr.opcode.name})",
                function.name,
                block.label,
            )

    def _validate_jump_targets(
        self,
        function: IRFunction,
        block: BasicBlock,
        block_labels: Set[str],
    ) -> None:
        for instr in block.instructions:
            if instr.opcode == IROpcode.JUMP:
                if len(instr.args) != 1:
                    self.result.add("JUMP must have exactly one target", function.name, block.label)
                    continue

                target = instr.args[0]
                if target.kind != IROperandKind.LABEL:
                    self.result.add("JUMP target must be a label", function.name, block.label)
                    continue

                if target.value not in block_labels:
                    self.result.add(
                        f"JUMP target '{target.value}' does not exist",
                        function.name,
                        block.label,
                    )

            elif instr.opcode == IROpcode.JUMP_IF:
                if len(instr.args) != 2:
                    self.result.add("JUMP_IF must have condition and label", function.name, block.label)
                    continue

                target = instr.args[1]
                if target.kind != IROperandKind.LABEL:
                    self.result.add("JUMP_IF target must be a label", function.name, block.label)
                    continue

                if target.value not in block_labels:
                    self.result.add(
                        f"JUMP_IF target '{target.value}' does not exist",
                        function.name,
                        block.label,
                    )

            elif instr.opcode == IROpcode.JUMP_IF_NOT:
                if len(instr.args) != 2:
                    self.result.add("JUMP_IF_NOT must have condition and label", function.name, block.label)
                    continue

                target = instr.args[1]
                if target.kind != IROperandKind.LABEL:
                    self.result.add("JUMP_IF_NOT target must be a label", function.name, block.label)
                    continue

                if target.value not in block_labels:
                    self.result.add(
                        f"JUMP_IF_NOT target '{target.value}' does not exist",
                        function.name,
                        block.label,
                    )

    def _validate_temporaries(self, function: IRFunction, block: BasicBlock) -> None:
        defined_temps: Set[str] = set()

        # собираем temps, определённые в предыдущих блоках,
        # чтобы не ругаться на обычный линейный CFG слишком агрессивно
        for other_block in function.blocks:
            if other_block == block:
                break
            for instr in other_block.instructions:
                if instr.dest is not None and instr.dest.kind == IROperandKind.TEMP:
                    defined_temps.add(instr.dest.value)

        for instr in block.instructions:
            for arg in instr.args:
                if arg.kind == IROperandKind.TEMP and arg.value not in defined_temps:
                    self.result.add(
                        f"use of undefined temporary '{arg.value}'",
                        function.name,
                        block.label,
                    )

            if instr.dest is not None and instr.dest.kind == IROperandKind.TEMP:
                defined_temps.add(instr.dest.value)

    def _validate_reachability(self, function: IRFunction) -> None:
        unreachable = find_unreachable_blocks(function)
        for label in unreachable:
            self.result.add(
                f"unreachable basic block '{label}'",
                function.name,
                label,
            )