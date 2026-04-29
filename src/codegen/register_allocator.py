from __future__ import annotations


class RegisterAllocator:
    def __init__(self) -> None:
        self.available_registers = ["rax", "rbx", "rcx", "rdx"]

    def allocate_temp_register(self) -> str:

        return "rax"