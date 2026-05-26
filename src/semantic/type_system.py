from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


class TypeKind(Enum):
    INT = auto()
    FLOAT = auto()
    BOOL = auto()
    VOID = auto()
    STRING = auto()
    STRUCT = auto()
    FUNCTION = auto()
    ERROR = auto()
    ARRAY = auto()
    POINTER = auto()


@dataclass
class Type:
    kind: TypeKind
    name: Optional[str] = None
    return_type: Optional["Type"] = None
    param_types: List["Type"] = field(default_factory=list)
    fields: Dict[str, "Type"] = field(default_factory=dict)
    element_type: Optional["Type"] = None
    array_size: Optional[int] = None


    def is_numeric(self) -> bool:
        return self.kind in {TypeKind.INT, TypeKind.FLOAT}

    def is_bool(self) -> bool:
        return self.kind == TypeKind.BOOL

    def is_void(self) -> bool:
        return self.kind == TypeKind.VOID

    def is_struct(self) -> bool:
        return self.kind == TypeKind.STRUCT

    def is_function(self) -> bool:
        return self.kind == TypeKind.FUNCTION

    def is_array(self) -> bool:
        return self.kind == TypeKind.ARRAY

    def is_pointer(self) -> bool:
        return self.kind == TypeKind.POINTER

    def equals(self, other: "Type") -> bool:
        if not isinstance(other, Type):
            return False

        if self.kind != other.kind:
            return False

        if self.kind == TypeKind.STRUCT:
            return self.name == other.name

        if self.kind == TypeKind.FUNCTION:
            if self.return_type is None or other.return_type is None:
                return False

            if not self.return_type.equals(other.return_type):
                return False

            if len(self.param_types) != len(other.param_types):
                return False

            return all(a.equals(b) for a, b in zip(self.param_types, other.param_types))

        if self.kind == TypeKind.POINTER:
            if self.element_type is None or other.element_type is None:
                return False
            return self.element_type.equals(other.element_type)

        return True

    def is_assignable_from(self, other: "Type") -> bool:
        if not isinstance(other, Type):
            return False

        if self.kind == TypeKind.ERROR or other.kind == TypeKind.ERROR:
            return True

        if self.equals(other):
            return True

        # widening: int -> float
        if self.kind == TypeKind.FLOAT and other.kind == TypeKind.INT:
            return True

        return False

    def __str__(self) -> str:
        if self.kind == TypeKind.INT:
            return "int"
        if self.kind == TypeKind.FLOAT:
            return "float"
        if self.kind == TypeKind.BOOL:
            return "bool"
        if self.kind == TypeKind.VOID:
            return "void"
        if self.kind == TypeKind.STRING:
            return "string"
        if self.kind == TypeKind.ERROR:
            return "<error>"

        if self.kind == TypeKind.STRUCT:
            return self.name if self.name else "struct"

        if self.kind == TypeKind.FUNCTION:
            params = ", ".join(str(param) for param in self.param_types)
            ret = str(self.return_type) if self.return_type else "void"
            return f"fn({params}) -> {ret}"

        if self.kind == TypeKind.ARRAY:
            return f"{self.element_type}[{self.array_size}]"

        if self.kind == TypeKind.POINTER:
            return f"{self.element_type}*"


        return "<unknown>"




INT_TYPE = Type(TypeKind.INT)
FLOAT_TYPE = Type(TypeKind.FLOAT)
BOOL_TYPE = Type(TypeKind.BOOL)
VOID_TYPE = Type(TypeKind.VOID)
STRING_TYPE = Type(TypeKind.STRING)
ERROR_TYPE = Type(TypeKind.ERROR)

BUILTIN_TYPES = {
    "int": INT_TYPE,
    "float": FLOAT_TYPE,
    "bool": BOOL_TYPE,
    "void": VOID_TYPE,
    "string": STRING_TYPE,
}


def get_builtin_type(type_name: str) -> Optional[Type]:
    return BUILTIN_TYPES.get(type_name)


def make_struct_type(name: str, fields: Optional[Dict[str, Type]] = None) -> Type:
    return Type(
        kind=TypeKind.STRUCT,
        name=name,
        fields=fields or {}
    )

def make_array_type(element_type: Type, array_size: int) -> Type:
    return Type(
        kind=TypeKind.ARRAY,
        element_type=element_type,
        array_size=array_size,
    )

def make_pointer_type(element_type: Type) -> Type:
    return Type(
        kind=TypeKind.POINTER,
        element_type=element_type,
    )

def make_function_type(param_types: List[Type], return_type: Type) -> Type:
    return Type(
        kind=TypeKind.FUNCTION,
        param_types=list(param_types),
        return_type=return_type
    )


def are_types_compatible(expected: Type, actual: Type) -> bool:
    return expected.is_assignable_from(actual)


def infer_numeric_result_type(left: Type, right: Type) -> Type:
    if not left.is_numeric() or not right.is_numeric():
        return ERROR_TYPE

    if left.kind == TypeKind.FLOAT or right.kind == TypeKind.FLOAT:
        return FLOAT_TYPE

    return INT_TYPE


def get_type_size(t: Type) -> int:
    if t == INT_TYPE:
        return 4
    if t == FLOAT_TYPE:
        return 8
    if t == BOOL_TYPE:
        return 1
    if t == STRING_TYPE:
        return 8

    if t.is_array():
        return get_type_size(t.element_type) * int(t.array_size)

    if t.is_struct():
        total_size = 0
        max_alignment = 1

        for field_name, field_type in t.fields.items():
            field_size = get_type_size(field_type)
            field_alignment = get_type_alignment(field_type)

            if total_size % field_alignment != 0:
                total_size += field_alignment - (total_size % field_alignment)

            total_size += field_size
            max_alignment = max(max_alignment, field_alignment)

        if total_size % max_alignment != 0:
            total_size += max_alignment - (total_size % max_alignment)

        return total_size

    if t.is_pointer():
        return 8

    return 0


def get_type_alignment(t: Type) -> int:
    if t == BOOL_TYPE:
        return 1
    if t == INT_TYPE:
        return 4
    if t == FLOAT_TYPE:
        return 8
    if t == STRING_TYPE:
        return 8

    if t.is_array():
        return get_type_alignment(t.element_type)

    if t.is_struct():
        max_alignment = 1
        for field_type in t.fields.values():
            field_alignment = get_type_alignment(field_type)
            max_alignment = max(max_alignment, field_alignment)
        return max_alignment

    if t.is_pointer():
        return 8

    return 1