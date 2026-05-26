from src.ir.ir_instructions import IROpcode, IROperandKind


class DeadStoreEliminationPass:
    def run(self, program):
        for func in program.functions:
            function_reads = self._collect_function_reads(func)

            for block in func.blocks:
                block.instructions = self._remove_dead_stores(
                    block.instructions,
                    function_reads,
                )

        return program

    def _collect_function_reads(self, func):
        reads = set()

        for block in func.blocks:
            for instr in block.instructions:
                if instr.opcode == IROpcode.STORE:
                    if len(instr.args) == 2:
                        self._mark_used(instr.args[1], reads)
                    continue

                if instr.opcode == IROpcode.ALLOCA:
                    continue

                for arg in instr.args:
                    self._mark_used(arg, reads)

        return reads

    def _remove_dead_stores(self, instructions, function_reads):
        result = []

        for instr in instructions:
            if instr.opcode == IROpcode.STORE and len(instr.args) == 2:
                target = instr.args[0]

                if (
                    target.kind == IROperandKind.VARIABLE
                    and target.value not in function_reads
                ):
                    continue

            result.append(instr)

        return result

    def _mark_used(self, operand, reads):
        if operand.kind == IROperandKind.VARIABLE:
            reads.add(operand.value)