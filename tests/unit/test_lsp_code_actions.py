"""M13.9: the code action offers a verified, current fix as a WorkspaceEdit on the right file, and nothing otherwise."""
import difflib
from pathlib import Path

import pytest
from lsprotocol import types

from faultline.lsp.code_actions import FixInfo, build_action, end_edit, find_target, matches_verified_content
from faultline.lsp.locations import sha256_of
from faultline.remediation.minimal import diff_for
from tests.fake_api import FakeApi, cell, finding, fix
from tests.lsp_client import LspClient

REQ = "flask==2.2.2\nclick==8.1.7\nitsdangerous==2.1.2\nbisect-svc-dep @ git+https://github.com/x/y@main\n"


def apply(text: str, edit: types.TextEdit) -> str:
    """Apply one insertion the way an editor does (UTF-16 columns, lines split on \\n)."""
    lines = text.split("\n")
    r = edit.range
    assert r.start == r.end
    line = lines[r.start.line] if r.start.line < len(lines) else ""
    col = len(line.encode("utf-16-le")[:r.start.character * 2].decode("utf-16-le"))
    if r.start.line >= len(lines):
        return text + edit.new_text
    lines[r.start.line] = line[:col] + edit.new_text + line[col:]
    return "\n".join(lines)


def diag(role="consumer", fid="fnd_1") -> types.Diagnostic:
    return types.Diagnostic(range=types.Range(start=types.Position(line=1, character=0), end=types.Position(line=1, character=20)), message="BREAK WITNESSED: x",
                            severity=types.DiagnosticSeverity.Error, source="faultline", code=fid, data={"finding_id": fid, "role": role, "verdict": "BREAK_WITNESSED"})


def info(text=REQ, **kw) -> FixInfo:
    base = dict(finding_id="fnd_1", label="VERIFIED", constraint="werkzeug<3", consumer="faultline-demo/bisect-svc", target_path="requirements.txt",
                target_sha256=sha256_of(text), diff=diff_for("requirements.txt", text, "werkzeug<3"))
    return FixInfo(**{**base, **kw})


def workspace(tmp_path: Path, text: str = REQ) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "requirements.txt").write_text(text, encoding="utf-8", newline="")
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "main.py").write_text("from acme_bisect.web import make_app\n", encoding="utf-8")
    return tmp_path


# ---- TC-13.9.1: the edit is exactly the stored fix ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [REQ, REQ.rstrip("\n"), "", "flask==2.2.2\n", "résumé-pkg==1\n"])
def test_applying_the_edit_gives_the_content_the_stored_diff_describes(text):
    edit = end_edit(text, "werkzeug<3")
    applied = apply(text, edit)
    expected_new = (text if text.endswith("\n") or not text else text + "\n") + "werkzeug<3\n"
    assert applied == expected_new
    stored = diff_for("requirements.txt", text, "werkzeug<3")
    again = "".join(difflib.unified_diff(text.splitlines(keepends=True), applied.splitlines(keepends=True), fromfile="a/requirements.txt", tofile="b/requirements.txt"))
    assert again == stored, "the edit and the stored diff say the same"


def test_a_crlf_file_gets_a_crlf_line():
    text = "flask==2.2.2\r\nclick==8.1.7\r\n"
    assert apply(text, end_edit(text, "werkzeug<3")) == text + "werkzeug<3\r\n"
    no_eol = "flask==2.2.2\r\nclick==8.1.7"
    assert apply(no_eol, end_edit(no_eol, "werkzeug<3")) == no_eol + "\r\nwerkzeug<3\r\n"


def test_a_verified_fix_for_the_current_file_gives_one_action(tmp_path):
    ws = workspace(tmp_path)
    a = build_action(diag(), info(), [ws], lambda uri: None)
    assert a is not None and a.kind == types.CodeActionKind.QuickFix and a.title.startswith("Faultline: add werkzeug<3 to requirements.txt")
    assert a.diagnostics[0].code == "fnd_1" and a.is_preferred is None
    ch = a.edit.document_changes[0]
    assert Path(__import__("faultline.lsp.locations", fromlist=["x"]).path_of(ch.text_document.uri)).name == "requirements.txt" and ch.text_document.version is None
    assert apply(REQ, ch.edits[0]) == REQ + "werkzeug<3\n"


def test_a_checkout_with_other_line_endings_has_the_same_content(tmp_path):
    crlf = REQ.replace("\n", "\r\n")
    ws = workspace(tmp_path, crlf)
    a = build_action(diag(), info(REQ), [ws], lambda uri: None)
    assert a is not None and apply(crlf, a.edit.document_changes[0].edits[0]).endswith("\r\nwerkzeug<3\r\n")
    assert matches_verified_content(crlf, sha256_of(REQ)) and not matches_verified_content(REQ + "x\n", sha256_of(REQ))


def test_an_open_document_is_used_with_its_version(tmp_path):
    ws = workspace(tmp_path, "something else entirely\n")             # the disk differs, the open buffer is the verified content
    a = build_action(diag(), info(), [ws], lambda uri: (REQ, 7) if uri.endswith("requirements.txt") else None)
    assert a is not None and a.edit.document_changes[0].text_document.version == 7
    b = build_action(diag(), info(), [ws], lambda uri: ("unsaved edit\n", 8) if uri.endswith("requirements.txt") else None)
    assert b is None, "the open buffer has changed: no action, whatever the disk says"


