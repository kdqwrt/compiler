from __future__ import annotations

from typing import List, Optional

from src.ir.basic_block import IRProgram, IRFunction
from src.ir.ir_instructions import IROpcode, IROperandKind
from src.codegen.stack_frame import StackFrame
from src.codegen.abi import INT_ARG_REGISTERS
from src.codegen.register_allocator import LinearScanRegisterAllocator



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

    def generate(self, program: IRProgram) -> str:
        self.lines = []

        self.global_variable_names = {
            var.name for var in getattr(program, "global_variables", [])
        }

        self._emit_global_sections(program)

        self.lines.append("section .text")
        self.lines.append("")
        self.lines.append("extern print_int")
        self.lines.append("extern print_string")
        self.lines.append("extern read_int")

        for function in program.functions:
            self._gen_function(function)

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
                self.lines.append(f"{var.name}: dq {var.initializer}")
            self.lines.append("")

        if uninitialized:
            self.lines.append("section .bss")
            for var in uninitialized:
                self.lines.append(f"global {var.name}")
                self.lines.append(f"{var.name}: resq 1")
            self.lines.append("")

    def _gen_function(self, function: IRFunction) -> None:
        self.current_function = function
        self.stack_frame = StackFrame()

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

        self._reserve_function_storage(function)

        self.lines.append("")
        self.lines.append(f"global {function.name}")
        self.lines.append(f"{function.name}:")

        self._emit_prologue()
        self._move_params_to_stack(function)

        for block in function.blocks:
            self.lines.append(f".{function.name}_{block.label}:")
            for instr in block.instructions:
                self._gen_instruction(instr)

        self.current_function = None
        self.stack_frame = None

    def _reserve_function_storage(self, function: IRFunction) -> None:
        for param_name in function.params:
            self.stack_frame.allocate_local(param_name, 8)

        for local_name in function.local_variables:
            self.stack_frame.allocate_local(local_name, 8)

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

    def _emit_prologue(self) -> None:
        self.lines.append("    push rbp")
        self.lines.append("    mov rbp, rsp")

        stack_size = self.stack_frame.aligned_stack_size()
        if stack_size > 0:
            self.lines.append(f"    sub rsp, {stack_size}")

    def _emit_epilogue(self) -> None:
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
        return f"{self._mem_prefix(type_name)} {self._var_addr(name)}"


    def _full_acc_reg(self, type_name: str | None) -> str:
        if type_name in {"int", "bool"}:
            return "eax"
        return "rax"

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

        if instr.opcode == IROpcode.STORE:
            self._gen_store(instr)
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

        self.lines.append(f"    ; unsupported STORE: {instr.to_text()}")

    def _gen_load(self, instr) -> None:
        source = instr.args[0]
        dest = instr.dest

        if source.kind == IROperandKind.VARIABLE and dest.kind == IROperandKind.TEMP:
            acc = self._acc_reg(dest.type_name)
            self.lines.append(f"    mov {acc}, {self._var_location(source.value, source.type_name)}")
            self.lines.append(f"    mov {self._temp_location(dest.value, dest.type_name)}, {acc}")
            return

        self.lines.append(f"    ; unsupported LOAD: {instr.to_text()}")

    def _gen_return(self, instr) -> None:
        if not instr.args:
            self._emit_epilogue()
            return

        value = instr.args[0]

        if value.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov eax, {value.value}")
            self._emit_epilogue()
            return

        if value.kind == IROperandKind.TEMP:
            acc = self._acc_reg(value.type_name)
            self.lines.append(f"    mov {acc}, {self._temp_location(value.value, value.type_name)}")
            self._emit_epilogue()
            return

        if value.kind == IROperandKind.VARIABLE:
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

    def _gen_jump(self, instr) -> None:
        target = instr.args[0]
        self.lines.append(f"    jmp {self._block_label(target.value)}")

    def _gen_jump_if_not(self, instr) -> None:
        cond = instr.args[0]
        target = instr.args[1]

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
                self.lines.append(f"    mov qword {addr}, {reg}")
            else:
                stack_arg_addr = self.stack_frame.get_stack_param_address(
                    i - len(INT_ARG_REGISTERS)
                )
                self.lines.append(f"    mov rax, qword {stack_arg_addr}")
                self.lines.append(f"    mov qword {addr}, rax")


    def _gen_param(self, instr) -> None:
        index_operand = instr.args[0]
        value_operand = instr.args[1]

        self.pending_params[int(index_operand.value)] = value_operand

    def _move_operand_to_register(self, operand, reg: str) -> None:
        if operand.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov {reg}, {operand.value}")
            return

        if operand.kind == IROperandKind.TEMP:
            typed_reg = self._reg_for_type(reg, operand.type_name)
            self.lines.append(f"    mov {typed_reg}, {self._temp_location(operand.value, operand.type_name)}")
            return

        if operand.kind == IROperandKind.VARIABLE:
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

