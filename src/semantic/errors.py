from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class SemanticErrorKind(Enum):
    UNDECLARED_IDENTIFIER = auto()
    DUPLICATE_DECLARATION = auto()
    TYPE_MISMATCH = auto()
    ARGUMENT_COUNT_MISMATCH = auto()
    ARGUMENT_TYPE_MISMATCH = auto()
    INVALID_RETURN_TYPE = auto()
    INVALID_CONDITION_TYPE = auto()
    USE_BEFORE_DECLARATION = auto()
    INVALID_ASSIGNMENT_TARGET = auto()
    UNINITIALIZED_VARIABLE = auto()
    UNKNOWN_TYPE = auto()
    INVALID_MEMBER_ACCESS = auto()


@dataclass
class SemanticError:
    kind: SemanticErrorKind
    message: str
    line: int
    column: int
    file_name: str = "<input>"
    context: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    note: Optional[str] = None
    source_line: Optional[str] = None

    def format(self) -> str:
        lines = []

        header = f"semantic error: {self.message}"
        lines.append(header)
        lines.append(f"  --> {self.file_name}:{self.line}:{self.column}")

        if self.context:
            lines.append(f"  = context: {self.context}")

        if self.source_line is not None:
            lines.append("  |")
            lines.append(f"{self.line} | {self.source_line}")

            pointer_indent = max(self.column - 1, 0)
            lines.append(f"  | {' ' * pointer_indent}^")

        if self.expected is not None:
            lines.append(f"  = expected: {self.expected}")

        if self.actual is not None:
            lines.append(f"  = found: {self.actual}")

        if self.note:
            lines.append(f"  = note: {self.note}")

        return "\n".join(lines)

    def __str__(self) -> str:
        return self.format()


class SemanticErrorReporter:
    def __init__(self, file_name: str = "<input>") -> None:
        self.file_name = file_name
        self.errors: list[SemanticError] = []
        self._seen: set[tuple] = set()

    def add(
            self,
            kind: SemanticErrorKind,
            message: str,
            line: int,
            column: int,
            *,
            context: Optional[str] = None,
            expected: Optional[str] = None,
            actual: Optional[str] = None,
            note: Optional[str] = None,
            source_line: Optional[str] = None,
    ) -> None:
        key = (kind, message, line, column, self.file_name)

        if key in self._seen:
            return

        self._seen.add(key)
        self.errors.append(
            SemanticError(
                kind=kind,
                message=message,
                line=line,
                column=column,
                file_name=self.file_name,
                context=context,
                expected=expected,
                actual=actual,
                note=note,
                source_line=source_line,
            )
        )

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def extend(self, errors: list[SemanticError]) -> None:
        for error in errors:
            key = (error.kind, error.message, error.line, error.column, error.file_name)
            if key in self._seen:
                continue
            self._seen.add(key)
            self.errors.append(error)

    def clear(self) -> None:
        self.errors.clear()
        self._seen.clear()

    def get_errors(self) -> list[SemanticError]:
        return list(self.errors)

    def format_all(self) -> str:
        if not self.errors:
            return "No semantic errors."
        return "\n\n".join(error.format() for error in self.errors)

    def error_count(self) -> int:
        return len(self.errors)