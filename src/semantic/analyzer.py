from __future__ import annotations

from typing import Optional
from src.parser.ast import *
from src.parser.visitor import ASTVisitor
from src.semantic.symbol_table import SymbolTable, SymbolInfo, SymbolKind, ScopeKind
from src.semantic.type_system import (
    Type,
    INT_TYPE,
    FLOAT_TYPE,
    BOOL_TYPE,
    VOID_TYPE,
    STRING_TYPE,
    ERROR_TYPE,
    get_builtin_type,
    make_struct_type,
    make_function_type,
)
from src.semantic.errors import SemanticErrorReporter, SemanticErrorKind


class SemanticAnalyzer(ASTVisitor):
    def __init__(self, file_name: str = "<input>"):
        self.file_name = file_name
        self.symbol_table = SymbolTable()
        self.error_reporter = SemanticErrorReporter(file_name)

        self.current_function = None
        self.current_function_return_type: Optional[Type] = None
        self.current_stack_offset = 0

        self.loop_depth = 0
        self.current_statement_index = -1

        self.decorated_ast = None

    def analyze(self, ast: ProgramNode) -> ProgramNode:
        self.decorated_ast = ast

        self._declare_builtin_functions()
        self._collect_global_declarations(ast)

        for decl in ast.declarations:
            if isinstance(decl, FunctionDeclNode):
                self.visit(decl)

        return ast

    def get_errors(self):
        return self.error_reporter.get_errors()

    def get_symbol_table(self) -> SymbolTable:
        return self.symbol_table

    def get_decorated_ast(self):
        return self.decorated_ast

    def _declare_builtin_functions(self) -> None:
        builtin_functions = [
            ("print_int", VOID_TYPE, [INT_TYPE]),
        ]

        for func_name, return_type, param_types in builtin_functions:
            if self.symbol_table.lookup_local(func_name) is not None:
                continue

            param_symbols = []

            for i, param_type in enumerate(param_types):
                param_symbols.append(
                    SymbolInfo(
                        name=f"arg{i}",
                        type=param_type,
                        kind=SymbolKind.PARAMETER,
                        line=0,
                        column=0,
                        initialized=True,
                    )
                )

            function_type = make_function_type(param_types, return_type)

            symbol = SymbolInfo(
                name=func_name,
                type=function_type,
                kind=SymbolKind.FUNCTION,
                line=0,
                column=0,
                return_type=return_type,
                params=param_symbols,
                initialized=True,
            )

            self.symbol_table.insert(func_name, symbol)


    def _collect_global_declarations(self, ast: ProgramNode) -> None:
        for decl in ast.declarations:
            if isinstance(decl, StructDeclNode):
                self._declare_struct(decl)
            elif isinstance(decl, FunctionDeclNode):
                self._declare_function(decl)
            elif isinstance(decl, VarDeclStmtNode):
                self._declare_global_variable(decl)

    def _declare_struct(self, node: StructDeclNode) -> None:
        struct_name = node.name.lexeme

        if self.symbol_table.lookup_local(struct_name) is not None:
            self._duplicate_declaration(node.name, struct_name)
            return

        field_map = {}
        field_symbols = {}

        for field_index, field in enumerate(node.fields):
            field_name = field.name.lexeme

            if field_name in field_map:
                self.error_reporter.add(
                    SemanticErrorKind.DUPLICATE_DECLARATION,
                    f"duplicate field declaration '{field_name}' in struct '{struct_name}'",
                    field.name.line,
                    field.name.column,
                    context=f"in struct '{struct_name}'",
                )
                continue

            field_type = self.resolve_type_token(field.type)

            if field_type == VOID_TYPE:
                self.error_reporter.add(
                    SemanticErrorKind.UNKNOWN_TYPE,
                    f"field '{field_name}' cannot have type void",
                    field.name.line,
                    field.name.column,
                    context=f"in struct '{struct_name}'",
                )
                field_type = ERROR_TYPE

            field_symbol = SymbolInfo(
                name=field_name,
                type=field_type,
                kind=SymbolKind.FIELD,
                line=field.name.line,
                column=field.name.column,
                initialized=True,
                declaration_order=field_index,
            )

            field_map[field_name] = field_type
            field_symbols[field_name] = field_symbol

        struct_type = make_struct_type(struct_name, field_map)

        symbol = SymbolInfo(
            name=struct_name,
            type=struct_type,
            kind=SymbolKind.STRUCT,
            line=node.name.line,
            column=node.name.column,
            fields=field_symbols,
            initialized=True,
        )

        self.symbol_table.insert(struct_name, symbol)

        self.symbol_table.enter_scope(f"struct:{struct_name}", ScopeKind.STRUCT)
        for field_symbol in field_symbols.values():
            self.symbol_table.insert(field_symbol.name, field_symbol)
        self.symbol_table.exit_scope()

    def _declare_function(self, node: FunctionDeclNode) -> None:
        func_name = node.name.lexeme

        if self.symbol_table.lookup_local(func_name) is not None:
            self._duplicate_declaration(node.name, func_name)
            return

        return_type = self.resolve_type_token(node.return_type)

        param_symbols = []
        param_types = []
        seen_params = set()

        for param in node.parameters:
            param_name = param.name.lexeme

            if param_name in seen_params:
                self.error_reporter.add(
                    SemanticErrorKind.DUPLICATE_DECLARATION,
                    f"duplicate parameter declaration '{param_name}'",
                    param.name.line,
                    param.name.column,
                    context=f"in function '{func_name}'",
                )
                continue

            seen_params.add(param_name)

            param_type = self.resolve_type_token(param.type)
            param_types.append(param_type)

            param_symbols.append(
                SymbolInfo(
                    name=param_name,
                    type=param_type,
                    kind=SymbolKind.PARAMETER,
                    line=param.name.line,
                    column=param.name.column,
                    initialized=True,
                )
            )

        function_type = make_function_type(param_types, return_type)

        symbol = SymbolInfo(
            name=func_name,
            type=function_type,
            kind=SymbolKind.FUNCTION,
            line=node.name.line,
            column=node.name.column,
            return_type=return_type,
            params=param_symbols,
            initialized=True,
        )

        self.symbol_table.insert(func_name, symbol)

    def _declare_global_variable(self, node: VarDeclStmtNode) -> None:
        from src.semantic.type_system import get_type_size, get_type_alignment

        var_name = node.name.lexeme

        if self.symbol_table.lookup_local(var_name) is not None:
            self._duplicate_declaration(node.name, var_name)
            return

        var_type = self.resolve_type_token(node.type)

        if var_type == VOID_TYPE:
            self.error_reporter.add(
                SemanticErrorKind.UNKNOWN_TYPE,
                f"variable '{var_name}' cannot have type void",
                node.name.line,
                node.name.column,
                context="in global scope",
            )
            var_type = ERROR_TYPE

        # Исправлено: явно определяем initialized
        initialized = node.initializer is not None

        if node.initializer is not None:
            init_type = self.visit(node.initializer)

            if init_type is not None and not var_type.is_assignable_from(init_type):
                self.error_reporter.add(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"type mismatch in initialization of '{var_name}'",
                    node.initializer.line,
                    node.initializer.column,
                    context="in global scope",
                    expected=str(var_type),
                    actual=str(init_type),
                )

        symbol = SymbolInfo(
            name=var_name,
            type=var_type,
            kind=SymbolKind.VARIABLE,
            line=node.name.line,
            column=node.name.column,
            initialized=initialized,  # Теперь передается явно
        )

        symbol.size = get_type_size(var_type)
        symbol.alignment = get_type_alignment(var_type)

        self.symbol_table.insert(var_name, symbol)

    def visit_FunctionDeclNode(self, node: FunctionDeclNode):
        function_symbol = self.symbol_table.lookup(node.name.lexeme)
        if function_symbol is None:
            return

        self.current_function = function_symbol
        self.current_function_return_type = function_symbol.return_type
        self.current_stack_offset = 0

        self.symbol_table.enter_scope(node.name.lexeme, ScopeKind.FUNCTION)

        seen_locally = set()
        for param_symbol in function_symbol.params:
            if param_symbol.name in seen_locally:
                continue
            seen_locally.add(param_symbol.name)
            self.symbol_table.insert(param_symbol.name, param_symbol)


        self._predeclare_block_variables(node.body.statements)
        self._walk_block_statements(node.body.statements)

        self.symbol_table.exit_scope()

        self.current_function = None
        self.current_function_return_type = None

    def visit_BlockStmtNode(self, node: BlockStmtNode):
        self.symbol_table.enter_scope("block", ScopeKind.BLOCK)
        self._predeclare_block_variables(node.statements)
        self._walk_block_statements(node.statements)
        self.symbol_table.exit_scope()

    def visit_VarDeclStmtNode(self, node: VarDeclStmtNode):
        from src.semantic.type_system import get_type_size, get_type_alignment

        var_name = node.name.lexeme
        existing_symbol = self.symbol_table.lookup_local(var_name)

        if existing_symbol is not None and not (
                existing_symbol.is_placeholder
                and existing_symbol.line == node.name.line
                and existing_symbol.column == node.name.column
        ):
            self._duplicate_declaration(node.name, var_name)
            return

        var_type = self.resolve_type_token(node.type)

        if var_type == VOID_TYPE:
            self.error_reporter.add(
                SemanticErrorKind.UNKNOWN_TYPE,
                f"variable '{var_name}' cannot have type void",
                node.name.line,
                node.name.column,
                context=self._current_context(),
            )
            var_type = ERROR_TYPE

        initialized = node.initializer is not None

        if node.initializer is not None:
            init_type = self.visit(node.initializer)

            if init_type is not None and init_type != ERROR_TYPE and not var_type.is_assignable_from(init_type):
                self.error_reporter.add(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"type mismatch in initialization of '{var_name}'",
                    node.initializer.line,
                    node.initializer.column,
                    context=self._current_context(),
                    expected=str(var_type),
                    actual=str(init_type),
                )

        symbol = SymbolInfo(
            name=var_name,
            type=var_type,
            kind=SymbolKind.VARIABLE,
            line=node.name.line,
            column=node.name.column,
            initialized=initialized,
            size=get_type_size(var_type),
            alignment=get_type_alignment(var_type),
            stack_offset=self.current_stack_offset,
            declaration_order=existing_symbol.declaration_order if existing_symbol else -1,
            is_placeholder=False,
        )

        self.current_stack_offset += symbol.size or 0

        if existing_symbol is not None and existing_symbol.is_placeholder:
            self.symbol_table.replace_local(var_name, symbol)
        else:
            self.symbol_table.insert(var_name, symbol)

    def visit_ExprStmtNode(self, node: ExprStmtNode):
        self.visit(node.expression)

    def visit_IfStmtNode(self, node: IfStmtNode):
        condition_type = self.visit(node.condition)

        if condition_type is not None and not condition_type.is_bool() and condition_type != ERROR_TYPE:
            self.error_reporter.add(
                SemanticErrorKind.INVALID_CONDITION_TYPE,
                "if condition must have type bool",
                node.condition.line,
                node.condition.column,
                context=self._current_context(),
                expected="bool",
                actual=str(condition_type),
            )

        self.visit(node.then_branch)
        if node.else_branch is not None:
            self.visit(node.else_branch)

    def visit_WhileStmtNode(self, node: WhileStmtNode):
        condition_type = self.visit(node.condition)

        if condition_type is not None and not condition_type.is_bool() and condition_type != ERROR_TYPE:
            self.error_reporter.add(
                SemanticErrorKind.INVALID_CONDITION_TYPE,
                "while condition must have type bool",
                node.condition.line,
                node.condition.column,
                context=self._current_context(),
                expected="bool",
                actual=str(condition_type),
            )

        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1

    def visit_ForStmtNode(self, node: ForStmtNode):
        self.symbol_table.enter_scope("for", ScopeKind.BLOCK)

        if node.init is not None:
            self.visit(node.init)

        if node.condition is not None:
            condition_type = self.visit(node.condition)
            if condition_type is not None and not condition_type.is_bool() and condition_type != ERROR_TYPE:
                self.error_reporter.add(
                    SemanticErrorKind.INVALID_CONDITION_TYPE,
                    "for condition must have type bool",
                    node.condition.line,
                    node.condition.column,
                    context=self._current_context(),
                    expected="bool",
                    actual=str(condition_type),
                )

        self.loop_depth += 1
        self.visit(node.body)

        if node.update is not None:
            self.visit(node.update)

        self.loop_depth -= 1
        self.symbol_table.exit_scope()

    def visit_ReturnStmtNode(self, node: ReturnStmtNode):
        expected_type = self.current_function_return_type or VOID_TYPE

        if node.value is None:
            if expected_type != VOID_TYPE:
                self.error_reporter.add(
                    SemanticErrorKind.INVALID_RETURN_TYPE,
                    "return statement is missing a value",
                    node.line,
                    node.column,
                    context=self._current_context(),
                    expected=str(expected_type),
                    actual="void",
                )
            return VOID_TYPE

        actual_type = self.visit(node.value)

        if expected_type == VOID_TYPE:
            self.error_reporter.add(
                SemanticErrorKind.INVALID_RETURN_TYPE,
                "void function must not return a value",
                node.value.line,
                node.value.column,
                context=self._current_context(),
                expected="void",
                actual=str(actual_type),
            )
            return ERROR_TYPE

        if actual_type is not None and not expected_type.is_assignable_from(actual_type):
            self.error_reporter.add(
                SemanticErrorKind.INVALID_RETURN_TYPE,
                "return type does not match function return type",
                node.value.line,
                node.value.column,
                context=self._current_context(),
                expected=str(expected_type),
                actual=str(actual_type),
            )
            return ERROR_TYPE

        return expected_type

    def visit_IdentifierExprNode(self, node: IdentifierExprNode):
        name = node.name.lexeme
        symbol = self.symbol_table.lookup(name)

        if symbol is None:
            self.error_reporter.add(
                SemanticErrorKind.UNDECLARED_IDENTIFIER,
                f"undeclared identifier '{name}'",
                node.name.line,
                node.name.column,
                context=self._current_context(),
            )
            node.inferred_type = ERROR_TYPE
            node.symbol = None
            return ERROR_TYPE

        node.symbol = symbol
        node.inferred_type = symbol.type

        # Проверка use-before-declaration нужна только для локальных переменных,
        # но не для параметров функции
        if (
                symbol.kind == SymbolKind.VARIABLE
                and symbol.scope_name == self.symbol_table.current_scope.name
                and symbol.scope_depth == self.symbol_table.current_scope.depth
                and symbol.declaration_order > self.current_statement_index >= 0
        ):
            self.error_reporter.add(
                SemanticErrorKind.USE_BEFORE_DECLARATION,
                f"identifier '{name}' is used before its declaration",
                node.name.line,
                node.name.column,
                context=self._current_context(),
                note=f"declared later at {symbol.line}:{symbol.column}",
            )
            return ERROR_TYPE

        if symbol.kind in {SymbolKind.VARIABLE, SymbolKind.PARAMETER} and not symbol.initialized:
            self.error_reporter.add(
                SemanticErrorKind.UNINITIALIZED_VARIABLE,
                f"variable '{name}' may be used before initialization",
                node.name.line,
                node.name.column,
                context=self._current_context(),
            )

        return symbol.type

    def visit_LiteralExprNode(self, node: LiteralExprNode):
        literal_type = self._infer_literal_type(node.value)

        if literal_type == INT_TYPE and isinstance(node.value, int):
            INT_MIN = -(2 ** 31)
            INT_MAX = 2 ** 31 - 1

            if node.value < INT_MIN or node.value > INT_MAX:
                self.error_reporter.add(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"integer literal out of 32-bit range: {node.value}",
                    node.line,
                    node.column,
                    context=self._current_context(),
                    expected=f"{INT_MIN}..{INT_MAX}",
                    actual=str(node.value),
                )
                node.inferred_type = ERROR_TYPE
                node.constant_value = node.value
                return ERROR_TYPE

        node.inferred_type = literal_type
        node.constant_value = node.value
        return literal_type

    def visit_UnaryExprNode(self, node: UnaryExprNode):
        operand_type = self.visit(node.operand)
        operator = node.operator.lexeme

        if operand_type is None:
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator == "-":
            if operand_type.is_numeric():
                node.inferred_type = operand_type
                operand_const = getattr(node.operand, "constant_value", None)
                if operand_const is not None:
                    try:
                        node.constant_value = -operand_const
                    except Exception:
                        node.constant_value = None
                return operand_type

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                "unary '-' requires numeric operand",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="int or float",
                actual=str(operand_type),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator == "!":
            if operand_type.is_bool():
                node.inferred_type = BOOL_TYPE
                operand_const = getattr(node.operand, "constant_value", None)
                if operand_const is not None:
                    try:
                        node.constant_value = not operand_const
                    except Exception:
                        node.constant_value = None
                return BOOL_TYPE

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                "unary '!' requires bool operand",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="bool",
                actual=str(operand_type),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator in {"++", "--"}:
            if not isinstance(node.operand, (IdentifierExprNode, StructAccessExprNode)):
                self.error_reporter.add(
                    SemanticErrorKind.INVALID_ASSIGNMENT_TARGET,
                    f"operator '{operator}' requires an assignable target",
                    node.operator.line,
                    node.operator.column,
                    context=self._current_context(),
                )
                node.inferred_type = ERROR_TYPE
                return ERROR_TYPE

            if not operand_type.is_numeric():
                self.error_reporter.add(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"operator '{operator}' requires numeric operand",
                    node.operator.line,
                    node.operator.column,
                    context=self._current_context(),
                    expected="int or float",
                    actual=str(operand_type),
                )
                node.inferred_type = ERROR_TYPE
                return ERROR_TYPE

            target_symbol = getattr(node.operand, "symbol", None)
            if target_symbol is not None and not target_symbol.mutable:
                self.error_reporter.add(
                    SemanticErrorKind.INVALID_ASSIGNMENT_TARGET,
                    f"operator '{operator}' cannot be applied to immutable target",
                    node.operator.line,
                    node.operator.column,
                    context=self._current_context(),
                    note=f"'{target_symbol.name}' is immutable",
                )
                node.inferred_type = ERROR_TYPE
                return ERROR_TYPE

            node.inferred_type = operand_type
            return operand_type

        node.inferred_type = ERROR_TYPE
        return ERROR_TYPE

    def visit_BinaryExprNode(self, node: BinaryExprNode):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        operator = node.operator.lexeme

        if left_type is None or right_type is None:
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator in {"+", "-", "*", "/"}:
            if left_type.is_numeric() and right_type.is_numeric():
                if left_type == FLOAT_TYPE or right_type == FLOAT_TYPE:
                    node.inferred_type = FLOAT_TYPE
                else:
                    node.inferred_type = INT_TYPE
                self._try_fold_binary(node, operator)
                return node.inferred_type

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                f"operator '{operator}' requires numeric operands",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="numeric operands",
                actual=f"{left_type} and {right_type}",
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator == "%":
            if left_type == INT_TYPE and right_type == INT_TYPE:
                node.inferred_type = INT_TYPE
                self._try_fold_binary(node, operator)
                return INT_TYPE

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                "operator '%' requires int operands",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="int and int",
                actual=f"{left_type} and {right_type}",
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator in {"<", "<=", ">", ">="}:
            if left_type.is_numeric() and right_type.is_numeric():
                node.inferred_type = BOOL_TYPE
                self._try_fold_binary(node, operator)
                return BOOL_TYPE

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                f"operator '{operator}' requires numeric operands",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="numeric operands",
                actual=f"{left_type} and {right_type}",
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator in {"==", "!="}:
            if left_type.equals(right_type) or left_type.is_assignable_from(
                    right_type) or right_type.is_assignable_from(left_type):
                node.inferred_type = BOOL_TYPE
                self._try_fold_binary(node, operator)
                return BOOL_TYPE

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                f"operator '{operator}' requires compatible operands",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="compatible operand types",
                actual=f"{left_type} and {right_type}",
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if operator in {"&&", "||"}:
            if left_type.is_bool() and right_type.is_bool():
                node.inferred_type = BOOL_TYPE
                self._try_fold_binary(node, operator)
                return BOOL_TYPE

            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                f"operator '{operator}' requires bool operands",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                expected="bool and bool",
                actual=f"{left_type} and {right_type}",
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        node.inferred_type = ERROR_TYPE
        return ERROR_TYPE

    def visit_AssignmentExprNode(self, node: AssignmentExprNode):
        if isinstance(node.target, IdentifierExprNode):
            target_type = self.visit(node.target)
        elif isinstance(node.target, StructAccessExprNode):
            target_type = self._resolve_assignment_target_struct_access(node.target)
        else:
            target_type = self.visit(node.target)

        value_type = self.visit(node.value)

        if not isinstance(node.target, (IdentifierExprNode, StructAccessExprNode)):
            self.error_reporter.add(
                SemanticErrorKind.INVALID_ASSIGNMENT_TARGET,
                "invalid assignment target",
                node.target.line,
                node.target.column,
                context=self._current_context(),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        target_symbol = getattr(node.target, "symbol", None)
        if target_symbol is not None and not target_symbol.mutable:
            self.error_reporter.add(
                SemanticErrorKind.INVALID_ASSIGNMENT_TARGET,
                "cannot assign to immutable target",
                node.operator.line,
                node.operator.column,
                context=self._current_context(),
                note=f"'{target_symbol.name}' is immutable",
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if target_type is None or value_type is None:
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        op = node.operator.lexeme

        if op == "=":
            if not target_type.is_assignable_from(value_type):
                self.error_reporter.add(
                    SemanticErrorKind.TYPE_MISMATCH,
                    "type mismatch in assignment",
                    node.operator.line,
                    node.operator.column,
                    context=self._current_context(),
                    expected=str(target_type),
                    actual=str(value_type),
                )
                node.inferred_type = ERROR_TYPE
                return ERROR_TYPE
        else:
            if op in {"+=", "-=", "*=", "/="}:
                if not (target_type.is_numeric() and value_type.is_numeric()):
                    self.error_reporter.add(
                        SemanticErrorKind.TYPE_MISMATCH,
                        f"operator '{op}' requires numeric types",
                        node.operator.line,
                        node.operator.column,
                        context=self._current_context(),
                        expected="numeric assignment",
                        actual=f"{target_type} and {value_type}",
                    )
                    node.inferred_type = ERROR_TYPE
                    return ERROR_TYPE

                result_type = FLOAT_TYPE if (target_type == FLOAT_TYPE or value_type == FLOAT_TYPE) else INT_TYPE

                if not target_type.is_assignable_from(result_type):
                    self.error_reporter.add(
                        SemanticErrorKind.TYPE_MISMATCH,
                        f"type mismatch in compound assignment '{op}'",
                        node.operator.line,
                        node.operator.column,
                        context=self._current_context(),
                        expected=str(target_type),
                        actual=str(result_type),
                    )
                    node.inferred_type = ERROR_TYPE
                    return ERROR_TYPE

        if isinstance(node.target, IdentifierExprNode) and node.target.symbol is not None:
            node.target.symbol.initialized = True

        elif isinstance(node.target, StructAccessExprNode):
            if isinstance(node.target.primary, IdentifierExprNode):
                base_symbol = self.symbol_table.lookup(node.target.primary.name.lexeme)
                if base_symbol is not None:
                    base_symbol.initialized = True

        node.inferred_type = target_type
        return target_type

    def visit_CallExprNode(self, node: CallExprNode):
        self.visit(node.callee)

        arg_types = []
        for arg in node.arguments:
            arg_types.append(self.visit(arg))

        if not isinstance(node.callee, IdentifierExprNode):
            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                "call target must be a function name",
                node.callee.line,
                node.callee.column,
                context=self._current_context(),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        callee_symbol = node.callee.symbol
        if callee_symbol is None or callee_symbol.kind != SymbolKind.FUNCTION:
            self.error_reporter.add(
                SemanticErrorKind.TYPE_MISMATCH,
                f"'{node.callee.name.lexeme}' is not a function",
                node.callee.name.line,
                node.callee.name.column,
                context=self._current_context(),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        expected_params = callee_symbol.params

        if len(node.arguments) != len(expected_params):
            self.error_reporter.add(
                SemanticErrorKind.ARGUMENT_COUNT_MISMATCH,
                f"argument count mismatch in call to '{callee_symbol.name}'",
                node.line,
                node.column,
                context=self._current_context(),
                expected=str(len(expected_params)),
                actual=str(len(node.arguments)),
                note=f"function signature: {callee_symbol.type}",
            )
            node.inferred_type = callee_symbol.return_type or ERROR_TYPE
            return node.inferred_type

        for i, (arg_type, param_symbol) in enumerate(zip(arg_types, expected_params), start=1):
            if arg_type is None:
                continue
            if not param_symbol.type.is_assignable_from(arg_type):
                self.error_reporter.add(
                    SemanticErrorKind.ARGUMENT_TYPE_MISMATCH,
                    f"argument {i} type mismatch in call to '{callee_symbol.name}'",
                    node.arguments[i - 1].line,
                    node.arguments[i - 1].column,
                    context=self._current_context(),
                    expected=str(param_symbol.type),
                    actual=str(arg_type),
                )

        node.symbol = callee_symbol
        node.inferred_type = callee_symbol.return_type or ERROR_TYPE
        return node.inferred_type

    def visit_StructAccessExprNode(self, node: StructAccessExprNode):
        primary_type = self.visit(node.primary)

        if primary_type is None or primary_type == ERROR_TYPE:
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if not primary_type.is_struct():
            self.error_reporter.add(
                SemanticErrorKind.INVALID_MEMBER_ACCESS,
                "member access is only valid on struct values",
                node.field.line,
                node.field.column,
                context=self._current_context(),
                expected="struct",
                actual=str(primary_type),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        field_name = node.field.lexeme
        field_type = primary_type.fields.get(field_name)

        if field_type is None:
            self.error_reporter.add(
                SemanticErrorKind.INVALID_MEMBER_ACCESS,
                f"struct '{primary_type.name}' has no field '{field_name}'",
                node.field.line,
                node.field.column,
                context=self._current_context(),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        node.inferred_type = field_type
        return field_type

    def _predeclare_block_variables(self, statements) -> None:
        from src.semantic.type_system import get_type_size, get_type_alignment

        for index, stmt in enumerate(statements):
            if not isinstance(stmt, VarDeclStmtNode):
                continue

            var_name = stmt.name.lexeme

            if self.symbol_table.lookup_local(var_name) is not None:
                continue

            var_type = self.resolve_type_token(stmt.type)

            placeholder = SymbolInfo(
                name=var_name,
                type=var_type,
                kind=SymbolKind.VARIABLE,
                line=stmt.name.line,
                column=stmt.name.column,
                initialized=False,
                size=get_type_size(var_type),
                alignment=get_type_alignment(var_type),
                declaration_order=index,
                is_placeholder=True,
            )

            self.symbol_table.insert(var_name, placeholder)

    def _walk_block_statements(self, statements) -> None:
        previous_index = self.current_statement_index

        for index, stmt in enumerate(statements):
            self.current_statement_index = index
            self.visit(stmt)

        self.current_statement_index = previous_index

    def format_decorated_ast(self) -> str:
        lines = []
        if self.decorated_ast is not None:
            self._collect_decorated_ast(self.decorated_ast, lines)
        return "\n".join(lines) if lines else "No decorated AST data."

    def _collect_decorated_ast(self, node, lines, indent=0):
        if node is None or not isinstance(node, ASTNode):
            return

        prefix = "  " * indent
        parts = [node.__class__.__name__]

        if hasattr(node, "inferred_type") and node.inferred_type is not None:
            parts.append(f"type={node.inferred_type}")

        if hasattr(node, "constant_value") and node.constant_value is not None:
            parts.append(f"const={node.constant_value!r}")

        if hasattr(node, "symbol") and node.symbol is not None:
            parts.append(f"symbol={node.symbol.name}")

        lines.append(f"{prefix}{' | '.join(parts)}")

        for key, value in vars(node).items():
            if key in {"symbol", "inferred_type", "constant_value"}:
                continue

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ASTNode):
                        self._collect_decorated_ast(item, lines, indent + 1)
            elif isinstance(value, ASTNode):
                self._collect_decorated_ast(value, lines, indent + 1)


    def _try_fold_binary(self, node: BinaryExprNode, operator: str):
        left_const = getattr(node.left, "constant_value", None)
        right_const = getattr(node.right, "constant_value", None)

        if left_const is None or right_const is None:
            return

        try:
            if operator == "+":
                node.constant_value = left_const + right_const
            elif operator == "-":
                node.constant_value = left_const - right_const
            elif operator == "*":
                node.constant_value = left_const * right_const
            elif operator == "/":
                node.constant_value = left_const / right_const
            elif operator == "%":
                node.constant_value = left_const % right_const
            elif operator == "==":
                node.constant_value = left_const == right_const
            elif operator == "!=":
                node.constant_value = left_const != right_const
            elif operator == "<":
                node.constant_value = left_const < right_const
            elif operator == "<=":
                node.constant_value = left_const <= right_const
            elif operator == ">":
                node.constant_value = left_const > right_const
            elif operator == ">=":
                node.constant_value = left_const >= right_const
            elif operator == "&&":
                node.constant_value = left_const and right_const
            elif operator == "||":
                node.constant_value = left_const or right_const
        except Exception:
            node.constant_value = None

    def _resolve_assignment_target_struct_access(self, node: StructAccessExprNode):
        if not isinstance(node.primary, IdentifierExprNode):
            primary_type = self.visit(node.primary)
        else:
            name = node.primary.name.lexeme
            symbol = self.symbol_table.lookup(name)

            if symbol is None:
                self.error_reporter.add(
                    SemanticErrorKind.UNDECLARED_IDENTIFIER,
                    f"undeclared identifier '{name}'",
                    node.primary.name.line,
                    node.primary.name.column,
                    context=self._current_context(),
                )
                node.inferred_type = ERROR_TYPE
                return ERROR_TYPE

            node.primary.symbol = symbol
            node.primary.inferred_type = symbol.type
            primary_type = symbol.type

        if primary_type is None or primary_type == ERROR_TYPE:
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        if not primary_type.is_struct():
            self.error_reporter.add(
                SemanticErrorKind.INVALID_MEMBER_ACCESS,
                "member access is only valid on struct values",
                node.field.line,
                node.field.column,
                context=self._current_context(),
                expected="struct",
                actual=str(primary_type),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        field_name = node.field.lexeme
        field_type = primary_type.fields.get(field_name)

        if field_type is None:
            self.error_reporter.add(
                SemanticErrorKind.INVALID_MEMBER_ACCESS,
                f"struct '{primary_type.name}' has no field '{field_name}'",
                node.field.line,
                node.field.column,
                context=self._current_context(),
            )
            node.inferred_type = ERROR_TYPE
            return ERROR_TYPE

        node.inferred_type = field_type
        return field_type

    def format_type_report(self) -> str:
        lines = []
        if self.decorated_ast is not None:
            self._collect_type_report(self.decorated_ast, lines)
        return "\n".join(lines) if lines else "No type inference data."

    def _collect_type_report(self, node, lines):

        if node is None or not isinstance(node, ASTNode):
            return

        if hasattr(node, "inferred_type") and node.inferred_type is not None:
            const_part = ""
            if getattr(node, "constant_value", None) is not None:
                const_part = f", const={node.constant_value!r}"

            lines.append(
                f"Line {getattr(node, 'line', '?')}:{getattr(node, 'column', '?')} "
                f"{node.__class__.__name__} -> {node.inferred_type}{const_part}"
            )

        for key, value in vars(node).items():
            if key in {"symbol", "inferred_type", "constant_value"}:
                continue

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ASTNode):
                        self._collect_type_report(item, lines)
            elif isinstance(value, ASTNode):
                self._collect_type_report(value, lines)

    def format_error_summary(self) -> str:
        category_counts = {}
        for error in self.get_errors():
            key = error.kind.name
            category_counts[key] = category_counts.get(key, 0) + 1

        if category_counts:
            categories = ", ".join(f"{k}={v}" for k, v in sorted(category_counts.items()))
        else:
            categories = "none"

        return f"Semantic summary: errors={len(self.get_errors())}, warnings=0, categories=[{categories}]"

    def _format_type_hierarchy(self) -> str:
        lines = [
            "Builtin types: int, float, bool, void, string",
            "Rules:",
            "  - int -> float implicit widening allowed",
            "  - struct types compare by name",
            "  - function types compare by parameter types and return type",
        ]
        return "\n".join(lines)

    def format_validation_report(self) -> str:
        parts = [
            self.format_error_summary(),
            "",
            "Declared symbols by scope:",
            self.symbol_table.dump(),
            "",
            self.symbol_table.dump_memory_layout(),
            "",
            "Type hierarchy information:",
            self._format_type_hierarchy(),
            "",
            "Type inference results:",
            self.format_type_report(),
        ]
        return "\n".join(parts)


    def resolve_type_token(self, type_token) -> Type:
        if type_token is None:
            return VOID_TYPE

        type_name = type_token.lexeme

        builtin = get_builtin_type(type_name)
        if builtin is not None:
            return builtin

        symbol = self.symbol_table.lookup(type_name)
        if symbol is not None and symbol.kind == SymbolKind.STRUCT:
            return symbol.type

        self.error_reporter.add(
            SemanticErrorKind.UNKNOWN_TYPE,
            f"unknown type '{type_name}'",
            type_token.line,
            type_token.column,
            context=self._current_context(),
        )
        return ERROR_TYPE

    def _infer_literal_type(self, value) -> Type:
        if isinstance(value, bool):
            return BOOL_TYPE
        if isinstance(value, int):
            return INT_TYPE
        if isinstance(value, float):
            return FLOAT_TYPE
        if isinstance(value, str):
            return STRING_TYPE
        return ERROR_TYPE

    def _duplicate_declaration(self, token, name: str) -> None:
        self.error_reporter.add(
            SemanticErrorKind.DUPLICATE_DECLARATION,
            f"duplicate declaration '{name}'",
            token.line,
            token.column,
            context=self._current_context(),
        )

    def _current_context(self) -> str:
        if self.current_function is not None:
            return f"in function '{self.current_function.name}'"
        return "in global scope"