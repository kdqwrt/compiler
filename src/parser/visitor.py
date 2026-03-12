from src.parser.ast import *


class ASTVisitor:
    """Базовый класс Visitor для обхода AST"""

    def visit(self, node):
        if node is None:
            return None
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """Общий метод обхода для узлов без специфического посетителя"""
        for attr_name in dir(node):
            if attr_name.startswith("_"):
                continue
            attr = getattr(node, attr_name)
            if isinstance(attr, ASTNode):
                self.visit(attr)
            elif isinstance(attr, list):
                for item in attr:
                    if isinstance(item, ASTNode):
                        self.visit(item)


class ASTPrettyPrinter(ASTVisitor):
    """Visitor для pretty printing AST"""

    def __init__(self):
        self.indent = 0
        self.lines = []

    def print(self, text=""):
        self.lines.append("  " * self.indent + text)

    def get_result(self):
        return "\n".join(self.lines)

    # ========================
    # top-level
    # ========================

    def visit_ProgramNode(self, node):
        self.print("Program:")
        self.indent += 1
        for decl in node.declarations:
            self.visit(decl)
        self.indent -= 1

    def visit_FunctionDeclNode(self, node):
        ret = node.return_type.lexeme if node.return_type else "void"
        self.print(f"FunctionDecl: {node.name.lexeme} -> {ret}")
        self.indent += 1

        self.print("Parameters:")
        self.indent += 1
        if node.parameters:
            for p in node.parameters:
                self.visit(p)
        else:
            self.print("[]")
        self.indent -= 1

        self.print("Body:")
        self.indent += 1
        self.visit(node.body)
        self.indent -= 1

        self.indent -= 1

    def visit_StructDeclNode(self, node):
        self.print(f"StructDecl: {node.name.lexeme}")
        self.indent += 1
        self.print("Fields:")
        self.indent += 1
        if node.fields:
            for field in node.fields:
                self.visit(field)
        else:
            self.print("[]")
        self.indent -= 2

    def visit_ParamNode(self, node):
        self.print(f"{node.type.lexeme} {node.name.lexeme}")

    # ========================
    # statements
    # ========================

    def visit_BlockStmtNode(self, node):
        self.print("Block:")
        self.indent += 1
        for stmt in node.statements:
            self.visit(stmt)
        self.indent -= 1

    def visit_VarDeclStmtNode(self, node):
        init = f" = {self._expr_to_str(node.initializer)}" if node.initializer is not None else ""
        self.print(f"VarDecl: {node.type.lexeme} {node.name.lexeme}{init}")

    def visit_ReturnStmtNode(self, node):
        if node.value is not None:
            self.print(f"Return: {self._expr_to_str(node.value)}")
        else:
            self.print("Return")

    def visit_ExprStmtNode(self, node):
        self.print(f"ExprStmt: {self._expr_to_str(node.expression)}")

    def visit_EmptyStmtNode(self, node):
        self.print("EmptyStmt: ;")

    def visit_IfStmtNode(self, node):
        self.print("IfStmt")
        self.indent += 1

        self.print("Condition:")
        self.indent += 1
        self.print(self._expr_to_str(node.condition))
        self.indent -= 1

        self.print("Then:")
        self.indent += 1
        self.visit(node.then_branch)
        self.indent -= 1

        if node.else_branch is not None:
            self.print("Else:")
            self.indent += 1
            self.visit(node.else_branch)
            self.indent -= 1

        self.indent -= 1

    def visit_WhileStmtNode(self, node):
        self.print("WhileStmt")
        self.indent += 1

        self.print("Condition:")
        self.indent += 1
        self.print(self._expr_to_str(node.condition))
        self.indent -= 1

        self.print("Body:")
        self.indent += 1
        self.visit(node.body)
        self.indent -= 1

        self.indent -= 1

    def visit_ForStmtNode(self, node):
        self.print("ForStmt")
        self.indent += 1

        self.print("Init:")
        self.indent += 1
        if node.init is not None:
            self.visit(node.init)
        else:
            self.print("None")
        self.indent -= 1

        self.print("Condition:")
        self.indent += 1
        if node.condition is not None:
            self.print(self._expr_to_str(node.condition))
        else:
            self.print("None")
        self.indent -= 1

        self.print("Update:")
        self.indent += 1
        if node.update is not None:
            self.print(self._expr_to_str(node.update))
        else:
            self.print("None")
        self.indent -= 1

        self.print("Body:")
        self.indent += 1
        self.visit(node.body)
        self.indent -= 1

        self.indent -= 1

    # ========================
    # expressions
    # ========================

    def _expr_to_str(self, expr):
        if expr is None:
            return "None"

        if isinstance(expr, LiteralExprNode):
            if expr.value is None:
                return "null"
            if isinstance(expr.value, str):
                return f'"{expr.value}"'
            if isinstance(expr.value, bool):
                return "true" if expr.value else "false"
            return str(expr.value)

        elif isinstance(expr, IdentifierExprNode):
            return expr.name.lexeme if hasattr(expr.name, "lexeme") else str(expr.name)

        elif isinstance(expr, BinaryExprNode):
            return f"({self._expr_to_str(expr.left)} {expr.operator.lexeme} {self._expr_to_str(expr.right)})"

        elif isinstance(expr, UnaryExprNode):
            if hasattr(expr, "is_postfix") and expr.is_postfix:
                return f"({self._expr_to_str(expr.operand)}{expr.operator.lexeme})"
            return f"({expr.operator.lexeme}{self._expr_to_str(expr.operand)})"

        elif isinstance(expr, AssignmentExprNode):
            return f"({self._expr_to_str(expr.target)} {expr.operator.lexeme} {self._expr_to_str(expr.value)})"

        elif isinstance(expr, CallExprNode):
            args = ", ".join(self._expr_to_str(a) for a in expr.arguments)
            return f"{self._expr_to_str(expr.callee)}({args})"

        elif isinstance(expr, StructAccessExprNode):
            return f"{self._expr_to_str(expr.primary)}.{expr.field.lexeme}"

        return str(expr)


class ASTSemanticAnalyzer(ASTVisitor):
    """Visitor для семантического анализа"""

    def __init__(self):
        self.errors = []
        self.current_function = None
        self.variables = []

    def visit_LiteralExprNode(self, node):
        if isinstance(node.value, int):
            INT_MIN = -(2 ** 31)
            INT_MAX = 2 ** 31 - 1
            if node.value < INT_MIN or node.value > INT_MAX:
                self.errors.append(
                    f"[Строка {node.line}, Колонка {node.column}] "
                    f"Целое число вне диапазона 32-бит: {node.value}"
                )

    def get_errors(self):
        return self.errors