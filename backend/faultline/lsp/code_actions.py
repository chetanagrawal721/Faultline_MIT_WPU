"""textDocument/codeAction: a verified fix as a WorkspaceEdit (ADR 0008, decision 6).

A fix is offered only when all of these hold:
  * the remediation labelled it VERIFIED (fresh runs in the fixed world; the witness is gone and no new one appeared);
  * the file it edits, the consumer's requirements file, is found in the workspace and still has the content the fix was verified against
    (compared by hash, line endings aside);
  * the diagnostic it answers belongs to the consumer repository (a producer's call-site diagnostic has no consumer-side fix).
Nothing is saved, committed or pushed, and nothing is executed. The edit appends the constraint line; the editor shows it and the user applies it.
"""
from dataclasses import dataclass
from pathlib import Path

from lsprotocol import types

from .locations import sha256_of, utf16_len


@dataclass(frozen=True)
class FixInfo:
    finding_id: str
    label: str
    constraint: str
    consumer: str | None
    target_path: str | None
    target_sha256: str | None
    diff: str


def fix_from(d: dict) -> FixInfo:
    return FixInfo(d["finding_id"], d["label"], d["constraint"], d.get("consumer"), d.get("target_path"), d.get("target_sha256"), d.get("diff") or "")


def matches_verified_content(text: str, expected: str | None) -> bool:
    """True when `text` is what the fix was verified against. A checkout that changed the line endings has the same content."""
    return bool(expected) and expected in (sha256_of(text), sha256_of(text.replace("\r\n", "\n")))


def end_edit(text: str, constraint: str) -> types.TextEdit:
    """The edit that appends `constraint` as a last line, in the file's own line-ending style: the same result as the diff the remediation stored."""
    eol = "\r\n" if "\r\n" in text else "\n"
    if not text:
        at = types.Position(line=0, character=0)
        return types.TextEdit(range=types.Range(start=at, end=at), new_text=constraint + eol)
    if text.endswith("\n"):
        at = types.Position(line=text.count("\n"), character=0)
        return types.TextEdit(range=types.Range(start=at, end=at), new_text=constraint + eol)
    last = text.rsplit("\n", 1)[-1]
    at = types.Position(line=text.count("\n"), character=utf16_len(last))
    return types.TextEdit(range=types.Range(start=at, end=at), new_text=eol + constraint + eol)


def find_target(roots: list[Path], rel: str) -> Path | None:
    """The fix's file inside a workspace folder (never outside it)."""
    for r in roots:
        try:
            base = r.resolve()
            p = (base / rel).resolve()
            p.relative_to(base)
        except (OSError, ValueError):
            continue
        if p.is_file():
            return p
    return None


def build_action(diag: types.Diagnostic, fix: FixInfo | None, roots: list[Path], open_text) -> types.CodeAction | None:
    """`open_text(uri)` returns (text, version) for a document the editor has open, or None."""
    data = diag.data if isinstance(diag.data, dict) else {}
    if fix is None or fix.label != "VERIFIED" or not fix.target_path or not fix.constraint:
        return None
    if data.get("role") != "consumer" or data.get("finding_id") != fix.finding_id:
        return None
    target = find_target(roots, fix.target_path)
    if target is None:
        return None
    uri = target.as_uri()
    opened = open_text(uri)
    try:
        text, version = opened if opened is not None else (target.read_bytes().decode("utf-8"), None)         # bytes: read_text would turn CRLF into LF
    except (OSError, UnicodeDecodeError):
        return None
    if not matches_verified_content(text, fix.target_sha256):
        return None                                                       # the file changed since the fix was verified: no action, never a guess
    return types.CodeAction(
        title=f"Faultline: add {fix.constraint} to {fix.target_path} (verified fix)", kind=types.CodeActionKind.QuickFix, diagnostics=[diag],
        edit=types.WorkspaceEdit(document_changes=[types.TextDocumentEdit(
            text_document=types.OptionalVersionedTextDocumentIdentifier(uri=uri, version=version), edits=[end_edit(text, fix.constraint)])]),
        data={"finding_id": fix.finding_id, "target_sha256": fix.target_sha256})
