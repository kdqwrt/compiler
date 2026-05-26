from src.ir.ir_instructions import IROpcode, IROperand, IROperandKind


class ConstantFoldingPass:
    def run(self, program):
        for func in program.functions:
            for block in func.blocks:
                constants = {}
                new_instr = []

                for instr in block.instructions:
                    instr = self._replace_known_constants(instr, constants)
                    instr = self._try_fold(instr)

                    if (
                        instr.opcode == IROpcode.MOVE
                        and instr.dest is not None
                        and instr.dest.kind == IROperandKind.TEMP
                        and instr.args
                        and instr.args[0].kind == IROperandKind.LITERAL
                    ):
                        constants[instr.dest.value] = instr.args[0]

                    new_instr.append(instr)

                block.instructions = new_instr

        return program

    def _replace_known_constants(self, instr, constants):
        replaced_args = []

        for arg in instr.args:
            if arg.kind == IROperandKind.TEMP and arg.value in constants:
                replaced_args.append(constants[arg.value])
            else:
                replaced_args.append(arg)

        instr.args = replaced_args
        return instr

    def _try_fold(self, instr):
        if len(instr.args) != 2:
            return instr

        left, right = instr.args

        if (
            left.kind != IROperandKind.LITERAL
            or right.kind != IROperandKind.LITERAL
        ):
            return instr

        a = left.value
        b = right.value

        if instr.opcode == IROpcode.ADD:
            value = a + b
        elif instr.opcode == IROpcode.SUB:
            value = a - b
        elif instr.opcode == IROpcode.MUL:
            value = a * b
        elif instr.opcode == IROpcode.DIV:
            if b == 0:
                return instr
            value = a // b
        elif instr.opcode == IROpcode.MOD:
            if b == 0:
                return instr
            value = a % b
        else:
            return instr

        literal = IROperand(
            IROperandKind.LITERAL,
            value,
            type_name=left.type_name or right.type_name or "int",
        )

        instr.opcode = IROpcode.MOVE
        instr.args = [literal]

        return instr