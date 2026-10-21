"""Where a finding is shown in a source file. Only lines derived from data Faultline holds are used; a line is never invented.

Order of sources, best first:
  1. the import site stored with the analysis, when the open file still has the hash it had at the analysed commit (fresh);
  2. an import of the affected module found in the open file itself, when the file has changed (the diagnostic is marked as stale);
  3. for the producer repository, the call site checked by O-bind (file, line and column from the analysis).
When none applies there is no precise diagnostic.
"""
import ast
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from ..core.hashing import sha256_hex
from .client_api import FindingInfo


@dataclass(frozen=True)
class Location:
    line: int                    # zero-based, as the protocol wants
    start: int                   # UTF-16 code units
    end: int
    source: str                  # what the location was derived from, shown in the diagnostic data


@dataclass(frozen=True)
class Placed:
    loc: Location
    fresh: bool | None           # True: the file is as analysed; False: it has changed since; None: not known (no stored hash)


def utf16_len(s: str) -> int:
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


def sha256_of(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


# ---- paths and URIs -----------------------------------------------------------------------------------------------------------------

def path_of(uri: str) -> Path:
    """A file URI as a path (Windows drive letters, percent-encoding, non-ASCII names and UNC forms included)."""
    u = urlparse(uri)
    return Path(url2pathname(unquote(u.path))) if not u.netloc else Path(f"//{u.netloc}{unquote(u.path)}")


def relative_path(uri: str, roots: list[Path]) -> str | None:
    """The path of the file below a workspace folder, with forward slashes, or None when it is outside every folder (never a path with `..`)."""
    p = path_of(uri)
    try:
        real = p.resolve()
    except OSError:
        real = p
    for r in roots:
        try:
            base = r.resolve()
        except OSError:
            base = r
        try:
            rel = os.path.relpath(os.path.normcase(str(real)), os.path.normcase(str(base)))
        except ValueError:                                           # another drive
            continue
        if not rel.startswith("..") and not os.path.isabs(rel):
            # the original spelling of the path below the folder, not the lower-cased one
            parts = real.parts[len(base.parts):]
            return "/".join(parts) if parts else None
    return None


# ---- finding in the text -------------------------------------------------------------------------------------------------------------------

def _matches(name: str, modules: set[str]) -> bool:
    return any(name == m or name.startswith(m + ".") or m.startswith(name + ".") for m in modules)


def _line_range(lines: list[str], line0: int, col_bytes: int, source: str) -> Location:
    line = lines[line0] if 0 <= line0 < len(lines) else ""
    prefix = line.encode("utf-8")[:col_bytes].decode("utf-8", "ignore")           # parser columns are UTF-8 byte offsets
    return Location(line0, utf16_len(prefix), utf16_len(line), source)


def import_location(text: str, modules: tuple[str, ...] | list[str]) -> Location | None:
    """The first import in `text` of one of `modules` (or of a package that contains one), as a range to the end of its line; None if there is none."""
    wanted = set(modules)
    if not wanted:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
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
    return _line_range(text.splitlines(), first.lineno - 1, first.col_offset, "an import of the affected module in the open file")


def place(text: str, rel_path: str | None, f: FindingInfo) -> Placed | None:
    """Where finding `f` is shown in this file, or None."""
    lines = text.splitlines()
    if f.role == "producer":
        for b in f.bind_sites:
            if rel_path is not None and b.file == rel_path and 1 <= b.line <= len(lines):
                return Placed(_line_range(lines, b.line - 1, b.col, "the call site checked by O-bind, from the analysis"), None)
        for x in f.static_sites:
            if rel_path is not None and x.file == rel_path and 1 <= x.line <= len(lines):
                return Placed(_line_range(lines, x.line - 1, x.col, f"the reference to {x.symbol} ({x.change}), read from source by the analysis"), None)
        return None
    here = [s for s in f.sites if rel_path is not None and s.file == rel_path]
    digest = sha256_of(text)
    if here and any(s.sha256 == digest for s in here):                                   # the file is exactly as analysed: the stored line is right
        s = min((x for x in here if x.sha256 == digest), key=lambda x: x.line)
        if 1 <= s.line <= len(lines):
            return Placed(_line_range(lines, s.line - 1, 0, "the import site stored with the analysis"), True)
    found = import_location(text, f.modules)                                              # changed (or never analysed): read the current text
    if found is None:
        return None
    return Placed(found, False if here else None)
