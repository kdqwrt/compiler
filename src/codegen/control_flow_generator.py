from __future__ import annotations
from src.parser.ast import BlockStmtNode, IfStmtNode, WhileStmtNode, ForStmtNode, BinaryExprNode
# from src.parser.ast import BlockStmtNode, IfStmtNode, WhileStmtNode, ForStmtNode
from src.ir.basic_block import BasicBlock
from src.ir.ir_instructions import IROpcode, IROperand, IROperandKind, IRInstruction

class ControlFlowGeneratorMixin:

    def _gen_condition_jump(self, expr, true_label: str, false_label: str) -> None:
        if isinstance(expr, BinaryExprNode) and expr.operator.lexeme == "&&":
            rhs_label = self.current_function.new_label("and_rhs_direct")
            rhs_block = BasicBlock(rhs_label)
            self.current_function.add_block(rhs_block)

            self._gen_condition_jump(expr.left, rhs_label, false_label)

            self._switch_block(rhs_block)
            self._gen_condition_jump(expr.right, true_label, false_label)
            return

        if isinstance(expr, BinaryExprNode) and expr.operator.lexeme == "||":
            rhs_label = self.current_function.new_label("or_rhs_direct")
            rhs_block = BasicBlock(rhs_label)
            self.current_function.add_block(rhs_block)

            self._gen_condition_jump(expr.left, true_label, rhs_label)

            self._switch_block(rhs_block)
            self._gen_condition_jump(expr.right, true_label, false_label)
            return

        cond_op = self._gen_expr(expr)

        self._emit_jump(
            IROpcode.JUMP_IF_NOT,
            cond_op,
            IROperand(IROperandKind.LABEL, false_label),
            comment="condition false",
        )
        self.current_function.add_edge(self.current_block.label, false_label)

        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, true_label),
            comment="condition true",
        )
        self.current_function.add_edge(self.current_block.label, true_label)


    def _gen_if(self, stmt: IfStmtNode) -> None:
        # cond_op = self._gen_expr(stmt.condition)

        then_label = self.current_function.new_label("then")
        end_label = self.current_function.new_label("endif")

        has_else = stmt.else_branch is not None
        else_label = self.current_function.new_label("else") if has_else else end_label

        then_block = BasicBlock(then_label)
        self.current_function.add_block(then_block)

        if has_else:
            else_block = BasicBlock(else_label)
            self.current_function.add_block(else_block)
        else:
            else_block = None

        end_block = BasicBlock(end_label)
        self.current_function.add_block(end_block)

        self._gen_condition_jump(stmt.condition, then_label, else_label)

        # # если условие ложно -> else/end
        # self._emit_jump(
        #     IROpcode.JUMP_IF_NOT,
        #     cond_op,
        #     IROperand(IROperandKind.LABEL, else_label),
        #     comment="if false",
        # )
        # self.current_function.add_edge(self.current_block.label, else_label)
        #
        # # иначе идём в then
        # self._emit_jump(
        #     IROpcode.JUMP,
        #     IROperand(IROperandKind.LABEL, then_label),
        #     comment="if true",
        # )
        # self.current_function.add_edge(self.current_block.label, then_label)

        # then branch
        self._switch_block(then_block)
        self._gen_branch_stmt(stmt.then_branch)

        then_fallthrough = not self.current_block.is_terminated()
        if then_fallthrough:
            self._emit_jump(
                IROpcode.JUMP,
                IROperand(IROperandKind.LABEL, end_label),
                comment="end if",
            )
            self.current_function.add_edge(self.current_block.label, end_label)

        # else branch
        if has_else:
            self._switch_block(else_block)
            self._gen_branch_stmt(stmt.else_branch)

            else_fallthrough = not self.current_block.is_terminated()
            if else_fallthrough:
                self._emit_jump(
                    IROpcode.JUMP,
                    IROperand(IROperandKind.LABEL, end_label),
                    comment="end if",
                )
                self.current_function.add_edge(self.current_block.label, end_label)

            if then_fallthrough and else_fallthrough:
                self._try_insert_phi(then_block, else_block, end_block)

        self._switch_block(end_block)


    def _gen_while(self, stmt: WhileStmtNode) -> None:
        cond_label = self.current_function.new_label("while_cond")
        body_label = self.current_function.new_label("while_body")
        exit_label = self.current_function.new_label("while_exit")

        cond_block = BasicBlock(cond_label)
        body_block = BasicBlock(body_label)
        exit_block = BasicBlock(exit_label)

        self.current_function.add_block(cond_block)
        self.current_function.add_block(body_block)
        self.current_function.add_block(exit_block)

        # переход к условию
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, cond_label),
            comment="while condition",
        )
        self.current_function.add_edge(self.current_block.label, cond_label)

        # блок условия
        self._switch_block(cond_block)
        cond_op = self._gen_expr(stmt.condition)

        # если условие ложно -> exit
        self._emit_jump(
            IROpcode.JUMP_IF_NOT,
            cond_op,
            IROperand(IROperandKind.LABEL, exit_label),
            comment="while false",
        )
        self.current_function.add_edge(self.current_block.label, exit_label)

        # иначе -> body
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, body_label),
            comment="while true",
        )
        self.current_function.add_edge(self.current_block.label, body_label)

        # блок тела
        self._switch_block(body_block)
        self._gen_branch_stmt(stmt.body)

        if not self.current_block.is_terminated():
            self._emit_jump(
                IROpcode.JUMP,
                IROperand(IROperandKind.LABEL, cond_label),
                comment="while repeat",
            )
            self.current_function.add_edge(self.current_block.label, cond_label)

        # выход
        self._switch_block(exit_block)


    def _gen_for(self, stmt: ForStmtNode) -> None:
        cond_label = self.current_function.new_label("for_cond")
        body_label = self.current_function.new_label("for_body")
        exit_label = self.current_function.new_label("for_exit")

        cond_block = BasicBlock(cond_label)
        body_block = BasicBlock(body_label)
        exit_block = BasicBlock(exit_label)

        # init выполняется в текущем блоке
        if stmt.init is not None:
            self._gen_stmt(stmt.init)

        self.current_function.add_block(cond_block)
        self.current_function.add_block(body_block)
        self.current_function.add_block(exit_block)

        # переход к условию
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, cond_label),
            comment="for condition",
        )
        self.current_function.add_edge(self.current_block.label, cond_label)

        # блок условия
        self._switch_block(cond_block)

        if stmt.condition is not None:
            cond_op = self._gen_expr(stmt.condition)

            # если условие ложно -> exit
            self._emit_jump(
                IROpcode.JUMP_IF_NOT,
                cond_op,
                IROperand(IROperandKind.LABEL, exit_label),
                comment="for false",
            )
            self.current_function.add_edge(self.current_block.label, exit_label)

            # иначе -> body
            self._emit_jump(
                IROpcode.JUMP,
                IROperand(IROperandKind.LABEL, body_label),
                comment="for true",
            )
            self.current_function.add_edge(self.current_block.label, body_label)
        else:
            # for (;;)
            self._emit_jump(
                IROpcode.JUMP,
                IROperand(IROperandKind.LABEL, body_label),
                comment="for no condition",
            )
            self.current_function.add_edge(self.current_block.label, body_label)

        # блок тела
        self._switch_block(body_block)
        self._gen_branch_stmt(stmt.body)

        # update после тела
        if not self.current_block.is_terminated():
            if stmt.update is not None:
                self._gen_expr(stmt.update)

            self._emit_jump(
                IROpcode.JUMP,
                IROperand(IROperandKind.LABEL, cond_label),
                comment="for repeat",
            )
            self.current_function.add_edge(self.current_block.label, cond_label)

        # выход
        self._switch_block(exit_block)


    def _gen_branch_stmt(self, stmt) -> None:
        if isinstance(stmt, BlockStmtNode):
            for inner in stmt.statements:
                self._gen_stmt(inner)
        else:
            self._gen_stmt(stmt)


    def _find_last_store_target(self, block: BasicBlock) -> tuple[str | None, IROperand | None]:
        for instr in reversed(block.instructions):
            if instr.opcode == IROpcode.STORE and len(instr.args) >= 2:
                target = instr.args[0]
                value = instr.args[1]

                if target.kind == IROperandKind.VARIABLE:
                    return target.value, value

        return None, None


    def _operand_to_phi_text(self, operand: IROperand) -> str:
        return str(operand.value)

    def _try_insert_phi(
        self,
        then_block: BasicBlock,
        else_block: BasicBlock,
        end_block: BasicBlock,
    ) -> None:
        then_name, then_value = self._find_last_store_target(then_block)
        else_name, else_value = self._find_last_store_target(else_block)

        if then_name is None or else_name is None:
            return

        if then_value is None or else_value is None:
            return

        if then_name != else_name:
            return

        phi_temp_name = self.current_function.new_temp()
        phi_dest = IROperand(
            IROperandKind.TEMP,
            phi_temp_name,
            type_name=then_value.type_name or else_value.type_name or "unknown",
        )

        phi_arg_1 = IROperand(
            IROperandKind.LITERAL,
            f"({self._operand_to_phi_text(then_value)}, {then_block.label})",
            type_name=then_value.type_name,
        )
        phi_arg_2 = IROperand(
            IROperandKind.LITERAL,
            f"({self._operand_to_phi_text(else_value)}, {else_block.label})",
            type_name=else_value.type_name,
        )

        end_block.add_instruction(
            IRInstruction(
                opcode=IROpcode.PHI,
                dest=phi_dest,
                args=[phi_arg_1, phi_arg_2],
                comment=f"merge {then_name}",
            )
        )

        end_block.add_instruction(
            IRInstruction(
                opcode=IROpcode.STORE,
                args=[
                    IROperand(
                        IROperandKind.VARIABLE,
                        then_name,
                        type_name=then_value.type_name or else_value.type_name or "unknown",
                    ),
                    phi_dest,
                ],
                comment=f"store merged {then_name}",
            )
        )