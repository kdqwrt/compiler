from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


class IROpcode(Enum):
    # Arithmetic
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    NEG = auto()

    # Logical
    AND = auto()
    OR = auto()
    NOT = auto()
    XOR = auto()

    # Comparison
    CMP_EQ = auto()
    CMP_NE = auto()
    CMP_LT = auto()
    CMP_LE = auto()
    CMP_GT = auto()
    CMP_GE = auto()

    # Memory / data movement
    LOAD = auto()
    STORE = auto()
    ALLOCA = auto()
    MOVE = auto()
    GEP = auto()
    MEMCPY = auto()
    ADDR_OF = auto()

    # Control flow
    LABEL = auto()
    JUMP = auto()
    JUMP_IF = auto()
    JUMP_IF_NOT = auto()
    PHI = auto()

    # Function
    PARAM = auto()
    CALL = auto()
    RETURN = auto()


class IROperandKind(Enum):
    TEMP = auto()       # t1, t2, ...
    VARIABLE = auto()   # x, y, ...
    LITERAL = auto()    # 42, 3.14, true, "hello"
    LABEL = auto()      # L1, entry, ...
    MEMORY = auto()     # [x], [t1], [t2+4]


@dataclass(frozen=True)
class IROperand:
    kind: IROperandKind
    value: Any
    type_name: Optional[str] = None

    def __str__(self) -> str:
        if self.kind == IROperandKind.MEMORY:
            return f"[{self.value}]"

        if self.kind == IROperandKind.LITERAL:
            if isinstance(self.value, str):
                if self.value.startswith("(") and self.value.endswith(")"):
                    return self.value
            if isinstance(self.value, bool):
                return "true" if self.value else "false"
            return str(self.value)

        return str(self.value)

    def to_json(self) -> dict:
        return {
            "kind": self.kind.name,
            "value": self.value,
            "type_name": self.type_name,
        }


@dataclass
class IRInstruction:
    opcode: IROpcode
    dest: Optional[IROperand] = None
    args: List[IROperand] = field(default_factory=list)
    comment: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None

    def is_terminator(self) -> bool:
        return self.opcode in {
            IROpcode.JUMP,
            IROpcode.JUMP_IF,
            IROpcode.JUMP_IF_NOT,
            IROpcode.RETURN,
        }

    def to_text(self) -> str:
        op = self.opcode.name

        # LABEL
        if self.opcode == IROpcode.LABEL:
            if not self.args:
                raise ValueError("LABEL instruction requires one label operand")
            return f"{self.args[0]}:"

        # dest = OPCODE args...
        if self.dest is not None:
            if self.args:
                base = f"{self.dest} = {op} " + ", ".join(str(arg) for arg in self.args)
            else:
                base = f"{self.dest} = {op}"
        else:
            if self.args:
                base = f"{op} " + ", ".join(str(arg) for arg in self.args)
            else:
                base = op

        if self.comment:
            base += f"    # {self.comment}"

        return base

    def to_json(self) -> dict:
        return {
            "opcode": self.opcode.name,
            "dest": self.dest.to_json() if self.dest else None,
            "args": [arg.to_json() for arg in self.args],
            "comment": self.comment,
            "line": self.line,
            "column": self.column,
            "filename": self.filename,
        }


def temp(name: str, type_name: Optional[str] = None) -> IROperand:
    return IROperand(IROperandKind.TEMP, name, type_name)


def var(name: str, type_name: Optional[str] = None) -> IROperand:
    return IROperand(IROperandKind.VARIABLE, name, type_name)


def lit(value: Any, type_name: Optional[str] = None) -> IROperand:
    return IROperand(IROperandKind.LITERAL, value, type_name)


def label(name: str) -> IROperand:
    return IROperand(IROperandKind.LABEL, name, None)


def mem(address: Any, type_name: Optional[str] = None) -> IROperand:
    return IROperand(IROperandKind.MEMORY, address, type_name)