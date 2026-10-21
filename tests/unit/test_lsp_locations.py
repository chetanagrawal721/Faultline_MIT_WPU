"""M13.8: where a finding is shown, how a file is found from its URI, the severity of each verdict, and what happens when a file changes."""
from pathlib import Path

import pytest
from lsprotocol.types import DiagnosticSeverity as Sev

from faultline.lsp.client_api import BindSiteInfo, FindingInfo, ImportSiteInfo
from faultline.lsp.diagnostics import STALE_NOTE, to_diagnostics
from faultline.lsp.locations import import_location, path_of, place, relative_path, sha256_of, utf16_len
from faultline.lsp.severity import NO_DIAGNOSTIC, SEVERITY, WORDS, UnknownVerdict, severity_of

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures" / "repos"


def finding(**kw) -> FindingInfo:
    base = dict(finding_id="fnd_1", analysis_id="an_1", cell_id="cell_1", verdict="BREAK_WITNESSED", headline="h", artifact="acme-models", role="consumer",
                consumers=("faultline-demo/notify-svc",), modules=("acme_models.web",))
    return FindingInfo(**{**base, **kw})


# ---- TC-13.8.1: positions are exact -------------------------------------------------------------------------------------------------------

def test_the_import_line_of_a_real_consumer_file_is_found_exactly():
    text = (FIX / "notify-svc" / "D" / "app" / "main.py").read_text(encoding="utf-8")
    loc = import_location(text, ("acme_models.web",))
    lines = text.splitlines()
    assert lines[loc.line] == "import acme_models.web as shared" and (loc.start, loc.end) == (0, len(lines[loc.line])) and loc.line == 1


def test_a_stored_import_site_is_used_when_the_file_is_as_analysed():
    text = (FIX / "notify-svc" / "D" / "app" / "main.py").read_text(encoding="utf-8")
    f = finding(sites=(ImportSiteInfo("acme_models.web", "app/main.py", 2, sha256_of(text)),))
    p = place(text, "app/main.py", f)
    assert p.fresh is True and p.loc.line == 1 and p.loc.source == "the import site stored with the analysis"


def test_a_changed_file_is_read_again_and_marked_stale():
    old = "import os\nimport acme_models.web\n"
    f = finding(sites=(ImportSiteInfo("acme_models.web", "app/main.py", 2, sha256_of(old)),))
    new = "\n\nimport os\nimport sys\nimport acme_models.web\n"                      # three lines were added above the import
    p = place(new, "app/main.py", f)
    assert p.fresh is False and p.loc.line == 4 and new.splitlines()[p.loc.line] == "import acme_models.web"
    d = to_diagnostics(new, "app/main.py", [f])[0]
    assert d.range.start.line == 4 and d.message.endswith(STALE_NOTE) and d.data["stale"] is True
    fresh = to_diagnostics(old, "app/main.py", [f])[0]
    assert fresh.range.start.line == 1 and STALE_NOTE not in fresh.message and fresh.data["stale"] is False


def test_a_removed_import_leaves_no_diagnostic_and_no_invented_line():
    old = "import acme_models.web\n"
    f = finding(sites=(ImportSiteInfo("acme_models.web", "app/main.py", 1, sha256_of(old)),))
    assert place("import os\n", "app/main.py", f) is None
    assert to_diagnostics("import os\n", "app/main.py", [f]) == []


def test_a_file_that_was_not_analysed_but_imports_the_module_is_shown_without_a_freshness_claim():
    f = finding(sites=(ImportSiteInfo("acme_models.web", "app/other.py", 1, "0" * 64),))
    p = place("from acme_models.web import make_app\n", "app/new.py", f)
    assert p is not None and p.fresh is None


def test_a_finding_without_modules_or_sites_has_no_location():
    assert place("import acme_models.web\n", "a.py", finding(modules=(), sites=())) is None


