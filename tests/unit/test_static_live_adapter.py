"""Information severity (TC-13.8.5): static evidence reaches the live verdict only where execution settled nothing, and only as EXPOSED or POTENTIAL.

The static evidence in these tests is built by the real pipeline (source parsed, API surfaces extracted and compared, references resolved); only the wheels
are replaced by two small source trees. Nothing here sets an exposure by hand.
"""
from pathlib import Path

import pytest
from lsprotocol.types import DiagnosticSeverity as Sev

from faultline.analysis import static
from faultline.diff.delta import compute_delta
from faultline.diff.surface import extract
from faultline.lsp.client_api import FindingInfo, ImportSiteInfo, StaticSiteInfo
from faultline.lsp.diagnostics import to_diagnostics
from faultline.lsp.locations import sha256_of
from faultline.usage.exposure import compute_exposure
from faultline.usage.index import build_index
from faultline.verdicts.engine import Evidence, decide
from faultline.witnesses.verify import Decision, EntryDecision

ROOT = Path(__file__).resolve().parents[2]
OLD = {"urllib3/__init__.py": b"from .retry import Retry\n",
       "urllib3/retry.py": b"class Retry:\n    def __init__(self, total=10, method_whitelist=None, allowed_methods=None, backoff_factor=0): pass\n"}
NEW = {"urllib3/__init__.py": b"from .retry import Retry\n",
       "urllib3/retry.py": b"class Retry:\n    def __init__(self, total=10, allowed_methods=None, backoff_factor=0): pass\n"}
PACKAGE = {"distribution": "urllib3", "import_root": "urllib3", "from": "1.26.18", "to": "2.2.3", "from_wheel": "a", "to_wheel": "b", "breaking": True, "incomplete": False}


def acme_http_sources() -> dict[str, bytes]:
    root = ROOT / "fixtures" / "repos" / "acme-http"
    return {p.relative_to(root).as_posix(): p.read_bytes().replace(b"urllib3.util.retry", b"urllib3.retry") for p in root.rglob("*.py")}


def evidence_of(sources: dict[str, bytes], old=OLD, new=NEW) -> static.StaticEvidence:
    delta = compute_delta(extract(old, "urllib3"), extract(new, "urllib3"))
    result = compute_exposure(build_index(sources, {"urllib3"}), {"urllib3": delta})
    return static.StaticEvidence(result, None, [{**PACKAGE, "breaking": delta.breaking}])


def unsettled() -> Evidence:
    """A run that settled nothing: the decision table gives INCONCLUSIVE."""
    return Evidence(relationship_level="L2", cell_state="PENDING", decisions=(), run_problem="the sandbox timed out")


def never_called():
    raise AssertionError("static evidence must not be read for a result execution settled")


def test_an_unsettled_run_with_a_reference_to_a_changed_api_becomes_exposed():
    st = evidence_of(acme_http_sources())
    out, used, note = static.settle(unsettled(), lambda: st)
    assert decide(unsettled()).outcome == "INCONCLUSIVE"
    assert out.outcome == "EXPOSED" and used is st and not out.witness_entries
    assert out.sub_label == "static-confirmed"                                               # the binding simulation says the call no longer binds
    assert any("timed out" in r for r in out.reasons), "why execution did not settle it stays in the verdict"
    text = static.headline(out, st, "acme-http")
    assert "urllib3.retry.Retry" in text and "1.26.18" in text and "2.2.3" in text and "Not executed because" in text
    assert not any(w in text.lower() for w in ("reproduced", "witness", "compatible", "proof", "guarantee"))


def test_an_unresolved_reference_to_a_package_with_breaking_changes_becomes_potential():
    sources = {"app/__init__.py": b"", "app/plug.py": b"import urllib3\n\ndef load(name):\n    return getattr(urllib3, name)()\n"}
    st = evidence_of(sources)
    assert st.result.dynamic and not st.result.breaking_exposures
    out, used, note = static.settle(unsettled(), lambda: st)
    assert out.outcome == "POTENTIAL" and used is st and out.rule == 7
    assert "urllib3 1.26.18→2.2.3" in static.headline(out, st, "acme-http")


def test_a_settled_result_is_never_changed_and_static_evidence_is_not_even_read():
    witnessed = Evidence(relationship_level="L2", cell_state="PENDING", decisions=(EntryDecision("a", Decision.WITNESS, "r"),))
    observed = Evidence(relationship_level="L2", cell_state="PENDING", decisions=(EntryDecision("a", Decision.NO_DIVERGENCE, "r"),))
    for ev, want in ((witnessed, "BREAK_WITNESSED"), (observed, "NO_DIVERGENCE_OBSERVED")):
        out, used, note = static.settle(ev, never_called)
        assert out.outcome == want and used is None and out == decide(ev)


