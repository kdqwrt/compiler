from src.lexer.tokens import TokenType, Token
from src.parser.ast import *


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.current = 0
        self.errors = []



    def peek(self):
        return self.tokens[self.current]

    def previous(self):
        return self.tokens[self.current - 1]

    def isAtEnd(self):
        return self.peek().type == TokenType.EOF

    def advance(self):
        if not self.isAtEnd():
            self.current += 1
        return self.previous()

    def check(self, type_):
        if self.isAtEnd():
            return False
        return self.peek().type == type_

    def checkNext(self, type_):
        if self.current + 1 >= len(self.tokens):
            return False
        return self.tokens[self.current + 1].type == type_

    def match(self, *types):
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def consume(self, type_, message):
        if self.check(type_):
            return self.advance()
        self.error(self.peek(), message)
        return None

    def error(self, token, message):
        error_msg = f"[line {token.line}, column {token.column}] Error: {message}"
        self.errors.append(error_msg)

    def get_errors(self):
        return self.errors

    def synchronize(self):
        if not self.isAtEnd():
            self.advance()

        while not self.isAtEnd():
            if self.previous().type == TokenType.SEMICOLON:
                return

            if self.peek().type in [
                TokenType.KW_FN,
                TokenType.KW_STRUCT,
                TokenType.KW_IF,
                TokenType.KW_WHILE,
                TokenType.KW_FOR,
                TokenType.KW_RETURN,
                TokenType.LBRACE,
                TokenType.RBRACE,
            ]:
                return

            self.advance()



    def parse(self):
        try:
            return self.parseProgram()
        except Exception as e:
            self.error(self.peek(), str(e))
            return ProgramNode([], 1, 1)

    def parseProgram(self):
        declarations = []

        while not self.isAtEnd():
            try:
                decl = self.parseDeclaration()
                if decl is not None:
                    declarations.append(decl)
                else:
                    self.error(self.peek(), "Expected top-level declaration")
                    self.synchronize()
            except Exception as e:
                self.error(self.peek(), str(e))
                self.synchronize()

        first = self.tokens[0] if self.tokens else None
        line = first.line if first else 1
        column = first.column if first else 1

        return ProgramNode(declarations, line, column)

    def parseDeclaration(self):
        if self.match(TokenType.KW_FN):
            return self.parseFunctionDecl()

        if self.match(TokenType.KW_STRUCT):
            return self.parseStructDecl()

        if self.isVarDeclStart():
            return self.parseVarDecl()

        return None





    def parseFunctionDecl(self):
        name = self.consume(TokenType.IDENTIFIER, "Expected function name")
        if name is None:
            return None

        self.consume(TokenType.LPAREN, "Expected '(' after function name")

        parameters = []
        if not self.check(TokenType.RPAREN):
            param = self.parseParameter()
            if param is not None:
                parameters.append(param)

            while self.match(TokenType.COMMA):
                param = self.parseParameter()
                if param is not None:
                    parameters.append(param)

        self.consume(TokenType.RPAREN, "Expected ')' after parameters")

        return_type = None
        if self.match(TokenType.ARROW):
            return_type = self.consumeType()

        body = self.parseBlock()
        if body is None:
            self.error(self.peek(), "Expected function body")
            return None

        return FunctionDeclNode(
            return_type,
            name,
            parameters,
            body,
            name.line,
            name.column
        )

    def parseStructDecl(self):
        name = self.consume(TokenType.IDENTIFIER, "Expected struct name")
        if name is None:
            return None

        self.consume(TokenType.LBRACE, "Expected '{' after struct name")

        fields = []
        while not self.check(TokenType.RBRACE) and not self.isAtEnd():
            field = self.parseFieldDecl()
            if field is not None:
                fields.append(field)
            else:
                self.synchronize()

        self.consume(TokenType.RBRACE, "Expected '}' after struct body")

        return StructDeclNode(name, fields, name.line, name.column)

    def parseFieldDecl(self):
        type_token = self.consumeType()
        if type_token is None:
            return None

        name = self.consume(TokenType.IDENTIFIER, "Expected field name")
        if name is None:
            return None

        self.consume(TokenType.SEMICOLON, "Expected ';' after field declaration")

        return VarDeclStmtNode(
            type_token,
            name,
            None,
            type_token.line,
            type_token.column
        )

    def parsePointerStars(self):
        pointer_depth = 0

        while self.match(TokenType.STAR):
            pointer_depth += 1

        return pointer_depth

    def parseParameter(self):
        type_token = self.consumeType()
        if type_token is None:
            return None

        pointer_depth = self.parsePointerStars()

        name = self.consume(TokenType.IDENTIFIER, "Expected parameter name")
        if name is None:
            return None

        array_sizes = []

        while self.match(TokenType.LBRACKET):
            size_expr = self.parseExpression()
            self.consume(TokenType.RBRACKET, "Expected ']' after array size")
            array_sizes.append(size_expr)

        node = ParamNode(type_token, name, type_token.line, type_token.column)
        node.array_sizes = array_sizes

        node.pointer_depth = pointer_depth

        return node


    def parseStatement(self):
        if self.match(TokenType.KW_IF):
            return self.parseIfStmt()

        if self.match(TokenType.KW_WHILE):
            return self.parseWhileStmt()

        if self.match(TokenType.KW_FOR):
            return self.parseForStmt()

        if self.match(TokenType.KW_RETURN):
            return self.parseReturnStmt()

        if self.match(TokenType.LBRACE):
            return self.parseBlockBody()

        if self.isVarDeclStart():
            return self.parseVarDecl()

        if self.match(TokenType.SEMICOLON):
            token = self.previous()
            return EmptyStmtNode(token.line, token.column)

        return self.parseExprStmt()

    def parseBlock(self):
        if not self.match(TokenType.LBRACE):
            self.error(self.peek(), "Expected '{'")
            return None
        return self.parseBlockBody()

    def parseBlockBody(self):
        statements = []

        while not self.check(TokenType.RBRACE) and not self.isAtEnd():
            stmt = self.parseStatement()
            if stmt is not None:
                statements.append(stmt)
            else:
                self.synchronize()

        end = self.consume(TokenType.RBRACE, "Expected '}' after block")
        if end is None:
            token = self.peek()
            return BlockStmtNode(statements, token.line, token.column)

        return BlockStmtNode(statements, end.line, end.column)


    def parseArrayInitializer(self):
        brace = self.consume(TokenType.LBRACE, "Expected '{' for array initializer")
        if brace is None:
            brace = self.peek()

        elements = []

        if not self.check(TokenType.RBRACE):
            element = self.parseExpression()
            if element is not None:
                elements.append(element)

            while self.match(TokenType.COMMA):
                if self.check(TokenType.RBRACE):
                    break

                element = self.parseExpression()
                if element is not None:
                    elements.append(element)

        self.consume(TokenType.RBRACE, "Expected '}' after array initializer")

        return ArrayInitializerExprNode(elements, brace.line, brace.column)


    def parseVarDecl(self):
        type_token = self.consumeType()
        if type_token is None:
            return None

        pointer_depth = self.parsePointerStars()

        name = self.consume(TokenType.IDENTIFIER, "Expected variable name")
        array_sizes = []

        while self.match(TokenType.LBRACKET):
            size_expr = self.parseExpression()
            self.consume(TokenType.RBRACKET, "Expected ']' after array size")
            array_sizes.append(size_expr)
        if name is None:
            return None

        initializer = None
        if self.match(TokenType.ASSIGN):
            if self.check(TokenType.LBRACE):
                initializer = self.parseArrayInitializer()
            else:
                initializer = self.parseExpression()

        semi = self.consume(TokenType.SEMICOLON, "Expected ';' after variable declaration")
        if semi is None:
            semi = name

        node = VarDeclStmtNode(
            type_token,
            name,
            initializer,
            type_token.line,
            type_token.column
        )
        node.array_sizes = array_sizes
        node.pointer_depth = pointer_depth
        return node

        # return VarDeclStmtNode(
        #     type_token,
        #     name,
        #     initializer,
        #     type_token.line,
        #     type_token.column
        # )

    def parseVarDeclNoSemicolon(self):
        type_token = self.consumeType()
        if type_token is None:
            return None

        pointer_depth = self.parsePointerStars()

        name = self.consume(TokenType.IDENTIFIER, "Expected variable name")
        if name is None:
            return None

        array_sizes = []

        while self.match(TokenType.LBRACKET):
            size_expr = self.parseExpression()
            self.consume(TokenType.RBRACKET, "Expected ']' after array size")
            array_sizes.append(size_expr)

        initializer = None
        if self.match(TokenType.ASSIGN):
            if self.check(TokenType.LBRACE):
                initializer = self.parseArrayInitializer()
            else:
                initializer = self.parseExpression()

        node = VarDeclStmtNode(
            type_token,
            name,
            initializer,
            type_token.line,
            type_token.column
        )

        node.array_sizes = array_sizes
        pointer_depth = self.parsePointerStars()
        return node

    def parseExprStmt(self):
        expr = self.parseExpression()
        if expr is None:
            self.error(self.peek(), "Expected expression statement")
            return None

        semi = self.consume(TokenType.SEMICOLON, "Expected ';' after expression")
        if semi is None:
            semi = expr

        return ExprStmtNode(expr, semi.line, semi.column)

    def parseIfStmt(self):
        self.consume(TokenType.LPAREN, "Expected '(' after 'if'")
        condition = self.parseExpression()
        self.consume(TokenType.RPAREN, "Expected ')' after if condition")

        then_branch = self.parseStatement()

        else_branch = None
        if self.match(TokenType.KW_ELSE):
            else_branch = self.parseStatement()

        token = self.previous()
        return IfStmtNode(condition, then_branch, else_branch, token.line, token.column)

    def parseWhileStmt(self):
        self.consume(TokenType.LPAREN, "Expected '(' after 'while'")
        condition = self.parseExpression()
        self.consume(TokenType.RPAREN, "Expected ')' after while condition")

        body = self.parseStatement()

        token = self.previous()
        return WhileStmtNode(condition, body, token.line, token.column)

    def parseForStmt(self):
        self.consume(TokenType.LPAREN, "Expected '(' after 'for'")

        init = None
        if self.check(TokenType.SEMICOLON):
            self.advance()
        elif self.isVarDeclStart():
            init = self.parseVarDeclNoSemicolon()
            self.consume(TokenType.SEMICOLON, "Expected ';' after for initializer")
        else:
            expr = self.parseExpression()
            semi = self.consume(TokenType.SEMICOLON, "Expected ';' after for initializer")
            if expr is not None:
                if semi is None:
                    semi = self.peek()
                init = ExprStmtNode(expr, semi.line, semi.column)

        condition = None
        if not self.check(TokenType.SEMICOLON):
            condition = self.parseExpression()
        self.consume(TokenType.SEMICOLON, "Expected ';' after for condition")

        update = None
        if not self.check(TokenType.RPAREN):
            update = self.parseExpression()
        self.consume(TokenType.RPAREN, "Expected ')' after for clauses")

        body = self.parseStatement()

        token = self.previous()
        return ForStmtNode(init, condition, update, body, token.line, token.column)

    def parseReturnStmt(self):
        value = None
        if not self.check(TokenType.SEMICOLON):
            value = self.parseExpression()

        semi = self.consume(TokenType.SEMICOLON, "Expected ';' after return statement")
        if semi is None:
            semi = self.peek()

        return ReturnStmtNode(value, semi.line, semi.column)



    def parseExpression(self):
        return self.parseAssignment()

    def parseAssignment(self):
        expr = self.parseOr()

        if self.match(
            TokenType.ASSIGN,
            TokenType.PLUS_ASSIGN,
            TokenType.MINUS_ASSIGN,
            TokenType.STAR_ASSIGN,
            TokenType.SLASH_ASSIGN
        ):
            operator = self.previous()
            value = self.parseAssignment()
            return AssignmentExprNode(
                expr,
                operator,
                value,
                operator.line,
                operator.column
            )

        return expr

    def parseOr(self):
        expr = self.parseAnd()

        while self.match(TokenType.OR):
            operator = self.previous()
            right = self.parseAnd()
            expr = BinaryExprNode(expr, operator, right, operator.line, operator.column)

        return expr

    def parseAnd(self):
        expr = self.parseEquality()

        while self.match(TokenType.AND):
            operator = self.previous()
            right = self.parseEquality()
            expr = BinaryExprNode(expr, operator, right, operator.line, operator.column)

        return expr

    def parseEquality(self):
        expr = self.parseComparison()

        if self.match(TokenType.EQ, TokenType.NEQ):
            operator = self.previous()
            right = self.parseComparison()
            expr = BinaryExprNode(expr, operator, right, operator.line, operator.column)

            if self.match(TokenType.EQ, TokenType.NEQ):
                bad = self.previous()
                self.error(
                    bad,
                    "Equality operators are non-associative; use parentheses"
                )
                extra_right = self.parseComparison()
                expr = BinaryExprNode(expr, bad, extra_right, bad.line, bad.column)

        return expr

    def parseComparison(self):
        expr = self.parseTerm()

        if self.match(TokenType.LT, TokenType.LEQ, TokenType.GT, TokenType.GEQ):
            operator = self.previous()
            right = self.parseTerm()
            expr = BinaryExprNode(expr, operator, right, operator.line, operator.column)

            if self.match(TokenType.LT, TokenType.LEQ, TokenType.GT, TokenType.GEQ):
                bad = self.previous()
                self.error(
                    bad,
                    "Comparison operators are non-associative; use parentheses"
                )
                extra_right = self.parseTerm()
                expr = BinaryExprNode(expr, bad, extra_right, bad.line, bad.column)

        return expr

    def parseTerm(self):
        expr = self.parseFactor()

        while self.match(TokenType.PLUS, TokenType.MINUS):
            operator = self.previous()
            right = self.parseFactor()
            expr = BinaryExprNode(expr, operator, right, operator.line, operator.column)

        return expr

    def parseFactor(self):
        expr = self.parseUnary()

        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            operator = self.previous()
            right = self.parseUnary()
            expr = BinaryExprNode(expr, operator, right, operator.line, operator.column)

        return expr

    def parseUnary(self):
        if self.match(
                TokenType.NOT,
                TokenType.MINUS,
                TokenType.STAR,
                TokenType.BIT_AND,
                TokenType.INCREMENT,
                TokenType.DECREMENT
        ):
            operator = self.previous()
            operand = self.parseUnary()
            return UnaryExprNode(operator, operand, operator.line, operator.column)

        return self.parsePostfix()

    def parsePostfix(self):
        expr = self.parsePrimary()
        if expr is None:
            return None

        while True:
            if self.match(TokenType.LPAREN):
                arguments = []

                if not self.check(TokenType.RPAREN):
                    arg = self.parseExpression()
                    if arg is not None:
                        arguments.append(arg)

                    while self.match(TokenType.COMMA):
                        arg = self.parseExpression()
                        if arg is not None:
                            arguments.append(arg)

                paren = self.consume(TokenType.RPAREN, "Expected ')' after arguments")
                if paren is None:
                    paren = self.peek()

                expr = CallExprNode(expr, arguments, paren.line, paren.column)

            elif self.match(TokenType.LBRACKET):
                index = self.parseExpression()
                bracket = self.consume(TokenType.RBRACKET, "Expected ']' after array index")

                if bracket is None:
                    bracket = self.peek()

                expr = ArrayAccessExprNode(
                    expr,
                    index,
                    bracket.line,
                    bracket.column,
                )

            elif self.match(TokenType.DOT):
                name = self.consume(TokenType.IDENTIFIER, "Expected field name after '.'")
                if name is None:
                    return expr
                expr = StructAccessExprNode(expr, name, name.line, name.column)

            else:
                break

        if self.match(TokenType.INCREMENT, TokenType.DECREMENT):
            operator = self.previous()
            unary_node = UnaryExprNode(operator, expr, operator.line, operator.column)
            unary_node.is_postfix = True
            expr = unary_node

            if self.match(TokenType.INCREMENT, TokenType.DECREMENT):
                bad = self.previous()
                self.error(
                    bad,
                    "Only one postfix increment/decrement operator is allowed"
                )

        return expr

    def parsePrimary(self):
        if self.match(TokenType.INT_LITERAL):
            token = self.previous()
            return LiteralExprNode(token.literal_value, token.line, token.column)

        if self.match(TokenType.FLOAT_LITERAL):
            token = self.previous()
            return LiteralExprNode(token.literal_value, token.line, token.column)

        if self.match(TokenType.STRING_LITERAL):
            token = self.previous()
            return LiteralExprNode(token.literal_value, token.line, token.column)

        if self.match(TokenType.BOOL_LITERAL):
            token = self.previous()
            return LiteralExprNode(token.literal_value, token.line, token.column)

        if self.match(TokenType.NULL_LITERAL):
            token = self.previous()
            return LiteralExprNode(None, token.line, token.column)

        if self.match(TokenType.IDENTIFIER):
            token = self.previous()
            return IdentifierExprNode(token, token.line, token.column)

        if self.match(TokenType.LPAREN):
            expr = self.parseExpression()
            self.consume(TokenType.RPAREN, "Expected ')' after expression")
            return expr

        self.error(self.peek(), "Expected expression")
        return None



    def consumeType(self):
        if self.match(
            TokenType.KW_INT,
            TokenType.KW_FLOAT,
            TokenType.KW_BOOL,
            TokenType.KW_STRING,
            TokenType.KW_VOID
        ):
            return self.previous()


        if self.match(TokenType.IDENTIFIER):
            return self.previous()

        self.error(self.peek(), "Expected type")
        return None

    def isVarDeclStart(self):
        if self.isAtEnd():
            return False

        if self.check(
            TokenType.KW_INT
        ) or self.check(
            TokenType.KW_FLOAT
        ) or self.check(
            TokenType.KW_BOOL
        ) or self.check(
            TokenType.KW_STRING
        ) or self.check(
            TokenType.KW_VOID
        ):
            return True


        if self.check(TokenType.IDENTIFIER) and self.checkNext(TokenType.IDENTIFIER):
            return True

        return False

    def consume(self, type_, message):
        if self.check(type_):
            return self.advance()

        token = self.peek()
        self.error(token, message)

        # Вставляем недостающий токен
        if type_ == TokenType.SEMICOLON:
            print(f"[Восстановление ошибок] вставка пропущенного токена ';' на линии {token.line}, позиции {token.column}")
            return self.make_synthetic_token(TokenType.SEMICOLON, ";")

        if type_ == TokenType.RBRACE:
            print(f"[Восстановление ошибок] вставка пропущенного токена '}}' на линии {token.line}, позиции {token.column}")
            return self.make_synthetic_token(TokenType.RBRACE, "}")

        if type_ == TokenType.RPAREN:
            print(f"[Восстановление ошибок] вставка пропущенного токена ')' на линии {token.line}, позиции {token.column}")
            return self.make_synthetic_token(TokenType.RPAREN, ")")

        return None

    def make_synthetic_token(self, token_type, lexeme=""):
        current = self.peek()
        return Token(token_type, lexeme, current.line, current.column)
