"""Where a finding is shown in a consumer's source file. Only lines derived from the file itself are used; a line is never invented.

First slice (M13.7): the first import statement in the open file that brings in one of the cell's entry modules. M13.8 adds the other sources
(call sites) and the file-hash freshness check.
"""
import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    line: int                    # zero-based, as the protocol wants
    start: int                   # UTF-16 code units
    end: int
    source: str                  # what the location was derived from, shown in the diagnostic data


def utf16_len(s: str) -> int:
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


def _matches(name: str, modules: set[str]) -> bool:
    return any(name == m or name.startswith(m + ".") or m.startswith(name + ".") for m in modules)


def import_location(text: str, modules: tuple[str, ...] | list[str]) -> Location | None:
    """The first import in `text` of one of `modules` (or of a package that contains one), as a whole-line range; None if there is none."""
    wanted = set(modules)
    if not wanted:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    lines = text.splitlines()
    hits: list[ast.stmt] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(_matches(a.name, wanted) for a in node.names):
            hits.append(node)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and (
                _matches(node.module, wanted) or any(_matches(f"{node.module}.{a.name}", wanted) for a in node.names)):
            hits.append(node)
    if not hits:
        return None
    first = min(hits, key=lambda n: (n.lineno, n.col_offset))
    line = lines[first.lineno - 1] if first.lineno - 1 < len(lines) else ""
    prefix = line.encode("utf-8")[:first.col_offset].decode("utf-8", "ignore")           # ast columns are UTF-8 byte offsets
    return Location(first.lineno - 1, utf16_len(prefix), utf16_len(line), "an import of the affected module in the open file")