def test_a_producer_call_site_is_placed_from_the_analysis():
    text = (FIX / "acme-http" / "src" / "acme_http" / "retry.py").read_text(encoding="utf-8")
    lines = text.splitlines()
    f = finding(role="producer", artifact="acme-http", bind_sites=(BindSiteInfo("src/acme_http/retry.py", 7, 11),))
    p = place(text, "src/acme_http/retry.py", f)
    assert p.loc.line == 6 and p.loc.start == 11 and p.loc.end == len(lines[6]) and p.fresh is None and "O-bind" in p.loc.source
    assert place(text, "src/acme_http/other.py", f) is None, "another file of the producer"
    assert place(text, None, f) is None
    assert place(text, "src/acme_http/retry.py", finding(role="producer", bind_sites=(BindSiteInfo("src/acme_http/retry.py", 999, 0),))) is None, "a line past the end is never used"


def test_columns_are_utf16_units_for_emoji_and_cjk_before_the_import():
    text = 'x = "😀日本"; import acme_models.web\n'
    loc = import_location(text, ("acme_models.web",))
    prefix = 'x = "😀日本"; '
    assert loc.start == utf16_len(prefix) == len(prefix) + 1 and loc.end == utf16_len(text.rstrip("\n"))
    p = text.encode("utf-8").index(b"import")
    assert p != loc.start, "the UTF-8 byte offset is not the UTF-16 column"


@pytest.mark.parametrize("src,expect", [
    ("import acme_models.web as w\n", 0), ("from acme_models import web\n", 0), ("from acme_models.web import make_app\n", 0),
    ("import os, acme_models.web\n", 0), ("if True:\n    import acme_models.web\n", 1), ("def f():\n    from acme_models.web import x\n", 1),
])
def test_forms_of_import_are_found(src, expect):
    assert import_location(src, ("acme_models.web",)).line == expect


@pytest.mark.parametrize("src", ["import acme_models.customer\n", "from . import web\n", "import acme_modelsx.web\n", "x = 'import acme_models.web'\n", "def broken(:\n"])
def test_other_text_is_not_an_import_of_the_module(src):
    assert import_location(src, ("acme_models.web",)) is None


# ---- TC-13.8.2: URIs, paths and encodings -------------------------------------------------------------------------------------------------------

def test_windows_uris_become_paths():
    assert path_of("file:///c%3A/Users/Chetan/app.py") == Path("c:/Users/Chetan/app.py") or str(path_of("file:///c%3A/Users/Chetan/app.py")).lower().endswith(r"c:\users\chetan\app.py")
    assert "é" in str(path_of("file:///c%3A/Users/Ch%C3%A9tan/app.py"))
    assert " " in str(path_of("file:///c%3A/My%20Project/app.py"))


