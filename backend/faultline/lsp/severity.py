"""Verdict -> editor severity (ADR 0008, decision 5). The mapping follows what each verdict claims; an unknown verdict is an error, never a default."""
from lsprotocol.types import DiagnosticSeverity as Severity

SEVERITY: dict[str, Severity] = {
    "BREAK_WITNESSED": Severity.Error,                  # a reproducible failure under the witness rule
    "SILENT_DIVERGENCE_WITNESSED": Severity.Warning,    # reproducible difference in output; harm is not established
    "EXPOSED": Severity.Warning,                        # a changed symbol is referenced; execution did not settle it
    "POTENTIAL": Severity.Information,                  # breaking changes exist; usage was not resolved
    "INCONCLUSIVE": Severity.Hint,                      # not enough evidence; the reason is in the message
    "HYGIENE": Severity.Hint,                           # versions differ with no relationship
}
NO_DIAGNOSTIC = frozenset({"NO_DIVERGENCE_OBSERVED", "NOT_EXPOSED"})

# the exact verdict words (CLAUDE.md): messages use these and no other wording for a verdict
WORDS = {"BREAK_WITNESSED": "BREAK WITNESSED", "SILENT_DIVERGENCE_WITNESSED": "SILENT DIVERGENCE WITNESSED", "NO_DIVERGENCE_OBSERVED": "NO DIVERGENCE OBSERVED",
         "EXPOSED": "EXPOSED", "POTENTIAL": "POTENTIAL", "NOT_EXPOSED": "NOT EXPOSED", "INCONCLUSIVE": "INCONCLUSIVE", "HYGIENE": "HYGIENE"}


class UnknownVerdict(ValueError):
    pass


def severity_of(verdict: str) -> Severity | None:
    """The severity of a verdict, or None when the verdict is shown by no diagnostic."""
    if verdict in NO_DIAGNOSTIC:
        return None
    try:
        return SEVERITY[verdict]
    except KeyError:
        raise UnknownVerdict(f"no editor severity is defined for the verdict {verdict!r}") from None
