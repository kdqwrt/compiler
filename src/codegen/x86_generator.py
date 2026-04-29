from __future__ import annotations

from typing import List, Optional

from src.ir.basic_block import IRProgram, IRFunction
from src.ir.ir_instructions import IROpcode, IROperandKind
from src.codegen.stack_frame import StackFrame
from src.codegen.abi import INT_ARG_REGISTERS

class X86Generator:
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.current_function: Optional[IRFunction] = None
        self.stack_frame: Optional[StackFrame] = None
        self.pending_params: dict[int, object] = {}

    def generate(self, program: IRProgram) -> str:
        self.lines = []
        self.lines.append("section .text")

        for function in program.functions:
            self._gen_function(function)

        return "\n".join(self.lines)

    def _gen_function(self, function: IRFunction) -> None:
        self.current_function = function
        self.stack_frame = StackFrame()

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
                    self.stack_frame.allocate_local(instr.dest.value, 8)

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
        return self.stack_frame.get_address(name)

    def _gen_instruction(self, instr) -> None:
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
            self.lines.append(f"    mov qword {addr}, {value.value}")
            return

        # STORE variable, temp
        if target.kind == IROperandKind.VARIABLE and value.kind == IROperandKind.TEMP:
            addr = self._var_addr(target.value)
            temp_slot = self._temp_addr(value.value)
            self.lines.append(f"    mov rax, qword {temp_slot}")
            self.lines.append(f"    mov qword {addr}, rax")
            return

        self.lines.append(f"    ; unsupported STORE: {instr.to_text()}")

    def _gen_load(self, instr) -> None:
        source = instr.args[0]
        dest = instr.dest

        # LOAD temp, variable
        if source.kind == IROperandKind.VARIABLE and dest.kind == IROperandKind.TEMP:
            src_addr = self._var_addr(source.value)
            dest_addr = self._temp_addr(dest.value)
            self.lines.append(f"    mov rax, qword {src_addr}")
            self.lines.append(f"    mov qword {dest_addr}, rax")
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
            temp_addr = self._temp_addr(value.value)
            self.lines.append(f"    mov rax, qword {temp_addr}")
            self._emit_epilogue()
            return

        if value.kind == IROperandKind.VARIABLE:
            addr = self._var_addr(value.value)
            self.lines.append(f"    mov rax, qword {addr}")
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

    def _gen_binary_arithmetic(self, instr) -> None:
        left = instr.args[0]
        right = instr.args[1]
        dest = instr.dest

        # left -> rax
        if left.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov rax, {left.value}")
        elif left.kind == IROperandKind.TEMP:
            self.lines.append(f"    mov rax, qword {self._temp_addr(left.value)}")
        elif left.kind == IROperandKind.VARIABLE:
            self.lines.append(f"    mov rax, qword {self._var_addr(left.value)}")
        else:
            self.lines.append(f"    ; unsupported left operand")
            return

        # operation with right
        if right.kind == IROperandKind.LITERAL:
            rhs = str(right.value)
        elif right.kind == IROperandKind.TEMP:
            rhs = f"qword {self._temp_addr(right.value)}"
        elif right.kind == IROperandKind.VARIABLE:
            rhs = f"qword {self._var_addr(right.value)}"
        else:
            self.lines.append(f"    ; unsupported right operand")
            return

        if instr.opcode == IROpcode.ADD:
            self.lines.append(f"    add rax, {rhs}")

        elif instr.opcode == IROpcode.SUB:
            self.lines.append(f"    sub rax, {rhs}")

        elif instr.opcode == IROpcode.MUL:
            self.lines.append(f"    imul rax, {rhs}")

        elif instr.opcode == IROpcode.DIV:
            self.lines.append("    cqo")
            self.lines.append(f"    idiv {rhs}")

        elif instr.opcode == IROpcode.MOD:
            self.lines.append("    cqo")
            self.lines.append(f"    idiv {rhs}")
            self.lines.append("    mov rax, rdx")


        elif instr.opcode == IROpcode.AND:
            self.lines.append(f"    and rax, {rhs}")

        elif instr.opcode == IROpcode.OR:
            self.lines.append(f"    or rax, {rhs}")

        elif instr.opcode == IROpcode.XOR:
            self.lines.append(f"    xor rax, {rhs}")

        if instr.opcode == IROpcode.NOT:
            self.lines.append(f"    not rax")

        # save result temp
        dest_addr = self._temp_addr(dest.value)
        self.lines.append(f"    mov qword {dest_addr}, rax")


    def _gen_not(self, instr) -> None:
        operand = instr.args[0]
        dest = instr.dest

        self._load_operand_to_rax(operand)

        self.lines.append("    cmp rax, 0")
        self.lines.append("    mov rax, 0")
        self.lines.append("    sete al")

        dest_addr = self._temp_addr(dest.value)
        self.lines.append(f"    mov qword {dest_addr}, rax")

    def _load_operand_to_rax(self, operand) -> None:
        if operand.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov rax, {operand.value}")
            return

        if operand.kind == IROperandKind.TEMP:
            self.lines.append(f"    mov rax, qword {self._temp_addr(operand.value)}")
            return

        if operand.kind == IROperandKind.VARIABLE:
            self.lines.append(f"    mov rax, qword {self._var_addr(operand.value)}")
            return

        self.lines.append(f"    ; unsupported operand load to rax: {operand}")


    def _rhs_operand_text(self, operand) -> str:
        if operand.kind == IROperandKind.LITERAL:
            return str(operand.value)

        if operand.kind == IROperandKind.TEMP:
            return f"qword {self._temp_addr(operand.value)}"

        if operand.kind == IROperandKind.VARIABLE:
            return f"qword {self._var_addr(operand.value)}"

        return "0"

    def _gen_compare(self, instr) -> None:
        left = instr.args[0]
        right = instr.args[1]
        dest = instr.dest

        self._load_operand_to_rax(left)
        rhs = self._rhs_operand_text(right)

        self.lines.append(f"    cmp rax, {rhs}")

        set_map = {
            IROpcode.CMP_EQ: "sete",
            IROpcode.CMP_NE: "setne",
            IROpcode.CMP_LT: "setl",
            IROpcode.CMP_LE: "setle",
            IROpcode.CMP_GT: "setg",
            IROpcode.CMP_GE: "setge",
        }

        set_instr = set_map[instr.opcode]

        # al = 0/1
        self.lines.append("    mov rax, 0")
        self.lines.append(f"    {set_instr} al")

        dest_addr = self._temp_addr(dest.value)
        self.lines.append(f"    mov qword {dest_addr}, rax")

    def _gen_jump(self, instr) -> None:
        target = instr.args[0]
        self.lines.append(f"    jmp {self._block_label(target.value)}")

    def _gen_jump_if_not(self, instr) -> None:
        cond = instr.args[0]
        target = instr.args[1]

        if cond.kind == IROperandKind.TEMP:
            self.lines.append(f"    mov rax, qword {self._temp_addr(cond.value)}")
        elif cond.kind == IROperandKind.VARIABLE:
            self.lines.append(f"    mov rax, qword {self._var_addr(cond.value)}")
        elif cond.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov rax, {cond.value}")
        else:
            self.lines.append(f"    ; unsupported JUMP_IF_NOT condition: {cond}")
            return

        self.lines.append("    cmp rax, 0")
        self.lines.append(f"    je {self._block_label(target.value)}")

    def _gen_jump_if(self, instr) -> None:
        cond = instr.args[0]
        target = instr.args[1]

        if cond.kind == IROperandKind.TEMP:
            self.lines.append(f"    mov rax, qword {self._temp_addr(cond.value)}")
        elif cond.kind == IROperandKind.VARIABLE:
            self.lines.append(f"    mov rax, qword {self._var_addr(cond.value)}")
        elif cond.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov rax, {cond.value}")
        else:
            self.lines.append(f"    ; unsupported JUMP_IF condition: {cond}")
            return

        self.lines.append("    cmp rax, 0")
        self.lines.append(f"    jne {self._block_label(target.value)}")


    def _move_params_to_stack(self, function: IRFunction) -> None:
        for i, param_name in enumerate(function.params):
            if i >= len(INT_ARG_REGISTERS):
                self.lines.append(f"    ; unsupported stack-passed param: {param_name}")
                continue

            reg = INT_ARG_REGISTERS[i]
            addr = self._var_addr(param_name)
            self.lines.append(f"    mov qword {addr}, {reg}")


    def _gen_param(self, instr) -> None:
        index_operand = instr.args[0]
        value_operand = instr.args[1]

        self.pending_params[int(index_operand.value)] = value_operand

    def _move_operand_to_register(self, operand, reg: str) -> None:
        if operand.kind == IROperandKind.LITERAL:
            self.lines.append(f"    mov {reg}, {operand.value}")
            return

        if operand.kind == IROperandKind.TEMP:
            self.lines.append(f"    mov {reg}, qword {self._temp_addr(operand.value)}")
            return

        if operand.kind == IROperandKind.VARIABLE:
            self.lines.append(f"    mov {reg}, qword {self._var_addr(operand.value)}")
            return

        self.lines.append(f"    ; unsupported operand move to {reg}: {operand}")

    def _gen_call(self, instr) -> None:
        if not instr.args:
            self.lines.append("    ; unsupported CALL without target")
            return

        func_operand = instr.args[0]
        func_name = func_operand.value

        # Разложить pending params по ABI-регистрам
        for index in sorted(self.pending_params.keys()):
            if index >= len(INT_ARG_REGISTERS):
                self.lines.append(f"    ; unsupported stack argument #{index}")
                continue

            reg = INT_ARG_REGISTERS[index]
            operand = self.pending_params[index]
            self._move_operand_to_register(operand, reg)

        self.lines.append(f"    call {func_name}")

        if instr.dest is not None and instr.dest.kind == IROperandKind.TEMP:
            dest_addr = self._temp_addr(instr.dest.value)
            self.lines.append(f"    mov qword {dest_addr}, rax")

        self.pending_params.clear()

