from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.ir.basic_block import IRFunction
from src.ir.ir_instructions import IROperandKind

class RegisterAllocator:
    def __init__(self) -> None:
        self.available_registers = ["rax", "rbx", "rcx", "rdx"]

    def allocate_temp_register(self) -> str:

        return "rax"



AVAILABLE_REGISTERS = [
    "r10",
    "r11",
    "r12",
    "r13",
]


@dataclass
class LiveRange:
    name: str
    start: int
    end: int
    register: Optional[str] = None
    spilled: bool = False
    stack_slot: Optional[int] = None


class LinearScanRegisterAllocator:
    def __init__(self, registers: Optional[List[str]] = None) -> None:
        self.registers = registers or AVAILABLE_REGISTERS
        self.live_ranges: Dict[str, LiveRange] = {}
        self.allocation: Dict[str, str] = {}
        self.spill_count = 0

    def allocate(self, function: IRFunction) -> Dict[str, str]:
        self.live_ranges = self._build_live_ranges(function)

        active: List[LiveRange] = []
        free_registers = list(self.registers)

        for live_range in sorted(self.live_ranges.values(), key=lambda r: r.start):
            self._expire_old_ranges(active, live_range.start, free_registers)

            if free_registers:
                reg = free_registers.pop(0)
                live_range.register = reg
                self.allocation[live_range.name] = reg
                active.append(live_range)
                active.sort(key=lambda r: r.end)
            else:
                self._spill(active, live_range)

        return dict(self.allocation)

    def _build_live_ranges(self, function: IRFunction) -> Dict[str, LiveRange]:
        ranges: Dict[str, LiveRange] = {}
        position = 0

        for block in function.blocks:
            for instr in block.instructions:
                operands = []

                if instr.dest is not None:
                    operands.append(instr.dest)

                operands.extend(instr.args)

                for operand in operands:
                    if operand.kind != IROperandKind.TEMP:
                        continue

                    name = str(operand.value)

                    if name not in ranges:
                        ranges[name] = LiveRange(name=name, start=position, end=position)
                    else:
                        ranges[name].end = position

                position += 1

        return ranges

    def _expire_old_ranges(self, active, current_start, free_registers):
        still_active = []

        for live_range in active:
            if live_range.end < current_start:
                if live_range.register:
                    free_registers.append(live_range.register)
            else:
                still_active.append(live_range)

        active[:] = sorted(still_active, key=lambda r: r.end)

    def _spill(self, active, current):
        spill_candidate = active[-1]

        if spill_candidate.end > current.end:
            current.register = spill_candidate.register
            self.allocation[current.name] = current.register

            spill_candidate.register = None
            spill_candidate.spilled = True
            spill_candidate.stack_slot = self.spill_count
            self.spill_count += 1

            self.allocation[spill_candidate.name] = f"spill{spill_candidate.stack_slot}"

            active[-1] = current
            active.sort(key=lambda r: r.end)
        else:
            current.spilled = True
            current.stack_slot = self.spill_count
            self.spill_count += 1
            self.allocation[current.name] = f"spill{current.stack_slot}"

    def get_live_ranges(self):
        return self.live_ranges

    def get_spill_count(self):
        return self.spill_count