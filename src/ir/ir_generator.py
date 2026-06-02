from __future__ import annotations

from typing import Optional

from src.parser.ast import *
from src.semantic.symbol_table import SymbolTable
from src.ir.ir_instructions import IROpcode, IROperand, IROperandKind, IRInstruction
from src.ir.basic_block import BasicBlock, IRFunction, IRProgram, IRGlobalVariable
from src.codegen.control_flow_generator import ControlFlowGeneratorMixin
from src.codegen.expression_generator import ExpressionGeneratorMixin

class IRGenerator(ControlFlowGeneratorMixin, ExpressionGeneratorMixin):
    def __init__(self, symbol_table: SymbolTable, type_system=None):
        self.symbol_table = symbol_table
        self.type_system = type_system
        self.program = IRProgram()
        self.current_function: Optional[IRFunction] = None
        self.current_block: Optional[BasicBlock] = None

    def generate(self, ast: ProgramNode) -> IRProgram:
        for decl in ast.declarations:
            if isinstance(decl, VarDeclStmtNode):
                self._generate_global_variable(decl)
            elif isinstance(decl, FunctionDeclNode):
                self._generate_function(decl)

        return self.program

    def get_function_ir(self, name: str) -> Optional[IRFunction]:
        for func in self.program.functions:
            if func.name == name:
                return func
        return None

    def get_all_ir(self) -> IRProgram:
        return self.program

    def _generate_global_variable(self, node: VarDeclStmtNode) -> None:
        initializer = None

        if isinstance(node.initializer, LiteralExprNode):
            initializer = node.initializer.value

        elif isinstance(node.initializer, ArrayInitializerExprNode):
            initializer = [
                element.value
                for element in node.initializer.elements
                if isinstance(element, LiteralExprNode)
            ]

        base_type_name = node.type.lexeme
        type_name = base_type_name

        array_sizes = getattr(node, "array_sizes", [])

        if array_sizes:
            for size_expr in array_sizes:
                if isinstance(size_expr, LiteralExprNode):
                    dim = int(size_expr.value)
                    type_name += f"[{dim}]"

        global_var = IRGlobalVariable(
            name=node.name.lexeme,
            type_name=type_name,
            initializer=initializer,
        )

        self.program.add_global_variable(global_var)

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


    def _emit_instruction(
        self,
        opcode: IROpcode,
        dest: IROperand | None = None,
        args: list[IROperand] | None = None,
        comment: str | None = None,
        node=None,
    ) -> IRInstruction:
        instr = IRInstruction(
            opcode=opcode,
            dest=dest,
            args=args or [],
            comment=comment,
            line=getattr(node, "line", None),
            column=getattr(node, "column", None),
            filename=getattr(node, "filename", None),
        )

        self.current_block.add_instruction(instr)
        return instr

    def _gen_stmt(self, stmt) -> None:
        if isinstance(stmt, VarDeclStmtNode):
            self._gen_var_decl(stmt)
            return

        if isinstance(stmt, ExprStmtNode):
            self._gen_expr(stmt.expression)
            return

        if isinstance(stmt, ReturnStmtNode):
            if stmt.value is None:
                self._emit_instruction(
                    IROpcode.RETURN,
                    comment="return",
                    node=stmt,
                )
            else:
                value_op = self._gen_expr(stmt.value)
                self._emit_instruction(
                    IROpcode.RETURN,
                    args=[value_op],
                    comment="return",
                    node=stmt,
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

    def _gen_var_decl(self, stmt: VarDeclStmtNode) -> None:
        var_name = stmt.name.lexeme
        base_type_name = stmt.type.lexeme
        type_name = base_type_name

        pointer_depth = getattr(stmt, "pointer_depth", 0)

        for _ in range(pointer_depth):
            type_name += "*"

        array_sizes = getattr(stmt, "array_sizes", [])
        is_array = bool(array_sizes)

        if is_array:
            total_count = 1

            for size_expr in array_sizes:
                if isinstance(size_expr, LiteralExprNode):
                    dim = int(size_expr.value)
                    total_count *= dim
                    type_name += f"[{dim}]"

            element_size = self._type_size(base_type_name)
            size = total_count * element_size
        else:
            size = self._type_size(type_name)

        var_op = IROperand(
            IROperandKind.VARIABLE,
            var_name,
            type_name=type_name,
        )

        if var_name not in self.current_function.local_variables:
            self.current_function.local_variables.append(var_name)

        self.current_function.variable_map[var_name] = var_name

        if is_array:
            self._emit_instruction(
                opcode=IROpcode.PARAM,
                args=[
                    IROperand(IROperandKind.LITERAL, 0, type_name="int"),
                    IROperand(IROperandKind.LITERAL, size, type_name="int"),
                ],
                comment=f"malloc size for {var_name}",
                node=stmt,
            )

            self._emit_instruction(
                opcode=IROpcode.CALL,
                dest=var_op,
                args=[
                    IROperand(
                        IROperandKind.VARIABLE,
                        "malloc",
                        type_name="fn(int) -> ptr",
                    )
                ],
                comment=f"malloc array {var_name}",
                node=stmt,
            )
        else:
            self._emit_instruction(
                opcode=IROpcode.ALLOCA,
                dest=var_op,
                args=[
                    IROperand(
                        IROperandKind.LITERAL,
                        size,
                        type_name="int",
                    )
                ],
                comment=f"allocate {var_name}",
                node=stmt,
            )

        if stmt.initializer is not None:
            init_op = self._gen_expr(stmt.initializer)
            self._emit_instruction(
                opcode=IROpcode.STORE,
                args=[var_op, init_op],
                comment=f"initialize {var_name}",
                node=stmt,
            )

