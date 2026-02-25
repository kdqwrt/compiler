from enum import Enum, auto


class TokenType(Enum):

    KW_IF = auto()
    KW_ELSE = auto()
    KW_WHILE = auto()
    KW_FOR = auto()
    KW_INT = auto()
    KW_FLOAT = auto()
    KW_BOOL = auto()
    KW_RETURN = auto()
    KW_VOID = auto()
    KW_STRUCT = auto()
    KW_FN = auto()



    IDENTIFIER = auto()
    BOOL_LITERAL = auto()
    INT_LITERAL = auto()
    FLOAT_LITERAL = auto()
    STRING_LITERAL = auto()


    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()

    EQ = auto()
    NEQ = auto()
    LT = auto()
    LEQ = auto()
    GT = auto()
    GEQ = auto()

    AND = auto()
    OR = auto()
    NOT = auto()

    ASSIGN = auto()
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto()


    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    SEMICOLON = auto()
    COLON = auto()


    EOF = auto()


class Token:
    def __init__(self, token_type, lexeme, line, column, literal_value=None):
        self.type = token_type
        self.lexeme = lexeme
        self.line = line
        self.column = column
        self.literal_value = literal_value

    def __str__(self):

        if self.type == TokenType.EOF:
            return f"{self.line}:{self.column} EOF \"\""


        result = f"{self.line}:{self.column} {self.type.name} \"{self.lexeme}\""


        if self.literal_value is not None:
            if self.type == TokenType.INT_LITERAL:
                result += f" {self.literal_value}"
            elif self.type == TokenType.FLOAT_LITERAL:
                result += f" {self.literal_value}"
            elif self.type == TokenType.BOOL_LITERAL:

                result += f" {'true' if self.literal_value else 'false'}"

        return result