def test_relative_paths_inside_the_workspace(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x\n", encoding="utf-8")
    uri = (tmp_path / "app" / "main.py").as_uri()
    assert relative_path(uri, [tmp_path]) == "app/main.py"
    assert relative_path(uri, [tmp_path / "app"]) == "main.py"


def test_names_with_spaces_and_non_ascii_letters(tmp_path):
    d = tmp_path / "my project" / "módulo"
    d.mkdir(parents=True)
    (d / "ficheiro 1.py").write_text("x\n", encoding="utf-8")
    assert relative_path((d / "ficheiro 1.py").as_uri(), [tmp_path / "my project"]) == "módulo/ficheiro 1.py"


@pytest.mark.skipif(__import__("os").name != "nt", reason="drive letters and case-insensitive paths are Windows rules")
def test_the_case_of_a_windows_path_does_not_matter(tmp_path):
    (tmp_path / "App").mkdir()
    (tmp_path / "App" / "Main.py").write_text("x\n", encoding="utf-8")
    uri = "file:///" + str(tmp_path / "App" / "Main.py").replace("\\", "/").lower().replace(":", "%3A")
    assert relative_path(uri, [Path(str(tmp_path).upper())]).lower() == "app/main.py"


def test_a_file_outside_the_workspace_or_reached_through_dotdot_is_not_in_it(tmp_path):
    inside = tmp_path / "ws"
    inside.mkdir()
    (tmp_path / "secret.py").write_text("x\n", encoding="utf-8")
    assert relative_path((tmp_path / "secret.py").as_uri(), [inside]) is None
    sneaky = (inside / ".." / "secret.py")
    assert relative_path(sneaky.as_uri(), [inside]) is None, "a path with .. that leaves the folder is outside it"
    assert relative_path((inside / "a" / ".." / "b.py").as_uri(), [inside]) == "b.py"


def test_a_symlink_that_leaves_the_workspace_is_outside_it(tmp_path):
    ws, out = tmp_path / "ws", tmp_path / "out"
    ws.mkdir()
    out.mkdir()
    (out / "x.py").write_text("x\n", encoding="utf-8")
    try:
        (ws / "link.py").symlink_to(out / "x.py")
    except OSError:
        pytest.skip("symbolic links need a privilege here")
    assert relative_path((ws / "link.py").as_uri(), [ws]) is None


def test_crlf_text_gives_the_same_lines_as_lf_text():
    lf = "import os\nimport acme_models.web\nprint(1)\n"
    crlf = lf.replace("\n", "\r\n")
    assert import_location(crlf, ("acme_models.web",)).line == import_location(lf, ("acme_models.web",)).line == 1
    assert import_location(crlf, ("acme_models.web",)).end == len("import acme_models.web")


def test_a_file_without_a_final_newline_and_an_empty_file():
    assert import_location("import acme_models.web", ("acme_models.web",)).end == len("import acme_models.web")
    assert import_location("", ("acme_models.web",)) is None


# ---- TC-13.8.3: severity per verdict --------------------------------------------------------------------------------------------------------------

def test_every_verdict_has_the_severity_of_the_adr():
    assert {v: severity_of(v) for v in ("BREAK_WITNESSED", "SILENT_DIVERGENCE_WITNESSED", "EXPOSED", "POTENTIAL", "INCONCLUSIVE", "HYGIENE")} == {
        "BREAK_WITNESSED": Sev.Error, "SILENT_DIVERGENCE_WITNESSED": Sev.Warning, "EXPOSED": Sev.Warning, "POTENTIAL": Sev.Information,
        "INCONCLUSIVE": Sev.Hint, "HYGIENE": Sev.Hint}
    assert severity_of("NO_DIVERGENCE_OBSERVED") is None and severity_of("NOT_EXPOSED") is None
    assert set(SEVERITY) | NO_DIAGNOSTIC == set(WORDS), "every verdict is either shown or deliberately not shown"
    assert len({SEVERITY[v] for v in SEVERITY}) == 4, "four distinct severities exist in the mapping"


def test_an_unknown_verdict_raises_instead_of_defaulting():
    with pytest.raises(UnknownVerdict):
        severity_of("COMPATIBLE")
    with pytest.raises(UnknownVerdict):
        to_diagnostics("import acme_models.web\n", "a.py", [finding(verdict="MADE_UP")])


def test_messages_use_the_exact_verdict_words():
    master = (ROOT / "docs" / "FAULTLINE_MASTER.md").read_text(encoding="utf-8")
    for word in WORDS.values():
        assert word in master, word
    assert set(WORDS.values()) == {"BREAK WITNESSED", "SILENT DIVERGENCE WITNESSED", "NO DIVERGENCE OBSERVED", "EXPOSED", "POTENTIAL", "NOT EXPOSED", "INCONCLUSIVE", "HYGIENE"}
    d = to_diagnostics("import acme_models.web\n", "a.py", [finding(verdict="SILENT_DIVERGENCE_WITNESSED", headline="the output differs")])[0]
    assert d.message == "SILENT DIVERGENCE WITNESSED: the output differs" and d.severity == Sev.Warning and d.source == "faultline" and d.code == "fnd_1"


def test_a_verdict_that_is_not_shown_gives_no_diagnostic():
    assert to_diagnostics("import acme_models.web\n", "a.py", [finding(verdict="NO_DIVERGENCE_OBSERVED")]) == []
    assert to_diagnostics("import acme_models.web\n", "a.py", [finding(verdict="NOT_EXPOSED")]) == []
