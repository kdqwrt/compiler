class Preprocessor:
    def __init__(self, source: str):
        self.source = source
        self.result_lines = []
        self.errors = []
        self.line_map = []
        self.current_line = 1

    def process(self) -> str:
        lines = self.source.splitlines(keepends=True)
        in_block_comment = False
        block_comment_start = None

        for line_num, line in enumerate(lines, 1):
            processed_line, in_block_comment, block_comment_start = self._process_line(
                line, line_num, in_block_comment, block_comment_start
            )

            if processed_line is not None:
                self.result_lines.append(processed_line)
                self.line_map.append((line_num, self.current_line))
                self.current_line += 1


        if in_block_comment and block_comment_start:
            self.errors.append(
                f"[Строка {block_comment_start}] Незавершенный блочный комментарий"
            )

        return ''.join(self.result_lines)

    def _process_line(self, line: str, line_num: int,
                      in_block_comment: bool, block_comment_start: int):

        result = []
        i = 0
        in_string = False
        string_char = None

        while i < len(line):
            char = line[i]


            if not in_block_comment and char in ('"', "'"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif string_char == char:

                    if i > 0 and line[i - 1] == '\\':
                        pass
                    else:
                        in_string = False
                        string_char = None
                result.append(char)
                i += 1
                continue

            if in_string:
                result.append(char)
                i += 1
                continue


            if not in_block_comment and i + 1 < len(line) and line[i:i + 2] == '//':
                result.append(' ')
                i = len(line)
                break


            if not in_block_comment and i + 1 < len(line) and line[i:i + 2] == '/*':
                in_block_comment = True
                block_comment_start = line_num
                result.append(' ')
                i += 2
                continue


            if in_block_comment and i + 1 < len(line) and line[i:i + 2] == '*/':
                in_block_comment = False
                block_comment_start = None

                result.append(' ')
                i += 2
                continue


            if in_block_comment:
                # Заменяем символы пробелом, кроме переноса строки
                if char == '\n':
                    result.append('\n')
                else:
                    result.append(' ')
                i += 1
                continue


            result.append(char)
            i += 1

        processed_line = ''.join(result)


        if processed_line.strip() or in_block_comment:
            return processed_line, in_block_comment, block_comment_start
        else:
            return None, in_block_comment, block_comment_start

    def get_original_line(self, processed_line: int) -> int:
        for orig, proc in self.line_map:
            if proc == processed_line:
                return orig
        return processed_line

    def get_errors(self):
        return self.errors