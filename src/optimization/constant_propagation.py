from src.ir.ir_instructions import IROpcode, IROperand, IROperandKind


class ConstantPropagationPass:
    def run(self, program):
        for func in program.functions:
            for block in func.blocks:
                constants = {}

                for instr in block.instructions:
                    self._rewrite_instruction(instr, constants)
                    self._track_constants(instr, constants)

        return program

    def _rewrite_instruction(self, instr, constants):
        if instr.opcode == IROpcode.LOAD:
            self._rewrite_load(instr, constants)
            return

        if instr.opcode == IROpcode.STORE:
            self._rewrite_store(instr, constants)
            return

        if instr.opcode in {
            IROpcode.ALLOCA,
            IROpcode.GEP,
            IROpcode.ADDR_OF,
            IROpcode.MEMCPY,
            IROpcode.PARAM,
        }:
            return

        instr.args = [
            constants.get(arg.value, arg)
            if arg.kind in {IROperandKind.VARIABLE, IROperandKind.TEMP}
            else arg
            for arg in instr.args
        ]

    def _rewrite_load(self, instr, constants):
        if (
            instr.dest is None
            or len(instr.args) != 1
            or instr.args[0].kind != IROperandKind.VARIABLE
        ):
            return

        source = instr.args[0]

        if source.value not in constants:
            return

        literal = constants[source.value]

        instr.opcode = IROpcode.MOVE
        instr.args = [literal]

    def _rewrite_store(self, instr, constants):
        if len(instr.args) != 2:
            return

        target, value = instr.args

        if value.kind in {IROperandKind.VARIABLE, IROperandKind.TEMP}:
            instr.args[1] = constants.get(value.value, value)

    def _track_constants(self, instr, constants):
        if (
            instr.opcode == IROpcode.STORE
            and len(instr.args) == 2
            and instr.args[0].kind == IROperandKind.VARIABLE
        ):
            target = instr.args[0]
            value = instr.args[1]

            if value.kind == IROperandKind.LITERAL:
                constants[target.value] = value
            else:
                constants.pop(target.value, None)

        if (
            instr.opcode == IROpcode.MOVE
            and instr.dest is not None
            and instr.dest.kind == IROperandKind.TEMP
            and instr.args
            and instr.args[0].kind == IROperandKind.LITERAL
        ):
            constants[instr.dest.value] = instr.args[0]