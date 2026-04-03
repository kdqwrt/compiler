from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class SymbolKind(Enum):
    VARIABLE = auto()
    FUNCTION = auto()
    PARAMETER = auto()
    STRUCT = auto()
    FIELD = auto()


class ScopeKind(Enum):
    GLOBAL = auto()
    FUNCTION = auto()
    BLOCK = auto()
    STRUCT = auto()


@dataclass
class SymbolInfo:
    name: str
    type: Any = None
    kind: SymbolKind = SymbolKind.VARIABLE
    line: int = 0
    column: int = 0

    initialized: bool = False
    mutable: bool = True

    return_type: Any = None
    params: List["SymbolInfo"] = field(default_factory=list)
    fields: Dict[str, "SymbolInfo"] = field(default_factory=dict)

    stack_offset: Optional[int] = None
    size: Optional[int] = None
    alignment: Optional[int] = None

    scope_name: Optional[str] = None
    scope_depth: int = 0
    declaration_order: int = -1
    is_placeholder: bool = False

    def short_description(self) -> str:
        parts = [self.kind.name.lower(), self.name]

        if self.type is not None:
            parts.append(f"type={self.type}")

        if self.kind == SymbolKind.FUNCTION and self.return_type is not None:
            parts.append(f"returns={self.return_type}")

        if self.stack_offset is not None:
            parts.append(f"offset={self.stack_offset}")

        if self.size is not None:
            parts.append(f"size={self.size}")

        if self.alignment is not None:
            parts.append(f"align={self.alignment}")

        if self.scope_name is not None:
            parts.append(f"scope={self.scope_name}")

        parts.append(f"depth={self.scope_depth}")
        parts.append(f"order={self.declaration_order}")
        parts.append(f"declared at {self.line}:{self.column}")
        return ", ".join(parts)


@dataclass
class Scope:
    name: str
    kind: ScopeKind
    parent: Optional["Scope"] = None
    depth: int = 0
    symbols: Dict[str, SymbolInfo] = field(default_factory=dict)
    children: List["Scope"] = field(default_factory=list)
    declaration_counter: int = 0

    def insert(self, symbol: SymbolInfo) -> bool:
        if symbol.name in self.symbols:
            return False

        symbol.scope_name = self.name
        symbol.scope_depth = self.depth

        if symbol.declaration_order < 0:
            symbol.declaration_order = self.declaration_counter

        self.declaration_counter += 1
        self.symbols[symbol.name] = symbol
        return True

    def replace_local(self, name: str, symbol: SymbolInfo) -> bool:
        if name not in self.symbols:
            return False

        old_symbol = self.symbols[name]
        symbol.scope_name = self.name
        symbol.scope_depth = self.depth
        symbol.declaration_order = old_symbol.declaration_order
        self.symbols[name] = symbol
        return True

    def lookup_local(self, name: str) -> Optional[SymbolInfo]:
        return self.symbols.get(name)

    def lookup(self, name: str) -> Optional[SymbolInfo]:
        current: Optional[Scope] = self
        while current is not None:
            found = current.symbols.get(name)
            if found is not None:
                return found
            current = current.parent
        return None


class SymbolTable:
    def __init__(self) -> None:
        self.global_scope = Scope(
            name="global",
            kind=ScopeKind.GLOBAL,
            parent=None,
            depth=0,
        )
        self.current_scope = self.global_scope

    def enter_scope(self, name: str = "block", kind: ScopeKind = ScopeKind.BLOCK) -> Scope:
        new_scope = Scope(
            name=name,
            kind=kind,
            parent=self.current_scope,
            depth=self.current_scope.depth + 1,
        )
        self.current_scope.children.append(new_scope)
        self.current_scope = new_scope
        return new_scope

    def exit_scope(self) -> Scope:
        if self.current_scope.parent is None:
            raise RuntimeError("Cannot exit global scope")
        exited = self.current_scope
        self.current_scope = self.current_scope.parent
        return exited

    def insert(self, name: str, symbol_info: SymbolInfo) -> bool:
        symbol_info.name = name
        return self.current_scope.insert(symbol_info)

    def lookup(self, name: str) -> Optional[SymbolInfo]:
        return self.current_scope.lookup(name)

    def lookup_local(self, name: str) -> Optional[SymbolInfo]:
        return self.current_scope.lookup_local(name)

    def scope_path(self) -> List[str]:
        path = []
        current = self.current_scope
        while current is not None:
            path.append(current.name)
            current = current.parent
        return list(reversed(path))

    def replace_local(self, name: str, symbol_info: SymbolInfo) -> bool:
        symbol_info.name = name
        return self.current_scope.replace_local(name, symbol_info)

    def dump(self) -> str:
        lines: List[str] = []
        self._dump_scope(self.global_scope, lines, indent=0)
        return "\n".join(lines)

    def _dump_scope(self, scope: Scope, lines: List[str], indent: int) -> None:
        prefix = "  " * indent
        lines.append(
            f"{prefix}Scope '{scope.name}' ({scope.kind.name.lower()}, depth={scope.depth})"
        )

        if not scope.symbols:
            lines.append(f"{prefix}  <empty>")
        else:
            for symbol in scope.symbols.values():
                lines.append(f"{prefix}  - {symbol.short_description()}")

        for child in scope.children:
            self._dump_scope(child, lines, indent + 1)

    def dump_memory_layout(self) -> str:
        lines: List[str] = ["Memory Layout:"]
        self._dump_memory_layout_scope(self.global_scope, lines, indent=1)
        return "\n".join(lines)

    def _dump_memory_layout_scope(self, scope: Scope, lines: List[str], indent: int) -> None:
        prefix = "  " * indent
        lines.append(f"{prefix}Scope '{scope.name}' ({scope.kind.name.lower()}, depth={scope.depth})")

        has_layout = False
        for symbol in scope.symbols.values():
            if symbol.kind in {SymbolKind.VARIABLE, SymbolKind.PARAMETER, SymbolKind.FIELD}:
                has_layout = True
                lines.append(
                    f"{prefix}  - {symbol.name}: "
                    f"type={symbol.type}, offset={symbol.stack_offset}, "
                    f"size={symbol.size}, align={symbol.alignment}"
                )

        if not has_layout:
            lines.append(f"{prefix}  <no layout data>")

        for child in scope.children:
            self._dump_memory_layout_scope(child, lines, indent + 1)