# ---- TC-13.9.2: no action when the fix is not verified or not current ----------------------------------------------------------------

@pytest.mark.parametrize("why,kw", [
    ("suggested, not verified", dict(label="SUGGESTED")), ("no constraint", dict(constraint="")), ("no target file", dict(target_path=None)),
    ("another finding", dict(finding_id="fnd_other")), ("no recorded hash", dict(target_sha256=None)),
])
def test_an_unverified_or_incomplete_fix_gives_no_action(tmp_path, why, kw):
    assert build_action(diag(), info(**kw), [workspace(tmp_path)], lambda u: None) is None, why


def test_a_file_that_changed_since_the_fix_was_verified_gives_no_action(tmp_path):
    ws = workspace(tmp_path)
    (ws / "requirements.txt").write_text(REQ + "new-pin==1\n", encoding="utf-8")
    assert build_action(diag(), info(), [ws], lambda u: None) is None


def test_a_producer_diagnostic_has_no_consumer_side_fix(tmp_path):
    assert build_action(diag(role="producer"), info(), [workspace(tmp_path)], lambda u: None) is None


def test_no_fix_at_all_and_a_missing_file(tmp_path):
    assert build_action(diag(), None, [workspace(tmp_path)], lambda u: None) is None
    assert build_action(diag(), info(target_path="missing/requirements.txt"), [workspace(tmp_path)], lambda u: None) is None
    assert build_action(types.Diagnostic(range=diag().range, message="x", source="other", data={}), info(), [workspace(tmp_path)], lambda u: None) is None


# ---- TC-13.9.3: the edit targets the dependency file, and only inside the workspace -------------------------------------------------------

def test_the_edit_targets_the_requirements_file_not_the_source_file(tmp_path):
    ws = workspace(tmp_path)
    ch = build_action(diag(), info(), [ws], lambda u: None).edit.document_changes[0]
    assert ch.text_document.uri.endswith("/requirements.txt") and not ch.text_document.uri.endswith("main.py")
    assert len(build_action(diag(), info(), [ws], lambda u: None).edit.document_changes) == 1


def test_a_path_that_leaves_the_workspace_is_never_edited(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text(REQ, encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    assert find_target([ws], "../outside.txt") is None
    assert build_action(diag(), info(target_path="../outside.txt"), [ws], lambda u: None) is None
    assert find_target([ws], "/etc/passwd") is None


# ---- through the real server process ------------------------------------------------------------------------------------------------------

def run_action(tmp_path: Path, fixes: dict, text: str = REQ, api_down: bool = False):
    f = finding()
    a = FakeApi([f], {"an_1": [cell()]}, None, fixes)
    c = LspClient()
    try:
        ws = workspace(tmp_path, text)
        c.initialize(ws, {"api": "http://127.0.0.1:1" if api_down else a.url, "consumer": "faultline-demo/bisect-svc"})
        uri = (ws / "app" / "main.py").as_uri()
        c.open(uri, (ws / "app" / "main.py").read_text(encoding="utf-8"))
        if api_down:
            c.wait(lambda m: m.get("method") == "faultline/status")
            d = {"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}}, "message": "x", "source": "faultline", "data": {"finding_id": "fnd_1", "role": "consumer"}}
        else:
            d = c.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri)["params"]["diagnostics"][0]
        r = c.request("textDocument/codeAction", {"textDocument": {"uri": uri}, "range": d["range"], "context": {"diagnostics": [d], "only": ["quickfix"]}})
        c.shutdown()
        return r["result"], ws
    finally:
        c.kill()
        a.close()


def test_the_server_returns_a_verified_fix_as_a_workspace_edit(tmp_path):
    result, ws = run_action(tmp_path, {"fnd_1": fix(target_sha256=sha256_of(REQ))})
    assert len(result) == 1 and result[0]["kind"] == "quickfix"
    a = result[0]
    ch = a["edit"]["documentChanges"][0]
    assert ch["textDocument"]["uri"].endswith("/requirements.txt") and ch["edits"][0]["newText"] == "werkzeug<3\n"
    assert ch["edits"][0]["range"]["start"] == {"line": 4, "character": 0}
    assert (ws / "requirements.txt").read_text(encoding="utf-8") == REQ, "the server never edits the file itself"


def test_the_server_returns_no_action_for_an_unverified_stale_or_missing_fix(tmp_path):
    assert run_action(tmp_path / "a", {"fnd_1": fix(label="SUGGESTED", target_sha256=sha256_of(REQ))})[0] == []
    assert run_action(tmp_path / "b", {"fnd_1": fix(target_sha256=sha256_of(REQ))}, text=REQ + "edited\n")[0] == []
    assert run_action(tmp_path / "c", {})[0] == [], "no stored fix: a non-import witness, or the fix was never verified"


def test_the_server_returns_no_action_when_the_api_is_down(tmp_path):
    assert run_action(tmp_path, {"fnd_1": fix(target_sha256=sha256_of(REQ))}, api_down=True)[0] == []
