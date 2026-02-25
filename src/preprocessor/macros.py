class MacroProcessor:

    def __init__(self):
        self.macros = {}
        self.conditional_stack = []
        self.errors = []
        self.recursion_depth = {}
        self.max_recursion_depth = 100

    def define(self, name: str, value: str = ""):
        if not self._is_valid_identifier(name):
            self.errors.append(f"Некорректное имя макроса: {name}")
            return

        if name in self.macros:
            self.errors.append(f"Переопределение макроса: {name}")

        self.macros[name] = value
        self.recursion_depth[name] = 0

    def undefine(self, name: str):
        if name in self.macros:
            del self.macros[name]
            del self.recursion_depth[name]

    def is_defined(self, name: str) -> bool:
        return name in self.macros

    def process_directives(self, source: str) -> str:
        lines = source.splitlines(keepends=True)
        result_lines = []
        skip_block = False
        skip_depth = 0

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            if skip_block and not stripped.startswith('#endif'):
                continue

            if stripped.startswith('#'):
                processed, skip_block, skip_depth = self._process_directive(
                    stripped, line_num, skip_block, skip_depth
                )
                if processed is not None:
                    result_lines.append(processed + '\n')
                continue

            if not skip_block:
                processed_line = self._expand_macros(line, line_num)
                result_lines.append(processed_line)
            else:
                result_lines.append(line)

        return ''.join(result_lines)

    def _process_directive(self, line: str, line_num: int,
                           skip_block: bool, skip_depth: int):

        parts = line.split()
        directive = parts[0].lower()

        if directive == '#define':
            if len(parts) < 2:
                self.errors.append(f"[Строка {line_num}] Синтаксическая ошибка в #define")
                return None, skip_block, skip_depth

            name = parts[1]
            value = ' '.join(parts[2:]) if len(parts) > 2 else ""
            self.define(name, value)
            return None, skip_block, skip_depth

        elif directive == '#undef':
            if len(parts) != 2:
                self.errors.append(f"[Строка {line_num}] Синтаксическая ошибка в #undef")
                return None, skip_block, skip_depth

            name = parts[1]
            self.undefine(name)
            return None, skip_block, skip_depth

        elif directive == '#ifdef':
            if len(parts) != 2:
                self.errors.append(f"[Строка {line_num}] Синтаксическая ошибка в #ifdef")
                return None, skip_block, skip_depth

            name = parts[1]
            condition_met = self.is_defined(name)

            if skip_block:
                skip_depth += 1
            elif not condition_met:
                skip_block = True
                skip_depth = 1

            return None, skip_block, skip_depth

        elif directive == '#ifndef':
            if len(parts) != 2:
                self.errors.append(f"[Строка {line_num}] Синтаксическая ошибка в #ifndef")
                return None, skip_block, skip_depth

            name = parts[1]
            condition_met = not self.is_defined(name)

            if skip_block:
                skip_depth += 1
            elif not condition_met:
                skip_block = True
                skip_depth = 1

            return None, skip_block, skip_depth

        elif directive == '#endif':
            if skip_depth > 0:
                skip_depth -= 1
                if skip_depth == 0:
                    skip_block = False

            return None, skip_block, skip_depth

        else:
            self.errors.append(f"[Строка {line_num}] Неизвестная директива: {directive}")
            return None, skip_block, skip_depth

    def _expand_macros(self, line: str, line_num: int) -> str:
        result = []
        i = 0

        while i < len(line):

            if line[i].isalpha() or line[i] == '_':
                start = i
                while i < len(line) and (line[i].isalnum() or line[i] == '_'):
                    i += 1

                name = line[start:i]

                if name in self.macros:

                    if self.recursion_depth.get(name, 0) >= self.max_recursion_depth:
                        self.errors.append(
                            f"[Строка {line_num}] Обнаружена рекурсия в макросе: {name}"
                        )
                        result.append(name)
                        continue

                    self.recursion_depth[name] += 1

                    value = self.macros[name]


                    expanded_value = self._expand_macros(value, line_num)


                    self.recursion_depth[name] -= 1

                    result.append(expanded_value)
                else:
                    result.append(name)

                continue


            result.append(line[i])
            i += 1

        return ''.join(result)

    def _is_valid_identifier(self, name: str) -> bool:
        if not name or not (name[0].isalpha() or name[0] == '_'):
            return False

        for char in name[1:]:
            if not (char.isalnum() or char == '_'):
                return False

        return True

    def get_errors(self):
        return self.errors