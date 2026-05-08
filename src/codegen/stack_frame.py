from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class StackFrame:
    variable_offsets: Dict[str, int] = field(default_factory=dict)
    stack_size: int = 0

    def allocate_local(self, name: str, size: int = 8) -> int:
        if name in self.variable_offsets:
            return self.variable_offsets[name]

        self.stack_size += size
        self.variable_offsets[name] = self.stack_size
        return self.stack_size

    def get_offset(self, name: str) -> int:
        if name not in self.variable_offsets:
            raise KeyError(f"Variable '{name}' is not allocated in stack frame")
        return self.variable_offsets[name]

    def get_address(self, name: str) -> str:
        offset = self.get_offset(name)
        return f"[rbp-{offset}]"

    def aligned_stack_size(self) -> int:
        size = self.stack_size
        if size % 16 != 0:
            size += 16 - (size % 16)
        return size

    def get_stack_param_address(self, index_after_six: int) -> str:
        offset = 16 + index_after_six * 8
        return f"[rbp+{offset}]"