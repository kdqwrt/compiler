from __future__ import annotations


class LabelManager:
    def __init__(self) -> None:
        self.counter = 0

    def new_label(self, prefix: str = "L") -> str:
        self.counter += 1
        return f"{prefix}{self.counter}"