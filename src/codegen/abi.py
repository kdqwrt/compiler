from __future__ import annotations

INT_ARG_REGISTERS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
FLOAT_ARG_REGISTERS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]

RETURN_INT_REGISTER = "rax"
RETURN_FLOAT_REGISTER = "xmm0"

CALLEE_SAVED = ["rbx", "rbp", "r12", "r13", "r14", "r15"]
CALLER_SAVED = ["rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"]