def test_without_static_evidence_nothing_changes():
    assert static.settle(unsettled(), None)[0].outcome == "INCONCLUSIVE"
    for why in (static.StaticEvidence(why_not="the artifact does not refer to any package whose version differs"),
                static.StaticEvidence(why_not="could not read the API surface of a wheel")):
        out, used, note = static.settle(unsettled(), lambda why=why: why)
        assert out.outcome == "INCONCLUSIVE" and used is None and note == {"considered": False, "why_not": why.why_not}


def test_a_changed_api_that_the_artifact_does_not_use_does_not_raise_anything():
    st = evidence_of({"app/__init__.py": b"", "app/x.py": b"import urllib3\nurllib3.PoolManager()\n"})
    out, used, note = static.settle(unsettled(), lambda: st)
    assert out.outcome == "INCONCLUSIVE" and used is None, "NOT EXPOSED is never taken from static evidence: it would hide the run problem"
    assert note["considered"] is True and note["static_outcome"] == "NOT_EXPOSED"


def test_an_api_that_did_not_change_raises_nothing():
    st = evidence_of(acme_http_sources(), OLD, OLD)
    assert static.settle(unsettled(), lambda: st)[1] is None


def test_the_rule_is_part_of_the_pair_identity():
    from dataclasses import replace

    from faultline.evidence.pair_key import explain, pair_key, record
    from faultline.verdicts.engine import STATIC_RULE
    from tests.unit.test_pair_key import base
    a = base()
    b = replace(a, static_rule=STATIC_RULE)
    assert pair_key(a) != pair_key(b) and [e["input"] for e in explain(record(a), record(b))] == ["static_rule"]


# ---- the normal diagnostics pipeline -----------------------------------------------------------------------------------------------------

def finding(**kw) -> FindingInfo:
    base = dict(finding_id="fnd_s", analysis_id="an_1", cell_id="c1", verdict="EXPOSED", headline="h", artifact="acme-http", role="producer",
                consumers=("faultline-demo/svc",), modules=("acme_http.retry",))
    return FindingInfo(**{**base, **kw})


def test_exposed_is_shown_as_a_warning_and_potential_as_information_on_real_lines():
    text = (ROOT / "fixtures" / "repos" / "acme-http" / "src" / "acme_http" / "retry.py").read_text(encoding="utf-8")
    exposed = finding(static_sites=(StaticSiteInfo("src/acme_http/retry.py", 7, 0, "urllib3.retry.Retry", "SIGNATURE_BREAKING"),))
    d = to_diagnostics(text, "src/acme_http/retry.py", [exposed])
    assert len(d) == 1 and d[0].range.start.line == 6 and d[0].severity == Sev.Warning and d[0].message.startswith("EXPOSED: ")
    consumer_text = "import os\nimport acme_http.retry\n"
    potential = finding(verdict="POTENTIAL", role="consumer", sites=(ImportSiteInfo("acme_http.retry", "app/main.py", 2, sha256_of(consumer_text)),))
    d = to_diagnostics(consumer_text, "app/main.py", [potential])
    assert len(d) == 1 and d[0].severity == Sev.Information and d[0].range.start.line == 1 and d[0].message.startswith("POTENTIAL: ")
    assert d[0].data["verdict"] == "POTENTIAL" and d[0].code == "fnd_s"


def test_a_producer_finding_without_a_stored_source_site_has_no_diagnostic():
    text = "x = 1\n"
    assert to_diagnostics(text, "src/a.py", [finding()]) == [], "no line is invented when the analysis stored none"
    other = finding(static_sites=(StaticSiteInfo("src/other.py", 3, 0, "s", "REMOVED"),))
    assert to_diagnostics(text, "src/a.py", [other]) == []


def test_other_severities_are_unchanged():
    text = "import os\nimport acme_http.retry\n"
    for verdict, sev in (("BREAK_WITNESSED", Sev.Error), ("SILENT_DIVERGENCE_WITNESSED", Sev.Warning), ("INCONCLUSIVE", Sev.Hint)):
        f = finding(verdict=verdict, role="consumer", sites=(ImportSiteInfo("acme_http.retry", "app/main.py", 2, sha256_of(text)),))
        assert [x.severity for x in to_diagnostics(text, "app/main.py", [f])] == [sev]
    for verdict in ("NO_DIVERGENCE_OBSERVED", "NOT_EXPOSED"):
        assert to_diagnostics(text, "app/main.py", [finding(verdict=verdict, role="consumer")]) == []


@pytest.mark.parametrize("verdict", ["EXPOSED", "POTENTIAL"])
def test_static_verdicts_are_never_witnessed_verdicts(verdict):
    from faultline.verdicts.engine import STATIC_VERDICTS, WITNESSED_VERDICTS
    assert verdict in STATIC_VERDICTS and verdict not in WITNESSED_VERDICTS
