from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.ir.ir_instructions import IRInstruction


@dataclass
class BasicBlock:
    label: str
    instructions: List[IRInstruction] = field(default_factory=list)
    successors: List[str] = field(default_factory=list)
    predecessors: List[str] = field(default_factory=list)

    def add_instruction(self, instruction: IRInstruction) -> None:
        self.instructions.append(instruction)

    def add_successor(self, label: str) -> None:
        if label not in self.successors:
            self.successors.append(label)

    def add_predecessor(self, label: str) -> None:
        if label not in self.predecessors:
            self.predecessors.append(label)

    def is_terminated(self) -> bool:
        if not self.instructions:
            return False
        return self.instructions[-1].is_terminator()

    def to_text(self, indent: str = "  ") -> str:
        lines = [f"{indent}{self.label}:"]
        if not self.instructions:
            lines.append(f"{indent}  <empty>")
            return "\n".join(lines)

        for instr in self.instructions:
            lines.append(f"{indent}  {instr.to_text()}")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "label": self.label,
            "instructions": [instr.to_json() for instr in self.instructions],
            "successors": list(self.successors),
            "predecessors": list(self.predecessors),
        }


@dataclass
class IRFunction:
    name: str
    return_type: str
    params: List[str] = field(default_factory=list)
    param_types: List[str] = field(default_factory=list)
    local_variables: List[str] = field(default_factory=list)
    blocks: List[BasicBlock] = field(default_factory=list)
    variable_map: Dict[str, str] = field(default_factory=dict)

    temp_counter: int = 0
    label_counter: int = 0

    def new_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def new_label(self, prefix: str = "L") -> str:
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"

    def add_block(self, block: BasicBlock) -> None:
        if self.get_block(block.label) is not None:
            raise ValueError(f"Block '{block.label}' already exists in function '{self.name}'")
        self.blocks.append(block)

    def get_block(self, label: str) -> Optional[BasicBlock]:
        for block in self.blocks:
            if block.label == label:
                return block
        return None

    def ensure_block(self, label: str) -> BasicBlock:
        block = self.get_block(label)
        if block is None:
            block = BasicBlock(label)
            self.blocks.append(block)
        return block

    def add_edge(self, from_label: str, to_label: str) -> None:
        from_block = self.ensure_block(from_label)
        to_block = self.ensure_block(to_label)

        from_block.add_successor(to_label)
        to_block.add_predecessor(from_label)

    def to_text(self) -> str:
        params_repr = ", ".join(
            f"{ptype} {pname}" if i < len(self.param_types) else pname
            for i, pname in enumerate(self.params)
            for ptype in [self.param_types[i]] if i < len(self.param_types)
        )

        if not params_repr and self.params:
            params_repr = ", ".join(self.params)

        lines = [f"function {self.name}: {self.return_type} ({params_repr})"]

        if self.variable_map:
            lines.append("  # Variable map:")
            for src_name, ir_name in self.variable_map.items():
                lines.append(f"  #   {src_name} -> {ir_name}")

        if self.local_variables:
            lines.append("  # Locals: " + ", ".join(self.local_variables))

        for block in self.blocks:
            lines.append(block.to_text())

        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "return_type": self.return_type,
            "params": list(self.params),
            "param_types": list(self.param_types),
            "local_variables": list(self.local_variables),
            "variable_map": dict(self.variable_map),
            "temp_counter": self.temp_counter,
            "label_counter": self.label_counter,
            "blocks": [block.to_json() for block in self.blocks],
        }


@dataclass
class IRProgram:
    functions: List[IRFunction] = field(default_factory=list)

    def add_function(self, function: IRFunction) -> None:
        if self.get_function(function.name) is not None:
            raise ValueError(f"Function '{function.name}' already exists in IR program")
        self.functions.append(function)

    def get_function(self, name: str) -> Optional[IRFunction]:
        for function in self.functions:
            if function.name == name:
                return function
        return None

    def to_text(self) -> str:
        if not self.functions:
            return "# Empty IR program"
        return "\n\n".join(function.to_text() for function in self.functions)

    def to_json(self) -> dict:
        return {
            "functions": [function.to_json() for function in self.functions],
        }

    def get_statistics(self) -> dict:
        instruction_count = 0
        block_count = 0
        temp_count = 0

        for function in self.functions:
            block_count += len(function.blocks)
            temp_count += function.temp_counter
            for block in function.blocks:
                instruction_count += len(block.instructions)

        return {
            "functions": len(self.functions),
            "basic_blocks": block_count,
            "instructions": instruction_count,
            "temporaries": temp_count,
        }