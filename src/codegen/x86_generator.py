from __future__ import annotations

from typing import List, Optional

from src.ir.basic_block import IRProgram, IRFunction
from src.ir.ir_instructions import IROpcode, IROperandKind
from src.codegen.stack_frame import StackFrame
from src.codegen.abi import INT_ARG_REGISTERS, RETURN_FLOAT_REGISTER
from src.codegen.register_allocator import LinearScanRegisterAllocator
from src.codegen.peephole_optimizer import PeepholeOptimizer


class X86Generator:
    def __init__(self, use_register_allocation: bool = False) -> None:
        self.lines: List[str] = []
        self.current_function: Optional[IRFunction] = None
        self.stack_frame: Optional[StackFrame] = None
        self.pending_params: dict[int, object] = {}
        self.skip_next_phi_store: bool = False

        self.use_register_allocation = use_register_allocation
        self.register_allocation: dict[str, str] = {}
        self.used_allocated_registers: set[str] = set()
        self.global_variable_names: set[str] = set()
        self.float_constants: dict[str, str] = {}
        self.float_counter = 0
        self.string_constants: dict[str, str] = {}
        self.string_counter = 0
        self.temp_compare_sources: dict[str, object] = {}
        self.variable_registers: dict[str, str] = {}

    def generate(self, program: IRProgram) -> str:
        self.lines = []
        self.float_constants = {}
        self.float_counter = 0
        self.string_constants = {}
        self.string_counter = 0

        self.global_variable_names = {
            var.name for var in getattr(program, "global_variables", [])
        }

        self._emit_global_sections(program)

        self._collect_float_constants(program)
        self._collect_string_constants(program)
        self._emit_rodata_section()

        self.lines.append("section .text")
        self.lines.append("")
        self.lines.append("extern print_int")
        self.lines.append("extern print_string")
        self.lines.append("extern read_int")
        self.lines.append("extern printf")
        self.lines.append("extern scanf")
        self.lines.append("extern malloc")
        self.lines.append("extern free")
        self.lines.append("extern strlen")
        self.lines.append("extern pow")

        for function in program.functions:
            self._gen_function(function)

        self.lines = PeepholeOptimizer(window_size=5).optimize(self.lines)

        self.lines.append("")
        self.lines.append("section .note.GNU-stack noalloc noexec nowrite progbits")

        return "\n".join(self.lines)

    def _emit_global_sections(self, program: IRProgram) -> None:
        globals_ = getattr(program, "global_variables", [])

        initialized = [
            var for var in globals_
            if getattr(var, "initializer", None) is not None
        ]

        uninitialized = [
            var for var in globals_
            if getattr(var, "initializer", None) is None
        ]

        if initialized:
            self.lines.append("section .data")
            for var in initialized:
                self.lines.append(f"global {var.name}")

                if isinstance(var.initializer, list):
                    values = ", ".join(str(value) for value in var.initializer)
                    self.lines.append(f"{var.name}: dd {values}")
                else:
                    self.lines.append(f"{var.name}: dq {var.initializer}")

            self.lines.append("")

        if uninitialized:
            self.lines.append("section .bss")
            for var in uninitialized:
                self.lines.append(f"global {var.name}")
                if "[" in getattr(var, "type_name", ""):
                    array_size = int(var.type_name.split("[", 1)[1].split("]", 1)[0])
                    self.lines.append(f"{var.name}: resd {array_size}")
                else:
                    self.lines.append(f"{var.name}: resq 1")
            self.lines.append("")


    def _collect_float_constants(self, program: IRProgram) -> None:
        for function in program.functions:
            for block in function.blocks:
                for instr in block.instructions:
                    for operand in ([instr.dest] if instr.dest is not None else []) + list(instr.args):
                        if (
                            operand is not None
                            and operand.kind == IROperandKind.LITERAL
                            and operand.type_name == "float"
                            and operand.value is not None
                        ):
                            self._float_label(float(operand.value))

    def _collect_string_constants(self, program: IRProgram) -> None:
        for function in program.functions:
            for block in function.blocks:
                for instr in block.instructions:
                    operands = []
                    if instr.dest is not None:
                        operands.append(instr.dest)
                    operands.extend(instr.args)

                    for operand in operands:
                        if (
                                operand is not None
                                and operand.kind == IROperandKind.LITERAL
                                and operand.type_name == "string"
                                and isinstance(operand.value, str)
                        ):
                            self._string_label(operand.value)

    def _string_label(self, value: str) -> str:
        if value not in self.string_constants:
            label = f"__str_{self.string_counter}"
            self.string_counter += 1
            self.string_constants[value] = label

        return self.string_constants[value]

    def _escape_string_bytes(self, value: str) -> str:
        parts = []

        for ch in value:
            code = ord(ch)

            if ch == "\n":
                parts.append("10")
            elif ch == "\t":
                parts.append("9")
            elif ch == "\r":
                parts.append("13")
            elif ch == "\0":
                parts.append("0")
            elif ch == '"':
                parts.append("'\"'")
            elif ch == "\\":
                parts.append("'\\\\'")
            elif 32 <= code <= 126:
                parts.append(f"'{ch}'")
            else:
                parts.append(str(code))

        parts.append("0")
        return ", ".join(parts)

    def _float_label(self, value: float) -> str:
        key = repr(float(value))

        if key not in self.float_constants:
            label = f"__float_const_{self.float_counter}"
            self.float_counter += 1
            self.float_constants[key] = label

        return self.float_constants[key]

    def _emit_rodata_section(self) -> None:
        if not self.float_constants and not self.string_constants:
            return

        self.lines.append("section .rodata")

        for value, label in self.float_constants.items():
            self.lines.append(f"{label}: dq {value}")

        for value, label in self.string_constants.items():
            encoded = self._escape_string_bytes(value)
            self.lines.append(f"{label}: db {encoded}")

        self.lines.append("")


    def _gen_function(self, function: IRFunction) -> None:
        self.current_function = function
        self.stack_frame = StackFrame()
        self.temp_compare_sources = {}
        self.variable_registers = {}

        if self.use_register_allocation:
            allocator = LinearScanRegisterAllocator()
            self.register_allocation = allocator.allocate(function)
            self.used_allocated_registers = {
                location
                for location in self.register_allocation.values()
                if not location.startswith("spill")
            }
        else:
            self.register_allocation = {}
            self.used_allocated_registers = set()

        if self.use_register_allocation:
            self.variable_registers = self._allocate_variable_registers(function)

        self._reserve_function_storage(function)

        self.lines.append("")
        self.lines.append(f"global {function.name}")
        self.lines.append(f"{function.name}:")

        self._emit_prologue()
        self._move_params_to_stack(function)

        for block in function.blocks:
            self.lines.append(f".{function.name}_{block.label}:")

            i = 0
            while i < len(block.instructions):
                instr = block.instructions[i]
                next_instr = block.instructions[i + 1] if i + 1 < len(block.instructions) else None

                if self._can_skip_compare_materialization(instr, next_instr):
                    self.temp_compare_sources[str(instr.dest.value)] = instr
                    i += 1
                    continue

                self._gen_instruction(instr)
                i += 1

        self.current_function = None
        self.stack_frame = None

    def _reserve_function_storage(self, function: IRFunction) -> None:
        for param_name in function.params:
            self.stack_frame.allocate_local(param_name, 8)

        alloca_sizes = {}

        for block in function.blocks:
            for instr in block.instructions:
                if (
                        instr.opcode == IROpcode.ALLOCA
                        and instr.dest is not None
                        and instr.dest.kind == IROperandKind.VARIABLE
                        and instr.args
                        and instr.args[0].kind == IROperandKind.LITERAL
                ):
                    alloca_sizes[instr.dest.value] = int(instr.args[0].value)

        for local_name in function.local_variables:
            self.stack_frame.allocate_local(
                local_name,
                alloca_sizes.get(local_name, 8)
            )

        for block in function.blocks:
            for instr in block.instructions:
                if instr.dest is not None and instr.dest.kind == IROperandKind.TEMP:
                    self.stack_frame.allocate_local(
                        instr.dest.value,
                        self._type_size(instr.dest.type_name),
                    )

                for arg in instr.args:
                    if arg.kind == IROperandKind.TEMP:
                        self.stack_frame.allocate_local(arg.value, 8)


    def _infer_variable_type(self, function: IRFunction, name: str) -> str | None:
        if name in function.params:
            index = function.params.index(name)
            if index < len(function.param_types):
                return function.param_types[index]

        for block in function.blocks:
            for instr in block.instructions:
                operands = []
                if instr.dest is not None:
                    operands.append(instr.dest)
                operands.extend(instr.args)

                for operand in operands:
                    if (
                        operand.kind == IROperandKind.VARIABLE
                        and operand.value == name
                        and operand.type_name is not None
                    ):
                        return operand.type_name

        return None

    def _allocate_variable_registers(self, function: IRFunction) -> dict[str, str]:
        registers = ["r12", "r13"]
        result: dict[str, str] = {}

        candidates = list(function.params) + list(function.local_variables)

        for name in candidates:
            if name in self.global_variable_names:
                continue

            var_type = self._infer_variable_type(function, name)

            if var_type not in {"int", "bool"}:
                continue

            if not registers:
                break

            result[name] = registers.pop(0)

        return result

    def _callee_saved_registers_to_save(self) -> list[str]:
        used = set(self.variable_registers.values())
        return [reg for reg in ["r12", "r13"] if reg in used]

    def _saved_register_address(self, index: int) -> str:
        offset = self.stack_frame.aligned_stack_size() + 8 * (index + 1)
        return f"[rbp-{offset}]"

    def _total_stack_size(self) -> int:
        local_size = self.stack_frame.aligned_stack_size()
        save_size = 8 * len(self._callee_saved_registers_to_save())
        total = local_size + save_size

        if total % 16 != 0:
            total += 16 - (total % 16)

        return total

    def _emit_prologue(self) -> None:
        self.lines.append("    push rbp")
        self.lines.append("    mov rbp, rsp")

        stack_size = self._total_stack_size()
        if stack_size > 0:
            self.lines.append(f"    sub rsp, {stack_size}")

        for index, reg in enumerate(self._callee_saved_registers_to_save()):
            self.lines.append(f"    mov qword {self._saved_register_address(index)}, {reg}")

    def _emit_epilogue(self) -> None:
        for index, reg in enumerate(self._callee_saved_registers_to_save()):
            self.lines.append(f"    mov {reg}, qword {self._saved_register_address(index)}")

        self.lines.append("    mov rsp, rbp")
        self.lines.append("    pop rbp")
        self.lines.append("    ret")

    def _var_addr(self, name: str) -> str:
        if name in self.global_variable_names:
            return f"[rel {name}]"

        return self.stack_frame.get_address(name)

    def _type_size(self, type_name: str | None) -> int:
        if type_name == "bool":
            return 1
        if type_name == "int":
            return 4
        return 8

    def _mem_prefix(self, type_name: str | None) -> str:
        if type_name == "int":
            return "dword"
        if type_name == "bool":
            return "byte"
        return "qword"

    def _reg_for_type(self, reg: str, type_name: str | None) -> str:
        if type_name == "bool":
            reg8 = {
                "rax": "al",
                "rbx": "bl",
                "rcx": "cl",
                "rdx": "dl",
                "rsi": "sil",
                "rdi": "dil",
                "r8": "r8b",
                "r9": "r9b",
                "r10": "r10b",
                "r11": "r11b",
                "r12": "r12b",
                "r13": "r13b",
            }
            return reg8.get(reg, reg)

        if type_name == "int":
            reg32 = {
                "rax": "eax",
                "rbx": "ebx",
                "rcx": "ecx",
                "rdx": "edx",
                "rsi": "esi",
                "rdi": "edi",
                "r8": "r8d",
                "r9": "r9d",
                "r10": "r10d",
                "r11": "r11d",
                "r12": "r12d",
                "r13": "r13d",
            }
            return reg32.get(reg, reg)

        return reg

    def _acc_reg(self, type_name: str | None) -> str:
        if type_name == "int":
            return "eax"
        if type_name == "bool":
            return "al"
        return "rax"

    def _var_location(self, name: str, type_name: str | None = None) -> str:
        if name in self.variable_registers:
            return self._reg_for_type(self.variable_registers[name], type_name)

        return f"{self._mem_prefix(type_name)} {self._var_addr(name)}"

    def _load_float_literal_to_xmm0(self, value) -> None:
        label = self._float_label(float(value))
        self.lines.append(f"    movsd xmm0, qword [rel {label}]")

    def _load_float_operand_to_xmm0(self, operand) -> None:
        if operand.kind == IROperandKind.LITERAL:
            if operand.type_name == "int":
                self.lines.append(f"    mov eax, {operand.value}")
                self.lines.append("    cvtsi2sd xmm0, eax")
            else:
                self._load_float_literal_to_xmm0(operand.value)
            return

        if operand.kind == IROperandKind.TEMP:
            if operand.type_name == "int":
                self.lines.append(
                    f"    mov eax, {self._temp_location(operand.value, operand.type_name)}"
                )
                self.lines.append("    cvtsi2sd xmm0, eax")
            else:
                self.lines.append(
                    f"    movsd xmm0, {self._temp_location(operand.value, operand.type_name)}"
                )
            return

        if operand.kind == IROperandKind.VARIABLE:
            if operand.type_name == "int":
                self.lines.append(
                    f"    mov eax, {self._var_location(operand.value, operand.type_name)}"
                )
                self.lines.append("    cvtsi2sd xmm0, eax")
            else:
                self.lines.append(
                    f"    movsd xmm0, {self._var_location(operand.value, operand.type_name)}"
                )
            return

        self.lines.append(f"    ; unsupported float operand load: {operand}")


    def _move_float_operand_to_xmm(self, operand, xmm_reg: str) -> None:
        if operand.kind == IROperandKind.LITERAL:
            if operand.type_name == "int":
                self.lines.append(f"    mov eax, {operand.value}")
                self.lines.append(f"    cvtsi2sd {xmm_reg}, eax")
            else:
                label = self._float_label(float(operand.value))
                self.lines.append(f"    movsd {xmm_reg}, qword [rel {label}]")
            return

        if operand.kind == IROperandKind.TEMP:
            if operand.type_name == "int":
                self.lines.append(
                    f"    mov eax, {self._temp_location(operand.value, operand.type_name)}"
                )
                self.lines.append(f"    cvtsi2sd {xmm_reg}, eax")
            else:
                self.lines.append(
                    f"    movsd {xmm_reg}, {self._temp_location(operand.value, operand.type_name)}"
                )
            return

        if operand.kind == IROperandKind.VARIABLE:
            if operand.type_name == "int":
                self.lines.append(
                    f"    mov eax, {self._var_location(operand.value, operand.type_name)}"
                )
                self.lines.append(f"    cvtsi2sd {xmm_reg}, eax")
            else:
                self.lines.append(
                    f"    movsd {xmm_reg}, {self._var_location(operand.value, operand.type_name)}"
                )
            return

        self.lines.append(f"    ; unsupported float arg for {xmm_reg}: {operand}")

    def _float_rhs_operand(self, operand) -> str:
        if operand.type_name == "int":
            self._move_operand_to_register(operand, "r10")
            self.lines.append("    cvtsi2sd xmm1, r10d")
            return "xmm1"

        if operand.kind == IROperandKind.LITERAL:
            label = self._float_label(float(operand.value))
            return f"qword [rel {label}]"

        if operand.kind == IROperandKind.TEMP:
            return self._temp_location(operand.value, operand.type_name)

        if operand.kind == IROperandKind.VARIABLE:
            return self._var_location(operand.value, operand.type_name)

        return "xmm1"

    def _full_acc_reg(self, type_name: str | None) -> str:
        if type_name in {"int", "bool"}:
            return "eax"
        return "rax"

    def _can_skip_compare_materialization(self, instr, next_instr) -> bool:
        if instr.opcode not in {
            IROpcode.CMP_EQ,
            IROpcode.CMP_NE,
            IROpcode.CMP_LT,
            IROpcode.CMP_LE,
            IROpcode.CMP_GT,
            IROpcode.CMP_GE,
        }:
            return False

        if instr.dest is None or instr.dest.kind != IROperandKind.TEMP:
            return False

        if next_instr is None:
            return False

        if next_instr.opcode not in {IROpcode.JUMP_IF, IROpcode.JUMP_IF_NOT}:
            return False

        if not next_instr.args:
            return False

        cond = next_instr.args[0]

        return (
                cond.kind == IROperandKind.TEMP
                and str(cond.value) == str(instr.dest.value)
        )


    def _gen_instruction(self, instr) -> None:
        if instr.opcode == IROpcode.PHI:
            self.skip_next_phi_store = True
            self.lines.append(f"    ; phi skipped: {instr.to_text()}")
            return

        if (
            self.skip_next_phi_store
            and instr.opcode == IROpcode.STORE
            and len(instr.args) >= 2
            and instr.args[1].kind == IROperandKind.TEMP
        ):
            self.skip_next_phi_store = False
            self.lines.append(f"    ; phi store skipped: {instr.to_text()}")
            return

        self.skip_next_phi_store = False

        if instr.opcode == IROpcode.ALLOCA:
            # ALLOCA уже отражён в stack_frame, отдельный asm не нужен
            self.lines.append(f"    ; {instr.to_text()}")
            return

        if instr.opcode == IROpcode.MOVE:
            self._gen_move(instr)
            return

        if instr.opcode == IROpcode.STORE:
            self._gen_store(instr)
            return

        if instr.opcode == IROpcode.GEP:
            self._gen_gep(instr)
            return

        if instr.opcode == IROpcode.MEMCPY:
            self._gen_memcpy(instr)
            return

        if instr.opcode == IROpcode.ADDR_OF:
            self._gen_addr_of(instr)
            return

        if instr.opcode == IROpcode.LOAD:
            self._gen_load(instr)
            return

        if instr.opcode in {
            IROpcode.ADD,
            IROpcode.SUB,
            IROpcode.MUL,
            IROpcode.DIV,
            IROpcode.MOD,
            IROpcode.AND,
            IROpcode.OR,
            IROpcode.XOR,
        }:
            self._gen_binary_arithmetic(instr)
            return

        if instr.opcode == IROpcode.NOT:
            self._gen_not(instr)
            return

        if instr.opcode in {
            IROpcode.CMP_EQ,
            IROpcode.CMP_NE,
            IROpcode.CMP_LT,
            IROpcode.CMP_LE,
            IROpcode.CMP_GT,
            IROpcode.CMP_GE,
        }:
            self._gen_compare(instr)
            return

        if instr.opcode == IROpcode.JUMP:
            self._gen_jump(instr)
            return

        if instr.opcode == IROpcode.JUMP_IF_NOT:
            self._gen_jump_if_not(instr)
            return

        if instr.opcode == IROpcode.JUMP_IF:
            self._gen_jump_if(instr)
            return

        if instr.opcode == IROpcode.PARAM:
            self._gen_param(instr)
            return

        if instr.opcode == IROpcode.CALL:
            self._gen_call(instr)
            return

        if instr.opcode == IROpcode.RETURN:
            self._gen_return(instr)
            return

        # Пока всё остальное комментируем
        self.lines.append(f"    ; unsupported IR: {instr.to_text()}")

    def _gen_store(self, instr) -> None:
        target = instr.args[0]
        value = instr.args[1]

        if target.kind == IROperandKind.VARIABLE and target.type_name == "float":
            self._load_float_operand_to_xmm0(value)
            self.lines.append(
                f"    movsd {self._var_location(target.value, target.type_name)}, xmm0"
            )
            return

        # STORE variable, literal
        if target.kind == IROperandKind.VARIABLE and value.kind == IROperandKind.LITERAL:
            addr = self._var_addr(target.value)
            self.lines.append(f"    mov {self._var_location(target.value, target.type_name)}, {value.value}")
            return

        # STORE variable, temp
        if target.kind == IROperandKind.VARIABLE and value.kind == IROperandKind.TEMP:
            acc = self._acc_reg(value.type_name)
            self.lines.append(f"    mov {acc}, {self._temp_location(value.value, value.type_name)}")
            self.lines.append(f"    mov {self._var_location(target.value, target.type_name)}, {acc}")
            return

        if target.kind == IROperandKind.MEMORY:
            self.lines.append(
                f"    mov r11, {self._temp_location(target.value, 'ptr')}"
            )

            if value.kind == IROperandKind.LITERAL:
                self.lines.append(f"    mov dword [r11], {value.value}")
                return

            if value.kind == IROperandKind.TEMP:
                self.lines.append(
                    f"    mov eax, {self._temp_location(value.value, value.type_name)}"
                )
                self.lines.append("    mov dword [r11], eax")
                return


        self.lines.append(f"    ; unsupported STORE: {instr.to_text()}")

    def _gen_move(self, instr) -> None:
        if instr.dest is None or not instr.args:
            self.lines.append(f"    ; unsupported MOVE: {instr.to_text()}")
            return

        dest = instr.dest
        value = instr.args[0]

        if dest.kind == IROperandKind.TEMP:
            dest_location = self._temp_location(dest.value, dest.type_name)
        elif dest.kind == IROperandKind.VARIABLE:
            dest_location = self._var_location(dest.value, dest.type_name)
        else:
            self.lines.append(f"    ; unsupported MOVE destination: {instr.to_text()}")
            return


        if dest.type_name == "float":
            self._load_float_operand_to_xmm0(value)
            self.lines.append(f"    movsd {dest_location}, xmm0")
            return


        if value.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov {dest_location}, {value.value}")
            return

        if value.kind == IROperandKind.TEMP:
            acc = self._acc_reg(value.type_name)
            self.lines.append(f"    mov {acc}, {self._temp_location(value.value, value.type_name)}")
            self.lines.append(f"    mov {dest_location}, {acc}")
            return

        if value.kind == IROperandKind.VARIABLE:
            acc = self._acc_reg(value.type_name)
            self.lines.append(f"    mov {acc}, {self._var_location(value.value, value.type_name)}")
            self.lines.append(f"    mov {dest_location}, {acc}")
            return

        self.lines.append(f"    ; unsupported MOVE value: {instr.to_text()}")

    def _gen_gep(self, instr) -> None:
        base = instr.args[0]
        offset = instr.args[1]
        dest = instr.dest

        # base address
        if base.kind != IROperandKind.VARIABLE:
            self.lines.append(f"    ; unsupported GEP base: {instr.to_text()}")
            return

        # offset -> r10
        if offset.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov r10, {offset.value}")
        elif offset.kind == IROperandKind.TEMP:
            reg = self._reg_for_type("r10", offset.type_name)
            self.lines.append(
                f"    mov {reg}, {self._temp_location(offset.value, offset.type_name)}"
            )
            if reg == "r10d":
                self.lines.append("    movsxd r10, r10d")

        else:
            self.lines.append(f"    ; unsupported GEP offset: {instr.to_text()}")
            return

        # lea base
        if base.value in self.global_variable_names:
            self.lines.append(f"    lea r11, [rel {base.value}]")
        else:
            addr = self._var_addr(base.value)

            if (
                    base.value in self.current_function.params
                    and base.type_name
                    and "[" in base.type_name
                    and "]" in base.type_name
            ):
                self.lines.append(f"    mov r11, qword {addr}")
            else:
                self.lines.append(f"    lea r11, {addr}")

        self.lines.append("    add r11, r10")

        self.lines.append(
            f"    mov {self._temp_location(dest.value, dest.type_name)}, r11"
        )

    def _gen_memcpy(self, instr) -> None:
        dst = instr.args[0]
        src = instr.args[1]
        size = instr.args[2]

        # destination
        if dst.value in self.global_variable_names:
            self.lines.append(f"    lea rdi, [rel {dst.value}]")
        else:
            self.lines.append(
                f"    lea rdi, {self._var_addr(dst.value)}"
            )

        # source
        if src.value in self.global_variable_names:
            self.lines.append(f"    lea rsi, [rel {src.value}]")
        else:
            self.lines.append(
                f"    lea rsi, {self._var_addr(src.value)}"
            )

        # bytes
        self.lines.append(
            f"    mov rcx, {size.value // 4}"
        )

        self.lines.append("    rep movsd")

    def _gen_addr_of(self, instr) -> None:
        dest = instr.dest
        source = instr.args[0]

        if source.kind != IROperandKind.VARIABLE:
            self.lines.append(f"    ; unsupported ADDR_OF: {instr.to_text()}")
            return

        if source.value in self.global_variable_names:
            self.lines.append(f"    lea rax, [rel {source.value}]")
        else:
            self.lines.append(f"    lea rax, {self._var_addr(source.value)}")

        self.lines.append(
            f"    mov {self._temp_location(dest.value, dest.type_name)}, rax"
        )


    def _gen_load(self, instr) -> None:
        source = instr.args[0]
        dest = instr.dest

        if (
            source.kind == IROperandKind.VARIABLE
            and dest.kind == IROperandKind.TEMP
            and dest.type_name == "float"
        ):
            self.lines.append(
                f"    movsd xmm0, {self._var_location(source.value, source.type_name)}"
            )
            self.lines.append(
                f"    movsd {self._temp_location(dest.value, dest.type_name)}, xmm0"
            )
            return

        if source.kind == IROperandKind.VARIABLE and dest.kind == IROperandKind.TEMP:
            acc = self._acc_reg(dest.type_name)
            self.lines.append(f"    mov {acc}, {self._var_location(source.value, source.type_name)}")
            self.lines.append(f"    mov {self._temp_location(dest.value, dest.type_name)}, {acc}")
            return

        if source.kind == IROperandKind.MEMORY and dest.kind == IROperandKind.TEMP:
            self.lines.append(
                f"    mov r11, {self._temp_location(source.value, 'ptr')}"
            )
            self.lines.append("    mov eax, dword [r11]")
            self.lines.append(
                f"    mov {self._temp_location(dest.value, dest.type_name)}, eax"
            )
            return

        self.lines.append(f"    ; unsupported LOAD: {instr.to_text()}")

    def _gen_return(self, instr) -> None:
        if not instr.args:
            self._emit_epilogue()
            return

        value = instr.args[0]

        if value.kind == IROperandKind.LITERAL:
            if value.type_name == "float":
                self._load_float_literal_to_xmm0(value.value)
            else:
                self.lines.append(f"    mov eax, {value.value}")
            self._emit_epilogue()
            return

        if value.kind == IROperandKind.TEMP:
            if value.type_name == "float":
                self.lines.append(
                    f"    movsd xmm0, {self._temp_location(value.value, value.type_name)}"
                )
            else:
                acc = self._acc_reg(value.type_name)
                self.lines.append(f"    mov {acc}, {self._temp_location(value.value, value.type_name)}")
            self._emit_epilogue()
            return

        if value.kind == IROperandKind.VARIABLE:
            if value.type_name == "float":
                self.lines.append(
                    f"    movsd xmm0, {self._var_location(value.value, value.type_name)}"
                )
            else:
                acc = self._acc_reg(value.type_name)
                self.lines.append(f"    mov {acc}, {self._var_location(value.value, value.type_name)}")
            self._emit_epilogue()
            return

        self.lines.append(f"    ; unsupported return operand: {value}")
        self._emit_epilogue()

    def _block_label(self, label: str) -> str:
        return f".{self.current_function.name}_{label}"

    def _temp_addr(self, temp_name: str) -> str:
        # Пока temps тоже храним в stack_frame как отдельные слоты
        if temp_name not in self.stack_frame.variable_offsets:
            self.stack_frame.allocate_local(temp_name, 8)
        return self.stack_frame.get_address(temp_name)

    def _temp_location(self, temp_name: str, type_name: str | None = None) -> str:
        if self.use_register_allocation:
            location = self.register_allocation.get(str(temp_name))

            if location is not None and not location.startswith("spill"):
                return self._reg_for_type(location, type_name)

        return f"{self._mem_prefix(type_name)} {self._temp_addr(temp_name)}"

    def _gen_binary_arithmetic(self, instr) -> None:
        left = instr.args[0]
        right = instr.args[1]
        dest = instr.dest
        type_name = dest.type_name

        if type_name == "float":
            self._gen_float_binary_arithmetic(instr)
            return

        acc = self._acc_reg(type_name)
        full_acc = "rax"

        if left.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov {acc}, {left.value}")
        elif left.kind == IROperandKind.TEMP:
            self.lines.append(f"    mov {acc}, {self._temp_location(left.value, left.type_name)}")
        elif left.kind == IROperandKind.VARIABLE:
            self.lines.append(f"    mov {acc}, {self._var_location(left.value, left.type_name)}")
        else:
            self.lines.append("    ; unsupported left operand")
            return

        if right.kind == IROperandKind.LITERAL:
            rhs = str(right.value)
        elif right.kind == IROperandKind.TEMP:
            rhs = self._temp_location(right.value, right.type_name)
        elif right.kind == IROperandKind.VARIABLE:
            rhs = self._var_location(right.value, right.type_name)
        else:
            self.lines.append("    ; unsupported right operand")
            return

        if instr.opcode == IROpcode.ADD:
            self.lines.append(f"    add {acc}, {rhs}")

        elif instr.opcode == IROpcode.SUB:
            self.lines.append(f"    sub {acc}, {rhs}")

        elif instr.opcode == IROpcode.MUL:
            self.lines.append(f"    imul {acc}, {rhs}")

        elif instr.opcode == IROpcode.DIV:
            self._move_operand_to_register(right, "r10")
            if type_name == "int":
                self.lines.append("    cdq")
                self.lines.append("    idiv r10d")
            else:
                self.lines.append("    cqo")
                self.lines.append("    idiv r10")

        elif instr.opcode == IROpcode.MOD:
            self._move_operand_to_register(right, "r10")
            if type_name == "int":
                self.lines.append("    cdq")
                self.lines.append("    idiv r10d")
                self.lines.append("    mov eax, edx")
            else:
                self.lines.append("    cqo")
                self.lines.append("    idiv r10")
                self.lines.append("    mov rax, rdx")

        elif instr.opcode == IROpcode.AND:
            self.lines.append(f"    and {acc}, {rhs}")

        elif instr.opcode == IROpcode.OR:
            self.lines.append(f"    or {acc}, {rhs}")

        elif instr.opcode == IROpcode.XOR:
            self.lines.append(f"    xor {acc}, {rhs}")

        self.lines.append(f"    mov {self._temp_location(dest.value, type_name)}, {acc}")


    def _gen_float_binary_arithmetic(self, instr) -> None:
        left = instr.args[0]
        right = instr.args[1]
        dest = instr.dest

        self._load_float_operand_to_xmm0(left)
        rhs = self._float_rhs_operand(right)

        if instr.opcode == IROpcode.ADD:
            self.lines.append(f"    addsd xmm0, {rhs}")

        elif instr.opcode == IROpcode.SUB:
            self.lines.append(f"    subsd xmm0, {rhs}")

        elif instr.opcode == IROpcode.MUL:
            self.lines.append(f"    mulsd xmm0, {rhs}")

        elif instr.opcode == IROpcode.DIV:
            self.lines.append(f"    divsd xmm0, {rhs}")

        else:
            self.lines.append(f"    ; unsupported float arithmetic: {instr.to_text()}")
            return

        self.lines.append(
            f"    movsd {self._temp_location(dest.value, dest.type_name)}, xmm0"
        )

    def _gen_not(self, instr) -> None:
        operand = instr.args[0]
        dest = instr.dest

        self._load_operand_to_rax(operand)

        self.lines.append("    cmp rax, 0")
        self.lines.append("    mov rax, 0")
        self.lines.append("    sete al")

        self.lines.append(f"    mov {self._temp_location(dest.value, dest.type_name)}, al")


    def _load_operand_to_rax(self, operand) -> None:
        if operand.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov rax, {operand.value}")
            return

        if operand.kind == IROperandKind.TEMP:
            acc = self._acc_reg(operand.type_name)
            self.lines.append(f"    mov {acc}, {self._temp_location(operand.value, operand.type_name)}")
            return

        if operand.kind == IROperandKind.VARIABLE:
            acc = self._acc_reg(operand.type_name)
            self.lines.append(f"    mov {acc}, {self._var_location(operand.value, operand.type_name)}")
            return

        self.lines.append(f"    ; unsupported operand load to rax: {operand}")

    def _rhs_operand_text(self, operand) -> str:
        if operand.kind == IROperandKind.LITERAL:
            return str(operand.value)

        if operand.kind == IROperandKind.TEMP:
            return self._temp_location(operand.value, operand.type_name)

        if operand.kind == IROperandKind.VARIABLE:
            return self._var_location(operand.value, operand.type_name)

        return "0"

    def _gen_compare(self, instr) -> None:
        left = instr.args[0]
        right = instr.args[1]
        dest = instr.dest

        if left.type_name == "float" or right.type_name == "float":
            self._gen_float_compare(instr)
            return

        if left.kind == IROperandKind.LITERAL:
            left_reg = "eax" if left.type_name == "int" else "rax"
            self.lines.append(f"    mov {left_reg}, {left.value}")
        elif left.kind == IROperandKind.TEMP:
            left_reg = self._acc_reg(left.type_name)
            self.lines.append(
                f"    mov {left_reg}, {self._temp_location(left.value, left.type_name)}"
            )
        elif left.kind == IROperandKind.VARIABLE:
            left_reg = self._acc_reg(left.type_name)
            self.lines.append(
                f"    mov {left_reg}, {self._var_location(left.value, left.type_name)}"
            )
        else:
            self.lines.append(f"    ; unsupported compare left operand: {left}")
            return

        if right.kind == IROperandKind.LITERAL:
            rhs = str(right.value)
        elif right.kind == IROperandKind.TEMP:
            rhs = self._temp_location(right.value, right.type_name)
        elif right.kind == IROperandKind.VARIABLE:
            rhs = self._var_location(right.value, right.type_name)
        else:
            self.lines.append(f"    ; unsupported compare right operand: {right}")
            return

        self.lines.append(f"    cmp {left_reg}, {rhs}")

        set_map = {
            IROpcode.CMP_EQ: "sete",
            IROpcode.CMP_NE: "setne",
            IROpcode.CMP_LT: "setl",
            IROpcode.CMP_LE: "setle",
            IROpcode.CMP_GT: "setg",
            IROpcode.CMP_GE: "setge",
        }

        set_instr = set_map[instr.opcode]

        self.lines.append("    mov rax, 0")
        self.lines.append(f"    {set_instr} al")
        self.lines.append(f"    mov {self._temp_location(dest.value, dest.type_name)}, al")
        self.temp_compare_sources[str(dest.value)] = instr

    def _gen_float_compare(self, instr) -> None:
        left = instr.args[0]
        right = instr.args[1]
        dest = instr.dest

        self._load_float_operand_to_xmm0(left)
        rhs = self._float_rhs_operand(right)

        self.lines.append(f"    ucomisd xmm0, {rhs}")

        set_map = {
            IROpcode.CMP_EQ: "sete",
            IROpcode.CMP_NE: "setne",
            IROpcode.CMP_LT: "setb",
            IROpcode.CMP_LE: "setbe",
            IROpcode.CMP_GT: "seta",
            IROpcode.CMP_GE: "setae",
        }

        set_instr = set_map[instr.opcode]

        self.lines.append("    mov rax, 0")
        self.lines.append(f"    {set_instr} al")
        self.lines.append(
            f"    mov {self._temp_location(dest.value, dest.type_name)}, al"
        )

        self.temp_compare_sources[str(dest.value)] = instr


    def _emit_compare_for_direct_jump(self, compare_instr) -> None:
        left = compare_instr.args[0]
        right = compare_instr.args[1]

        if left.type_name == "float" or right.type_name == "float":
            self._load_float_operand_to_xmm0(left)
            rhs = self._float_rhs_operand(right)
            self.lines.append(f"    ucomisd xmm0, {rhs}")
            return

        if left.kind == IROperandKind.LITERAL:
            left_reg = "eax" if left.type_name == "int" else "rax"
            self.lines.append(f"    mov {left_reg}, {left.value}")
        elif left.kind == IROperandKind.TEMP:
            left_reg = self._acc_reg(left.type_name)
            self.lines.append(
                f"    mov {left_reg}, {self._temp_location(left.value, left.type_name)}"
            )
        elif left.kind == IROperandKind.VARIABLE:
            left_reg = self._acc_reg(left.type_name)
            self.lines.append(
                f"    mov {left_reg}, {self._var_location(left.value, left.type_name)}"
            )
        else:
            self.lines.append(f"    ; unsupported direct compare left operand: {left}")
            return

        if right.kind == IROperandKind.LITERAL:
            rhs = str(right.value)
        elif right.kind == IROperandKind.TEMP:
            rhs = self._temp_location(right.value, right.type_name)
        elif right.kind == IROperandKind.VARIABLE:
            rhs = self._var_location(right.value, right.type_name)
        else:
            self.lines.append(f"    ; unsupported direct compare right operand: {right}")
            return

        self.lines.append(f"    cmp {left_reg}, {rhs}")

    def _direct_jump_for_compare(self, opcode, jump_if_true: bool) -> str:
        signed_true = {
            IROpcode.CMP_EQ: "je",
            IROpcode.CMP_NE: "jne",
            IROpcode.CMP_LT: "jl",
            IROpcode.CMP_LE: "jle",
            IROpcode.CMP_GT: "jg",
            IROpcode.CMP_GE: "jge",
        }

        signed_false = {
            IROpcode.CMP_EQ: "jne",
            IROpcode.CMP_NE: "je",
            IROpcode.CMP_LT: "jge",
            IROpcode.CMP_LE: "jg",
            IROpcode.CMP_GT: "jle",
            IROpcode.CMP_GE: "jl",
        }

        if jump_if_true:
            return signed_true[opcode]

        return signed_false[opcode]

    def _direct_float_jump_for_compare(self, opcode, jump_if_true: bool) -> str:
        true_map = {
            IROpcode.CMP_EQ: "je",
            IROpcode.CMP_NE: "jne",
            IROpcode.CMP_LT: "jb",
            IROpcode.CMP_LE: "jbe",
            IROpcode.CMP_GT: "ja",
            IROpcode.CMP_GE: "jae",
        }

        false_map = {
            IROpcode.CMP_EQ: "jne",
            IROpcode.CMP_NE: "je",
            IROpcode.CMP_LT: "jae",
            IROpcode.CMP_LE: "ja",
            IROpcode.CMP_GT: "jbe",
            IROpcode.CMP_GE: "jb",
        }

        if jump_if_true:
            return true_map[opcode]

        return false_map[opcode]

    def _gen_jump(self, instr) -> None:
        target = instr.args[0]
        self.lines.append(f"    jmp {self._block_label(target.value)}")

    def _gen_jump_if_not(self, instr) -> None:
        cond = instr.args[0]
        target = instr.args[1]

        if cond.kind == IROperandKind.TEMP:
            compare_instr = self.temp_compare_sources.get(str(cond.value))
            if compare_instr is not None:
                self._emit_compare_for_direct_jump(compare_instr)

                if compare_instr.args[0].type_name == "float" or compare_instr.args[1].type_name == "float":
                    target_label = self._block_label(target.value)

                    if compare_instr.opcode != IROpcode.CMP_NE:
                        self.lines.append(f"    jp {target_label}")

                    jump = self._direct_float_jump_for_compare(compare_instr.opcode, jump_if_true=False)
                    self.lines.append(f"    {jump} {target_label}")
                else:
                    jump = self._direct_jump_for_compare(compare_instr.opcode, jump_if_true=False)
                    self.lines.append(f"    {jump} {self._block_label(target.value)}")

                return

        if cond.kind == IROperandKind.TEMP:
            reg = self._acc_reg(cond.type_name)
            self.lines.append(
                f"    mov {reg}, {self._temp_location(cond.value, cond.type_name)}"
            )
        elif cond.kind == IROperandKind.VARIABLE:
            reg = self._acc_reg(cond.type_name)
            self.lines.append(
                f"    mov {reg}, {self._var_location(cond.value, cond.type_name)}"
            )
        elif cond.kind == IROperandKind.LITERAL:
            reg = "rax"
            self.lines.append(f"    mov {reg}, {cond.value}")
        else:
            self.lines.append(f"    ; unsupported JUMP_IF_NOT condition: {cond}")
            return

        self.lines.append(f"    cmp {reg}, 0")
        self.lines.append(f"    je {self._block_label(target.value)}")

    def _gen_jump_if(self, instr) -> None:
        cond = instr.args[0]
        target = instr.args[1]

        if cond.kind == IROperandKind.TEMP:
            compare_instr = self.temp_compare_sources.get(str(cond.value))
            if compare_instr is not None:
                self._emit_compare_for_direct_jump(compare_instr)

                if compare_instr.args[0].type_name == "float" or compare_instr.args[1].type_name == "float":
                    target_label = self._block_label(target.value)

                    if compare_instr.opcode == IROpcode.CMP_NE:
                        self.lines.append(f"    jp {target_label}")
                    else:
                        false_label = self.current_function.new_label("float_unordered_skip")
                        self.lines.append(f"    jp {self._block_label(false_label)}")

                    jump = self._direct_float_jump_for_compare(compare_instr.opcode, jump_if_true=True)
                    self.lines.append(f"    {jump} {target_label}")

                    if compare_instr.opcode != IROpcode.CMP_NE:
                        self.lines.append(f"{self._block_label(false_label)}:")
                else:
                    jump = self._direct_jump_for_compare(compare_instr.opcode, jump_if_true=True)
                    self.lines.append(f"    {jump} {self._block_label(target.value)}")

                return

        if cond.kind == IROperandKind.TEMP:
            reg = self._acc_reg(cond.type_name)
            self.lines.append(
                f"    mov {reg}, {self._temp_location(cond.value, cond.type_name)}"
            )
        elif cond.kind == IROperandKind.VARIABLE:
            reg = self._acc_reg(cond.type_name)
            self.lines.append(
                f"    mov {reg}, {self._var_location(cond.value, cond.type_name)}"
            )
        elif cond.kind == IROperandKind.LITERAL:
            reg = "rax"
            self.lines.append(f"    mov {reg}, {cond.value}")
        else:
            self.lines.append(f"    ; unsupported JUMP_IF condition: {cond}")
            return

        self.lines.append(f"    cmp {reg}, 0")
        self.lines.append(f"    jne {self._block_label(target.value)}")

    def _move_params_to_stack(self, function: IRFunction) -> None:
        for i, param_name in enumerate(function.params):
            addr = self._var_addr(param_name)

            if i < len(INT_ARG_REGISTERS):
                reg = INT_ARG_REGISTERS[i]

                if param_name in self.variable_registers:
                    target_reg = self._reg_for_type(self.variable_registers[param_name], "int")
                    source_reg = self._reg_for_type(reg, "int")
                    self.lines.append(f"    mov {target_reg}, {source_reg}")
                else:
                    self.lines.append(f"    mov qword {addr}, {reg}")
            else:
                stack_arg_addr = self.stack_frame.get_stack_param_address(
                    i - len(INT_ARG_REGISTERS)
                )
                self.lines.append(f"    mov rax, qword {stack_arg_addr}")

                if param_name in self.variable_registers:
                    target_reg = self._reg_for_type(self.variable_registers[param_name], "int")
                    self.lines.append(f"    mov {target_reg}, eax")
                else:
                    self.lines.append(f"    mov qword {addr}, rax")


    def _gen_param(self, instr) -> None:
        index_operand = instr.args[0]
        value_operand = instr.args[1]

        self.pending_params[int(index_operand.value)] = value_operand

    def _move_operand_to_register(self, operand, reg: str) -> None:
        if operand.kind == IROperandKind.LITERAL:
            if operand.type_name == "string" and isinstance(operand.value, str):
                label = self._string_label(operand.value)
                self.lines.append(f"    lea {reg}, [rel {label}]")
                return

            self.lines.append(f"    mov {reg}, {operand.value}")
            return

        if operand.kind == IROperandKind.TEMP:
            typed_reg = self._reg_for_type(reg, operand.type_name)
            self.lines.append(f"    mov {typed_reg}, {self._temp_location(operand.value, operand.type_name)}")
            return

        if operand.kind == IROperandKind.VARIABLE:
            if operand.type_name and "[" in operand.type_name and "]" in operand.type_name:
                addr = self._var_addr(operand.value)
                self.lines.append(f"    lea {reg}, {addr}")
                return

            typed_reg = self._reg_for_type(reg, operand.type_name)
            self.lines.append(f"    mov {typed_reg}, {self._var_location(operand.value, operand.type_name)}")
            return

        self.lines.append(f"    ; unsupported operand move to {reg}: {operand}")

    def _gen_call(self, instr) -> None:
        if not instr.args:
            self.lines.append("    ; unsupported CALL without target")
            return

        func_operand = instr.args[0]
        func_name = func_operand.value

        if func_name == "pow":
            arg0 = self.pending_params.get(0)
            arg1 = self.pending_params.get(1)

            if arg0 is not None:
                self._move_float_operand_to_xmm(arg0, "xmm0")

            if arg1 is not None:
                self._move_float_operand_to_xmm(arg1, "xmm1")

            self.lines.append("    call pow")

            if instr.dest is not None and instr.dest.kind == IROperandKind.TEMP:
                self.lines.append(
                    f"    movsd {self._temp_location(instr.dest.value, instr.dest.type_name)}, xmm0"
                )

            self.pending_params.clear()
            return

        stack_arg_indices = [
            index
            for index in sorted(self.pending_params.keys(), reverse=True)
            if index >= len(INT_ARG_REGISTERS)
        ]

        for index in stack_arg_indices:
            operand = self.pending_params[index]
            self._move_operand_to_register(operand, "rax")
            self.lines.append("    push rax")

        for index in sorted(self.pending_params.keys()):
            if index >= len(INT_ARG_REGISTERS):
                continue

            reg = INT_ARG_REGISTERS[index]
            operand = self.pending_params[index]
            self._move_operand_to_register(operand, reg)

        if func_name in {"printf", "scanf"}:
            self.lines.append("    xor eax, eax")

        self.lines.append(f"    call {func_name}")

        stack_arg_count = len(stack_arg_indices)
        if stack_arg_count > 0:
            self.lines.append(f"    add rsp, {stack_arg_count * 8}")

        if instr.dest is not None and instr.dest.kind == IROperandKind.TEMP:
            self.lines.append(
                f"    mov {self._temp_location(instr.dest.value, instr.dest.type_name)}, "
                f"{self._acc_reg(instr.dest.type_name)}"
            )

        self.pending_params.clear()

