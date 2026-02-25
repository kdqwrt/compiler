from .tokens import TokenType, Token


class Scanner:
    KEYWORDS = {
        'if': TokenType.KW_IF,
        'else': TokenType.KW_ELSE,
        'while': TokenType.KW_WHILE,
        'for': TokenType.KW_FOR,
        'int': TokenType.KW_INT,
        'float': TokenType.KW_FLOAT,
        'bool': TokenType.KW_BOOL,
        'return': TokenType.KW_RETURN,
        'void': TokenType.KW_VOID,
        'struct': TokenType.KW_STRUCT,
        'fn': TokenType.KW_FN,
    }

    def __init__(self, source):
        self.source = source
        self.tokens = []

        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.token_start_line = 1
        self.token_start_column = 1

        self.errors = []

        self._all_tokens = None
        self._token_position = 0

    def scan_tokens(self):
        block_stack = []
        while not self.is_at_end():
            self.start = self.current
            self.token_start_line = self.line
            self.token_start_column = self.column
            c = self.peek()
            match c:
                case '{':
                    block_stack.append('{')
                case '}':
                    if block_stack:
                        block_stack.pop()
                    else:
                        self.error(f"Закрывающая скобка '}}' без открывающей")
            self.scan_token()

        if block_stack:
            self.error("Незакрытый блок")
        self.token_start_line = self.line
        self.token_start_column = self.column
        self.add_token(TokenType.EOF, "")
        return self.tokens

    def next_token(self):
        if self._all_tokens is None:
            self._all_tokens = self.scan_tokens()
            self._token_position = 0

        if self._token_position >= len(self._all_tokens):
            return self._all_tokens[-1]

        token = self._all_tokens[self._token_position]
        self._token_position += 1
        return token

    def peek_token(self):
        if self._all_tokens is None:
            self._all_tokens = self.scan_tokens()
            self._token_position = 0

        if self._token_position >= len(self._all_tokens):
            return self._all_tokens[-1]

        return self._all_tokens[self._token_position]

    def is_at_end(self):
        return self.current >= len(self.source)

    def get_line(self):
        return self.line

    def get_column(self):
        return self.column

    def scan_token(self):
        c = self.advance()

        match c:
            case '\r' if self.peek() == '\n':
                self.advance()
                self.line += 1
                self.column = 1

            case '(':
                self.add_token(TokenType.LPAREN)
            case ')':
                self.add_token(TokenType.RPAREN)
            case '{':
                self.add_token(TokenType.LBRACE)
            case '}':
                self.add_token(TokenType.RBRACE)
            case '[':
                self.add_token(TokenType.LBRACKET)
            case ']':
                self.add_token(TokenType.RBRACKET)
            case ',':
                self.add_token(TokenType.COMMA)
            case ';':
                self.add_token(TokenType.SEMICOLON)
            case ':':
                self.add_token(TokenType.COLON)

            case '+':
                self.add_token(TokenType.PLUS_ASSIGN if self.match('=') else TokenType.PLUS)

            case '-':
                if self.match('='):
                    self.add_token(TokenType.MINUS_ASSIGN)
                elif self.peek().isdigit():
                    self.number()
                else:
                    self.add_token(TokenType.MINUS)

            case '*':
                self.add_token(TokenType.STAR_ASSIGN if self.match('=') else TokenType.STAR)

            case '/':
                if self.match('/'):
                    while not self.is_at_end() and self.peek() not in '\r\n':
                        self.advance()
                elif self.match('*'):
                    self.block_comment()
                elif self.match('='):
                    self.add_token(TokenType.SLASH_ASSIGN)
                else:
                    self.add_token(TokenType.SLASH)

            case '%':
                self.add_token(TokenType.PERCENT)

            case '!':
                self.add_token(TokenType.NEQ if self.match('=') else TokenType.NOT)

            case '=':
                self.add_token(TokenType.EQ if self.match('=') else TokenType.ASSIGN)

            case '<':
                self.add_token(TokenType.LEQ if self.match('=') else TokenType.LT)

            case '>':
                self.add_token(TokenType.GEQ if self.match('=') else TokenType.GT)

            case '&':
                if self.match('&'):
                    self.add_token(TokenType.AND)
                else:
                    self.error(f"Ожидался '&', получено '{self.peek()}'")

            case '|':
                if self.match('|'):
                    self.add_token(TokenType.OR)
                else:
                    self.error(f"Ожидался '|', получено '{self.peek()}'")

            case '"':
                self.string()

            case _ if c.isdigit():
                self.number()

            case _ if c.isalpha() or c == '_':
                self.identifier()

            case c if c in ' \t\r':
                pass

            case '\n':
                self.line += 1
                self.column = 1

            case _:
                self.error(f"Неизвестный символ: '{c}' (ASCII: {ord(c)})")

    def block_comment(self):
        while not self.is_at_end():
            match (self.peek(), self.peek_next()):
                case ('*', '/'):
                    self.advance()
                    self.advance()
                    return
                case ('\n', _):
                    self.line += 1
                    self.column = 1
                    self.advance()
                case ('\r', '\n'):
                    self.advance()
                    self.advance()
                    self.line += 1
                    self.column = 1
                case _:
                    self.advance()

        self.error("Незакрытый многострочный комментарий")
        self.start = self.current
        self.token_start_line = self.line
        self.token_start_column = self.column

    def string(self):
        value = []
        start_line = self.token_start_line
        start_column = self.token_start_column

        while not self.is_at_end():
            c = self.peek()
            match c:
                case '"':
                    self.advance()
                    lexeme = self.source[self.start:self.current]
                    self.add_token(TokenType.STRING_LITERAL, ''.join(value), lexeme_override=lexeme)
                    return

                case '\\':
                    self.advance()
                    if self.is_at_end():
                        self.error(f"Незакрытая строка, начатая в {start_line}:{start_column}")
                        self.error("Неизвестная escape-последовательность: \\")
                        content = ''.join(value)
                        self.add_token(TokenType.STRING_LITERAL, content, lexeme_override=content)
                        return

                    n = self.advance()
                    match n:
                        case 'n':
                            value.append('\n')
                        case 't':
                            value.append('\t')
                        case 'r':
                            value.append('\r')
                        case '"':
                            value.append('"')
                        case '\\':
                            value.append('\\')
                        case '0':
                            value.append('\0')
                        case 'b':
                            value.append('\b')
                        case 'f':
                            value.append('\f')
                        case _:
                            self.error(f"Неизвестная escape-последовательность: \\{n}")
                            value.append(n)

                case c if c in '\r\n':
                    self.error(f"Незакрытая строка, начатая в {start_line}:{start_column}")
                    content = ''.join(value)
                    self.add_token(TokenType.STRING_LITERAL, content, lexeme_override=content)
                    return

                case _:
                    value.append(c)
                    self.advance()

        self.error(f"Незакрытая строка, начатая в {start_line}:{start_column}")
        content = ''.join(value)
        self.add_token(TokenType.STRING_LITERAL, content, lexeme_override=content)

    def number(self):
        start_pos = self.start
        while self.peek().isdigit():
            self.advance()

        match (self.peek(), self.peek_next().isdigit()):
            case ('.', True):
                self.advance()
                while self.peek().isdigit():
                    self.advance()
                num_str = self.source[start_pos:self.current]
                try:
                    value = float(num_str)
                    if abs(value) > 1e308:
                        self.error(f"Число с плавающей точкой вне допустимого диапазона: {num_str}")
                    self.add_token(TokenType.FLOAT_LITERAL, value)
                except ValueError:
                    self.error(f"Некорректное число с плавающей точкой: {num_str}")
                    self.add_token(TokenType.FLOAT_LITERAL, 0.0)

            case _:
                num_str = self.source[start_pos:self.current]
                try:
                    value = int(num_str)
                    INT_MIN = -2**31
                    INT_MAX = 2**31 - 1
                    if value < INT_MIN or value > INT_MAX:
                        self.error(f"Целое число вне диапазона 32-бит: {value} (допустимо {INT_MIN}..{INT_MAX})")
                    self.add_token(TokenType.INT_LITERAL, value)
                except ValueError:
                    self.error(f"Некорректное целое число: {num_str}")
                    self.add_token(TokenType.INT_LITERAL, 0)

    def identifier(self):
        while self.peek().isalnum() or self.peek() == '_':
            self.advance()

        lexeme = self.source[self.start:self.current]

        if len(lexeme) > 255:
            self.error(f"Идентификатор слишком длинный: {lexeme[:20]}... (макс. 255 символов)")

        if lexeme[0].isdigit():
            self.error(f"Идентификатор не может начинаться с цифры: '{lexeme}'")

        match lexeme:
            case 'true':
                self.add_token(TokenType.BOOL_LITERAL, True)
            case 'false':
                self.add_token(TokenType.BOOL_LITERAL, False)
            case _:
                token_type = self.KEYWORDS.get(lexeme, TokenType.IDENTIFIER)
                self.add_token(token_type)

    def add_token(self, token_type, literal_value=None, lexeme_override=None):
        lexeme = lexeme_override if lexeme_override is not None else self.source[self.start:self.current]
        token = Token(
            token_type,
            lexeme,
            self.token_start_line,
            self.token_start_column,
            literal_value
        )
        self.tokens.append(token)

    def advance(self):
        c = self.source[self.current]
        self.current += 1
        self.column += 1
        return c

    def match(self, expected):
        if self.is_at_end():
            return False
        if self.source[self.current] != expected:
            return False
        self.current += 1
        self.column += 1
        return True

    def peek(self):
        if self.is_at_end():
            return '\0'
        return self.source[self.current]

    def peek_next(self):
        if self.current + 1 >= len(self.source):
            return '\0'
        return self.source[self.current + 1]

    def error(self, message):
        self.errors.append(f"[Строка {self.line}, Колонка {self.column}] {message}")

    def get_errors(self):
        return self.errors