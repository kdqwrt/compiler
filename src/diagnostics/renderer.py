from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json

class DiagnosticLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass
class Diagnostic:
    level: DiagnosticLevel
    category: str
    message: str
    file_name: str = "<input>"
    line: int | None = None
    column: int | None = None
    source_line: str | None = None
    context: str | None = None
    note: str | None = None
    suggestion: str | None = None


class DiagnosticRenderer:
    def __init__(self, use_color: bool = False):
        self.use_color = use_color

    def render(self, diagnostic: Diagnostic) -> str:
        location = self._format_location(diagnostic)
        header = (
            f"{diagnostic.level.value}[{diagnostic.category}]: "
            f"{diagnostic.message}"
        )

        lines = [header]

        if location:
            lines.append(f" --> {location}")

        if diagnostic.source_line and diagnostic.line is not None:
            lines.append("  |")
            lines.append(f"{diagnostic.line} | {diagnostic.source_line}")

            if diagnostic.column is not None and diagnostic.column > 0:
                pointer_offset = len(str(diagnostic.line)) + 3 + diagnostic.column - 1
                lines.append(" " * pointer_offset + "^")

        if diagnostic.context:
            lines.append(f"  = context: {diagnostic.context}")

        if diagnostic.note:
            lines.append(f"  = note: {diagnostic.note}")

        if diagnostic.suggestion:
            lines.append(f"  = help: {diagnostic.suggestion}")

        return "\n".join(lines)

    def render_many(self, diagnostics: list[Diagnostic]) -> str:
        return "\n\n".join(self.render(diagnostic) for diagnostic in diagnostics)

    def _format_location(self, diagnostic: Diagnostic) -> str:
        if diagnostic.line is None:
            return diagnostic.file_name

        if diagnostic.column is None:
            return f"{diagnostic.file_name}:{diagnostic.line}"

        return f"{diagnostic.file_name}:{diagnostic.line}:{diagnostic.column}"


    def render_json_many(self, diagnostics: list[Diagnostic]) -> str:
        payload = []

        for diagnostic in diagnostics:
            payload.append(
                {
                    "level": diagnostic.level.value,
                    "category": diagnostic.category,
                    "message": diagnostic.message,
                    "file": diagnostic.file_name,
                    "line": diagnostic.line,
                    "column": diagnostic.column,
                    "context": diagnostic.context,
                    "note": diagnostic.note,
                    "suggestion": diagnostic.suggestion,
                }
            )

        return json.dumps(payload, ensure_ascii=False, indent=2)


def from_semantic_error(error) -> Diagnostic:
    return Diagnostic(
        level=DiagnosticLevel.ERROR,
        category="SEMANTIC",
        message=getattr(error, "message", str(error)),
        file_name=getattr(error, "file_name", "<input>") or "<input>",
        line=getattr(error, "line", None),
        column=getattr(error, "column", None),
        source_line=getattr(error, "source_line", None),
        context=getattr(error, "context", None),
        note=getattr(error, "note", None),
        suggestion=_semantic_suggestion(error),
    )


def from_plain_error(error, category: str, file_name: str = "<input>") -> Diagnostic:
    return Diagnostic(
        level=DiagnosticLevel.ERROR,
        category=category,
        message=str(error),
        file_name=file_name,
    )


def _semantic_suggestion(error) -> str | None:
    kind = getattr(getattr(error, "kind", None), "name", "")

    suggestions = {
        "UNDECLARED_IDENTIFIER": "Declare the identifier before using it.",
        "UNINITIALIZED_VARIABLE": "Initialize the variable before reading it.",
        "TYPE_MISMATCH": "Check that both expressions have compatible types.",
        "ARGUMENT_COUNT_MISMATCH": "Check the number of arguments in the function call.",
        "ARGUMENT_TYPE_MISMATCH": "Check argument types in the function call.",
        "INVALID_RETURN_TYPE": "Check the function return type and returned expression.",
    }

    return suggestions.get(kind)