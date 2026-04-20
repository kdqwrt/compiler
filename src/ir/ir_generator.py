from __future__ import annotations

from typing import Optional

from src.parser.ast import *
from src.semantic.symbol_table import SymbolTable
from src.ir.ir_instructions import IROpcode, IROperand, IROperandKind, IRInstruction
from src.ir.basic_block import BasicBlock, IRFunction, IRProgram


class IRGenerator:
    def __init__(self, symbol_table: SymbolTable, type_system=None):
        self.symbol_table = symbol_table
        self.type_system = type_system
        self.program = IRProgram()
        self.current_function: Optional[IRFunction] = None
        self.current_block: Optional[BasicBlock] = None

    def generate(self, ast: ProgramNode) -> IRProgram:
        for decl in ast.declarations:
            if isinstance(decl, FunctionDeclNode):
                self._generate_function(decl)
        return self.program

    def get_function_ir(self, name: str) -> Optional[IRFunction]:
        for func in self.program.functions:
            if func.name == name:
                return func
        return None

    def get_all_ir(self) -> IRProgram:
        return self.program

    def _generate_function(self, node: FunctionDeclNode) -> None:
        ret_type = node.return_type.lexeme if node.return_type else "void"
        func = IRFunction(
            name=node.name.lexeme,
            return_type=ret_type,
            params=[p.name.lexeme for p in node.parameters],
            param_types=[p.type.lexeme for p in node.parameters],
        )
        self.program.add_function(func)
        self.current_function = func

        entry = BasicBlock("entry")
        func.add_block(entry)
        self.current_block = entry

        for stmt in node.body.statements:
            self._gen_stmt(stmt)

        # implicit return for void functions
        if (
            self.current_block is not None
            and not self.current_block.is_terminated()
            and ret_type == "void"
        ):
            self.current_block.add_instruction(
                IRInstruction(IROpcode.RETURN, comment="implicit return")
            )

        self.current_function = None
        self.current_block = None

    def _switch_block(self, block: BasicBlock) -> None:
        self.current_block = block

    def _emit_jump(self, opcode: IROpcode, *args: IROperand, comment: str | None = None) -> None:
        self.current_block.add_instruction(
            IRInstruction(opcode=opcode, args=list(args), comment=comment)
        )

    def _gen_stmt(self, stmt) -> None:
        if isinstance(stmt, VarDeclStmtNode):
            self._gen_var_decl(stmt)
            return

        if isinstance(stmt, ExprStmtNode):
            self._gen_expr(stmt.expression)
            return

        if isinstance(stmt, ReturnStmtNode):
            if stmt.value is None:
                self.current_block.add_instruction(
                    IRInstruction(IROpcode.RETURN, comment="return")
                )
            else:
                value_op = self._gen_expr(stmt.value)
                self.current_block.add_instruction(
                    IRInstruction(IROpcode.RETURN, args=[value_op], comment="return")
                )
            return

        if isinstance(stmt, IfStmtNode):
            self._gen_if(stmt)
            return

        if isinstance(stmt, WhileStmtNode):
            self._gen_while(stmt)
            return

        if isinstance(stmt, ForStmtNode):
            self._gen_for(stmt)
            return

        raise NotImplementedError(
            f"IR generation for statement {type(stmt).__name__} is not implemented yet"
        )

    def _gen_if(self, stmt: IfStmtNode) -> None:
        cond_op = self._gen_expr(stmt.condition)

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

        # если условие ложно -> else/end
        self._emit_jump(
            IROpcode.JUMP_IF_NOT,
            cond_op,
            IROperand(IROperandKind.LABEL, else_label),
            comment="if false",
        )
        self.current_function.add_edge(self.current_block.label, else_label)

        # иначе идём в then
        self._emit_jump(
            IROpcode.JUMP,
            IROperand(IROperandKind.LABEL, then_label),
            comment="if true",
        )
        self.current_function.add_edge(self.current_block.label, then_label)

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

    def _gen_var_decl(self, stmt: VarDeclStmtNode) -> None:
        var_name = stmt.name.lexeme
        type_name = stmt.type.lexeme
        size = self._type_size(type_name)

        var_op = IROperand(IROperandKind.VARIABLE, var_name, type_name=type_name)

        if var_name not in self.current_function.local_variables:
            self.current_function.local_variables.append(var_name)
        self.current_function.variable_map[var_name] = var_name

        self.current_block.add_instruction(
            IRInstruction(
                opcode=IROpcode.ALLOCA,
                dest=var_op,
                args=[IROperand(IROperandKind.LITERAL, size, type_name="int")],
                comment=f"allocate {var_name}",
            )
        )

        if stmt.initializer is not None:
            init_op = self._gen_expr(stmt.initializer)
            self.current_block.add_instruction(
                IRInstruction(
                    opcode=IROpcode.STORE,
                    args=[var_op, init_op],
                    comment=f"initialize {var_name}",
                )
            )

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
                "&&": IROpcode.AND,
                "||": IROpcode.OR,
            }

            instr = IRInstruction(
                opcode=opcode_map[expr.operator.lexeme],
                dest=dest,
                args=[left, right],
                comment=f"{expr.operator.lexeme} expression",
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