"""Findings -> LSP diagnostics. One diagnostic per finding that has a location in the open file and a verdict that is shown."""
from lsprotocol import types

from .client_api import FindingInfo
from .locations import import_location
from .severity import WORDS, severity_of


def to_diagnostics(text: str, findings: list[FindingInfo]) -> list[types.Diagnostic]:
    out: list[types.Diagnostic] = []
    for f in findings:
        sev = severity_of(f.verdict)
        if sev is None:
            continue
        loc = import_location(text, f.modules)
        if loc is None:                                                      # no line derived from this file: no diagnostic, and no invented line
            continue
        out.append(types.Diagnostic(
            range=types.Range(start=types.Position(line=loc.line, character=loc.start), end=types.Position(line=loc.line, character=loc.end)),
            message=f"{WORDS[f.verdict]}: {f.headline}", severity=sev, source="faultline", code=f.finding_id,
            data={"finding_id": f.finding_id, "verdict": f.verdict, "analysis_id": f.analysis_id, "cell_id": f.cell_id, "location": loc.source}))
    return out
