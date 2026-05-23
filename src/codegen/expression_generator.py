from __future__ import annotations
from src.parser.ast import *
from src.ir.basic_block import BasicBlock
from src.ir.ir_instructions import IROpcode, IROperand, IROperandKind, IRInstruction

class ExpressionGeneratorMixin:
    def _gen_expr(self, expr) -> IROperand:
        if isinstance(expr, LiteralExprNode):
            return IROperand(
                IROperandKind.LITERAL,
                expr.value,
                type_name=self._safe_type_name(expr),
            )

        if isinstance(expr, IdentifierExprNode):
            temp_name = self.current_function.new_temp()
            dest = IROperand(
                IROperandKind.TEMP,
                temp_name,
                type_name=self._safe_type_name(expr),
            )
            src = IROperand(
                IROperandKind.VARIABLE,
                expr.name.lexeme,
                type_name=self._safe_type_name(expr),
            )

            self.current_block.add_instruction(
                IRInstruction(
                    opcode=IROpcode.LOAD,
                    dest=dest,
                    args=[src],
                    comment=f"load {expr.name.lexeme}",
                )
            )
            return dest

        if isinstance(expr, StructAccessExprNode):
            addr_op = self._struct_field_address(expr)

            temp_name = self.current_function.new_temp()
            dest = IROperand(
                IROperandKind.TEMP,
                temp_name,
                type_name=self._safe_type_name(expr),
            )

            self.current_block.add_instruction(
                IRInstruction(
                    opcode=IROpcode.LOAD,
                    dest=dest,
                    args=[addr_op],
                    comment=f"load field {expr.primary.name.lexeme}.{expr.field.lexeme}",
                )
            )
            return dest

        if isinstance(expr, BinaryExprNode):
            operator = expr.operator.lexeme

            if operator == "&&":
                return self._gen_logical_and(expr)

            if operator == "||":
                return self._gen_logical_or(expr)

            left = self._gen_expr(expr.left)
            right = self._gen_expr(expr.right)



            temp_name = self.current_function.new_temp()
            dest = IROperand(
                IROperandKind.TEMP,
                temp_name,
                type_name=self._safe_type_name(expr),
            )

            opcode_map = {
                "+": IROpcode.ADD,
                "-": IROpcode.SUB,
                "*": IROpcode.MUL,
                "/": IROpcode.DIV,
                "%": IROpcode.MOD,
                "==": IROpcode.CMP_EQ,
                "!=": IROpcode.CMP_NE,
                "<": IROpcode.CMP_LT,
                "<=": IROpcode.CMP_LE,
                ">": IROpcode.CMP_GT,
                ">=": IROpcode.CMP_GE,
            }

            instr = IRInstruction(
                opcode=opcode_map[operator],
                dest=dest,
                args=[left, right],
                comment=f"{operator} expression",
            )
            self.current_block.add_instruction(instr)
            return dest

        if isinstance(expr, UnaryExprNode):
            operand = self._gen_expr(expr.operand)
            operator = expr.operator.lexeme

            if operator == "-":
                temp_name = self.current_function.new_temp()
                dest = IROperand(
                    IROperandKind.TEMP,
                    temp_name,
                    type_name=self._safe_type_name(expr),
                )
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.NEG,
                        dest=dest,
                        args=[operand],
                        comment="unary minus",
                    )
                )
                return dest

            if operator == "!":
                temp_name = self.current_function.new_temp()
                dest = IROperand(
                    IROperandKind.TEMP,
                    temp_name,
                    type_name=self._safe_type_name(expr),
                )
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.NOT,
                        dest=dest,
                        args=[operand],
                        comment="logical not",
                    )
                )
                return dest

            if operator in {"++", "--"}:
                if not isinstance(expr.operand, IdentifierExprNode):
                    raise NotImplementedError(
                        "IR generation for ++/-- is only implemented for identifiers"
                    )

                var_name = expr.operand.name.lexeme
                var_op = IROperand(
                    IROperandKind.VARIABLE,
                    var_name,
                    type_name=self._safe_type_name(expr.operand),
                )

                loaded_name = self.current_function.new_temp()
                loaded = IROperand(
                    IROperandKind.TEMP,
                    loaded_name,
                    type_name=self._safe_type_name(expr.operand),
                )
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.LOAD,
                        dest=loaded,
                        args=[var_op],
                        comment=f"load {var_name}",
                    )
                )

                result_name = self.current_function.new_temp()
                result = IROperand(
                    IROperandKind.TEMP,
                    result_name,
                    type_name=self._safe_type_name(expr),
                )
                op = IROpcode.ADD if operator == "++" else IROpcode.SUB
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=op,
                        dest=result,
                        args=[loaded, IROperand(IROperandKind.LITERAL, 1, type_name="int")],
                        comment=f"{operator} {var_name}",
                    )
                )

                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.STORE,
                        args=[var_op, result],
                        comment=f"store {var_name}",
                    )
                )
                return result

            raise NotImplementedError(
                f"IR generation for unary operator {operator!r} is not implemented yet"
            )

        if isinstance(expr, AssignmentExprNode):
            if isinstance(expr.target, IdentifierExprNode):
                target_name = expr.target.name.lexeme
                target_type = self._safe_type_name(expr.target)
                target_op = IROperand(
                    IROperandKind.VARIABLE,
                    target_name,
                    type_name=target_type,
                )

            elif isinstance(expr.target, StructAccessExprNode):
                target_name = f"{expr.target.primary.name.lexeme}.{expr.target.field.lexeme}"
                target_type = self._safe_type_name(expr.target)
                target_op = self._struct_field_address(expr.target)

            else:
                raise NotImplementedError(
                    "IR generation for assignment target is only implemented for identifiers and struct fields"
                )

            operator = expr.operator.lexeme

            if operator == "=":
                value_op = self._gen_expr(expr.value)
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.STORE,
                        args=[target_op, value_op],
                        comment=f"{target_name} = ...",
                    )
                )
                return value_op

            compound_map = {
                "+=": IROpcode.ADD,
                "-=": IROpcode.SUB,
                "*=": IROpcode.MUL,
                "/=": IROpcode.DIV,
            }

            if operator in compound_map:
                loaded_name = self.current_function.new_temp()
                loaded = IROperand(
                    IROperandKind.TEMP,
                    loaded_name,
                    type_name=target_type,
                )
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.LOAD,
                        dest=loaded,
                        args=[target_op],
                        comment=f"load {target_name}",
                    )
                )

                value_op = self._gen_expr(expr.value)

                result_name = self.current_function.new_temp()
                result = IROperand(
                    IROperandKind.TEMP,
                    result_name,
                    type_name=self._safe_type_name(expr),
                )
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=compound_map[operator],
                        dest=result,
                        args=[loaded, value_op],
                        comment=f"{target_name} {operator} ...",
                    )
                )

                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.STORE,
                        args=[target_op, result],
                        comment=f"store {target_name}",
                    )
                )
                return result

            raise NotImplementedError(
                f"IR generation for assignment operator {operator!r} is not implemented yet"
            )

        if isinstance(expr, CallExprNode):
            if not isinstance(expr.callee, IdentifierExprNode):
                raise NotImplementedError(
                    "IR generation for non-identifier call targets is not implemented yet"
                )

            for i, arg in enumerate(expr.arguments):
                arg_op = self._gen_expr(arg)
                self.current_block.add_instruction(
                    IRInstruction(
                        IROpcode.PARAM,
                        args=[
                            IROperand(IROperandKind.LITERAL, i, type_name="int"),
                            arg_op,
                        ],
                        comment=f"param {i}",
                    )
                )

            func_name = expr.callee.name.lexeme
            func_op = IROperand(
                IROperandKind.VARIABLE,
                func_name,
                type_name="function",
            )

            result_type = self._safe_type_name(expr)

            if result_type == "void":
                self.current_block.add_instruction(
                    IRInstruction(
                        opcode=IROpcode.CALL,
                        args=[func_op],
                        comment=f"call {func_name}",
                    )
                )
                return IROperand(IROperandKind.LITERAL, None, type_name="void")

            result_name = self.current_function.new_temp()
            result_temp = IROperand(
                IROperandKind.TEMP,
                result_name,
                type_name=result_type,
            )

            self.current_block.add_instruction(
                IRInstruction(
                    opcode=IROpcode.CALL,
                    dest=result_temp,
                    args=[func_op],
                    comment=f"call {func_name}",
                )
            )

            return result_temp

        raise NotImplementedError(
            f"IR generation for expression {type(expr).__name__} is not implemented yet"
        )





    def _emit_move(self, dest: IROperand, value: IROperand, comment: str) -> None:
        self.current_block.add_instruction(
            IRInstruction(
                opcode=IROpcode.MOVE,
                dest=dest,
                args=[value],
                comment=comment,
            )
        )

    def _gen_logical_and(self, expr: BinaryExprNode) -> IROperand:
        result = IROperand(
            IROperandKind.TEMP,
            self.current_function.new_temp(),
            type_name="bool",
        )

        rhs_label = self.current_function.new_label("and_rhs")
        true_label = self.current_function.new_label("and_true")
        false_label = self.current_function.new_label("and_false")
        end_label = self.current_function.new_label("and_end")

        rhs_block = BasicBlock(rhs_label)
        true_block = BasicBlock(true_label)
        false_block = BasicBlock(false_label)
        end_block = BasicBlock(end_label)

        self.current_function.add_block(rhs_block)
        self.current_function.add_block(true_block)
        self.current_function.add_block(false_block)
        self.current_function.add_block(end_block)

        left = self._gen_expr(expr.left)

        self._emit_jump(
            IROpcode.JUMP_IF_NOT,
            left,
            IROperand(IROperandKind.LABEL, false_label),
            comment="&& short-circuit false",
        )
        self.current_function.add_edge(self.current_block.label, false_label)

        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, rhs_label),
            comment="&& evaluate right",
        )
        self.current_function.add_edge(self.current_block.label, rhs_label)

        self._switch_block(rhs_block)
        right = self._gen_expr(expr.right)

        self._emit_jump(
            IROpcode.JUMP_IF_NOT,
            right,
            IROperand(IROperandKind.LABEL, false_label),
            comment="&& right false",
        )
        self.current_function.add_edge(self.current_block.label, false_label)

        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, true_label),
            comment="&& true",
        )
        self.current_function.add_edge(self.current_block.label, true_label)

        self._switch_block(true_block)
        self._emit_move(
            result,
            IROperand(IROperandKind.LITERAL, 1, type_name="bool"),
            "&& result true",
        )
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, end_label),
            comment="&& end",
        )
        self.current_function.add_edge(self.current_block.label, end_label)

        self._switch_block(false_block)
        self._emit_move(
            result,
            IROperand(IROperandKind.LITERAL, 0, type_name="bool"),
            "&& result false",
        )
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, end_label),
            comment="&& end",
        )
        self.current_function.add_edge(self.current_block.label, end_label)

        self._switch_block(end_block)
        return result

    def _gen_logical_or(self, expr: BinaryExprNode) -> IROperand:
        result = IROperand(
            IROperandKind.TEMP,
            self.current_function.new_temp(),
            type_name="bool",
        )

        rhs_label = self.current_function.new_label("or_rhs")
        true_label = self.current_function.new_label("or_true")
        false_label = self.current_function.new_label("or_false")
        end_label = self.current_function.new_label("or_end")

        rhs_block = BasicBlock(rhs_label)
        true_block = BasicBlock(true_label)
        false_block = BasicBlock(false_label)
        end_block = BasicBlock(end_label)

        self.current_function.add_block(rhs_block)
        self.current_function.add_block(true_block)
        self.current_function.add_block(false_block)
        self.current_function.add_block(end_block)

        left = self._gen_expr(expr.left)

        self._emit_jump(
            IROpcode.JUMP_IF,
            left,
            IROperand(IROperandKind.LABEL, true_label),
            comment="|| short-circuit true",
        )
        self.current_function.add_edge(self.current_block.label, true_label)

        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, rhs_label),
            comment="|| evaluate right",
        )
        self.current_function.add_edge(self.current_block.label, rhs_label)

        self._switch_block(rhs_block)
        right = self._gen_expr(expr.right)

        self._emit_jump(
            IROpcode.JUMP_IF,
            right,
            IROperand(IROperandKind.LABEL, true_label),
            comment="|| right true",
        )
        self.current_function.add_edge(self.current_block.label, true_label)

        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, false_label),
            comment="|| false",
        )
        self.current_function.add_edge(self.current_block.label, false_label)

        self._switch_block(true_block)
        self._emit_move(
            result,
            IROperand(IROperandKind.LITERAL, 1, type_name="bool"),
            "|| result true",
        )
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, end_label),
            comment="|| end",
        )
        self.current_function.add_edge(self.current_block.label, end_label)

        self._switch_block(false_block)
        self._emit_move(
            result,
            IROperand(IROperandKind.LITERAL, 0, type_name="bool"),
            "|| result false",
        )
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, end_label),
            comment="|| end",
        )
        self.current_function.add_edge(self.current_block.label, end_label)

        self._switch_block(end_block)
        return result

    def _struct_field_offset(self, struct_type_name: str, field_name: str) -> int:
        symbol = self.symbol_table.lookup(struct_type_name)
        if symbol is None or getattr(symbol, "fields", None) is None:
            raise NotImplementedError(
                f"Struct layout for '{struct_type_name}' is not available"
            )

        offset = 0
        for fname, ftype in symbol.fields.items():
            if fname == field_name:
                return offset
            offset += self._type_size(str(ftype))

        raise NotImplementedError(
            f"Field '{field_name}' not found in struct '{struct_type_name}'"
        )

    def _struct_field_address(self, expr: StructAccessExprNode) -> IROperand:
        if not isinstance(expr.primary, IdentifierExprNode):
            raise NotImplementedError(
                "IR generation for nested/non-identifier struct access is not implemented yet"
            )

        base_name = expr.primary.name.lexeme
        base_type = self._safe_type_name(expr.primary)
        field_name = expr.field.lexeme
        field_type = self._safe_type_name(expr)

        offset = self._struct_field_offset(base_type, field_name)

        addr_temp_name = self.current_function.new_temp()
        addr_temp = IROperand(
            IROperandKind.TEMP,
            addr_temp_name,
            type_name=f"{field_type}*",
        )

        base_operand = IROperand(
            IROperandKind.VARIABLE,
            base_name,
            type_name=base_type,
        )

        offset_operand = IROperand(
            IROperandKind.LITERAL,
            offset,
            type_name="int",
        )

        self.current_block.add_instruction(
            IRInstruction(
                opcode=IROpcode.GEP,
                dest=addr_temp,
                args=[base_operand, offset_operand],
                comment=f"address of {base_name}.{field_name}",
            )
        )

        return IROperand(
            IROperandKind.MEMORY,
            addr_temp.value,
            type_name=field_type,
        )

    def _type_size(self, type_name: str) -> int:
        if type_name == "int":
            return 4
        if type_name == "float":
            return 8
        if type_name == "bool":
            return 1
        if type_name == "string":
            return 8

        symbol = self.symbol_table.lookup(type_name)
        if symbol is not None and getattr(symbol, "fields", None) is not None:
            size = 0
            for _, ftype in symbol.fields.items():
                size += self._type_size(str(ftype))
            return size

        return 8

    def _safe_type_name(self, node) -> str:
        inferred = getattr(node, "inferred_type", None)
        if inferred is None:
            return "unknown"
        return str(inferred)