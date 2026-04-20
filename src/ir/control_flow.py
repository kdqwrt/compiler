from __future__ import annotations

from typing import Dict, List, Set

from src.ir.basic_block import IRFunction, BasicBlock


def build_cfg_map(function: IRFunction) -> Dict[str, List[str]]:
    return {block.label: list(block.successors) for block in function.blocks}


def get_entry_block(function: IRFunction) -> BasicBlock | None:
    if not function.blocks:
        return None
    return function.blocks[0]


def get_exit_blocks(function: IRFunction) -> List[BasicBlock]:
    exits = []
    for block in function.blocks:
        if not block.successors:
            exits.append(block)
    return exits


def get_reachable_blocks(function: IRFunction) -> Set[str]:
    entry = get_entry_block(function)
    if entry is None:
        return set()

    visited: Set[str] = set()
    stack = [entry.label]
    cfg = build_cfg_map(function)

    while stack:
        label = stack.pop()
        if label in visited:
            continue
        visited.add(label)

        for succ in cfg.get(label, []):
            if succ not in visited:
                stack.append(succ)

    return visited


def find_unreachable_blocks(function: IRFunction) -> List[str]:
    reachable = get_reachable_blocks(function)
    return [block.label for block in function.blocks if block.label not in reachable]