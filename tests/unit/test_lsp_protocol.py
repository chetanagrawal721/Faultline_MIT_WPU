"""M13.7: the stdio language server, tested as a real process through a real JSON-RPC client."""
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fake_api import FakeApi, cell, finding
from tests.lsp_client import ROOT, LspClient

SOURCE = "from acme_bisect.util import NAMES\nfrom acme_bisect.web import make_app\n\napp = make_app()\n"


@pytest.fixture
def api():
    a = FakeApi([finding()], {"an_1": [cell()]})
    yield a
    a.close()


@pytest.fixture
def client(api):
    c = LspClient()
    yield c
    c.kill()


def diagnostics_for(client: LspClient, uri: str) -> dict:
    return client.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri)["params"]


def init(client: LspClient, api, tmp_path: Path):
    return client.initialize(tmp_path, {"api": api.url, "consumer": "faultline-demo/bisect-svc"})


def test_tc_13_7_1_framing_survives_newlines_crlf_and_non_ascii_text(client, api, tmp_path):
    init(client, api, tmp_path)
    uri = (tmp_path / "app.py").as_uri()
    text = '# préparation: 日本語, emoji 😀\r\nx = "😀"; from acme_bisect.web import make_app\r\nfor i in range(1):\r\n    pass\r\n'
    client.open(uri, text)
    p = diagnostics_for(client, uri)
    assert len(p["diagnostics"]) == 1
    d = p["diagnostics"][0]
    # line 2 (index 1): the emoji in the string is two UTF-16 units, so the import starts at 'x = "😀"; ' = 10 + 1 characters
    assert d["range"]["start"]["line"] == 1 and d["range"]["start"]["character"] == len('x = "') + 2 + len('"; ')
    assert d["range"]["end"]["character"] == len('x = "') + 2 + len('"; from acme_bisect.web import make_app')
    assert d["message"].startswith("BREAK WITNESSED: ") and d["source"] == "faultline" and d["code"] == "fnd_1" and d["severity"] == 1
    assert client.shutdown() == 0
    assert client.leftover == b"" and bytes(client.raw).count(b"Content-Length: ") >= 3, "stdout held protocol frames only"
    assert b"\r\n\r\n" in client.raw and b'"\xc3\xa9' not in client.raw[:0]


def test_stdout_holds_only_frames_even_when_the_server_logs(client, api, tmp_path):
    init(client, api, tmp_path)
    client.open((tmp_path / "a.py").as_uri(), SOURCE)
    client.drain(1.0)
    client.shutdown()
    assert client.leftover == b""
    assert "initialize" in client.stderr_text(), "the log went to stderr"
    assert b"faultline.lsp" not in bytes(client.raw) and b"INFO" not in bytes(client.raw)


def test_tc_13_7_2_lifecycle_initialize_shutdown_exit(client, api, tmp_path):
    r = init(client, api, tmp_path)
    assert r["result"]["capabilities"]["textDocumentSync"] is not None and r["result"]["serverInfo"]["name"] == "faultline"
    assert client.shutdown() == 0


def test_exit_without_shutdown_is_an_error_exit(client, api, tmp_path):
    init(client, api, tmp_path)
    assert client.shutdown(clean=False) == 1


def test_tc_13_7_3_a_malformed_request_and_an_unsupported_method_do_not_stop_the_server(client, api, tmp_path):
    init(client, api, tmp_path)
    client.send(b"{ this is not json")
    r = client.request("faultline/doesNotExist", {})
    assert r["error"]["code"] == -32601
    r2 = client.request("textDocument/hover", {"textDocument": {"uri": (tmp_path / "x.py").as_uri()}, "position": {"line": 0, "character": 0}})
    assert "error" in r2 or r2.get("result") is None
    assert client.proc.poll() is None, "the server is still running"
    assert client.shutdown() == 0


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_tc_13_7_4_with_the_api_down_nothing_clean_is_published(tmp_path):
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": f"http://127.0.0.1:{free_port()}", "consumer": "faultline-demo/bisect-svc"})
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, SOURCE)
        st = c.wait(lambda m: m.get("method") == "faultline/status")
        assert st["params"]["state"] == "unavailable" and "127.0.0.1" in st["params"]["detail"]
        msg = c.wait(lambda m: m.get("method") == "window/showMessage")
        assert "not a clean result" in msg["params"]["message"]
        rest = c.drain(1.0)
        assert not [m for m in c.log + rest if m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri], "an empty list would read as clean"
        assert c.shutdown() == 0
    finally:
        c.kill()


def test_an_unknown_consumer_is_reported_not_guessed(tmp_path, api):
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": api.url})                      # no consumer and no git origin in the workspace
        c.open((tmp_path / "app.py").as_uri(), SOURCE)
        st = c.wait(lambda m: m.get("method") == "faultline/status")
        assert st["params"]["state"] == "unavailable" and "consumer repository is not known" in st["params"]["detail"]
        c.shutdown()
    finally:
        c.kill()


def test_the_consumer_is_read_from_the_git_origin(tmp_path, api):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text('[core]\n\trepositoryformatversion = 0\n[remote "origin"]\n\turl = https://github.com/faultline-demo/bisect-svc.git\n'
                                              '\tfetch = +refs/heads/*:refs/remotes/origin/*\n', encoding="utf-8")
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": api.url})
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, SOURCE)
        assert len(diagnostics_for(c, uri)["diagnostics"]) == 1
        c.shutdown()
    finally:
        c.kill()


def test_a_file_that_does_not_import_the_affected_module_gets_an_empty_list_not_an_invented_line(client, api, tmp_path):
    init(client, api, tmp_path)
    uri = (tmp_path / "other.py").as_uri()
    client.open(uri, "import os\nprint(os.name)\n")
    assert diagnostics_for(client, uri)["diagnostics"] == []          # the API answered: this file has no finding
    client.shutdown()


def test_a_finding_for_another_consumer_is_not_shown(tmp_path):
    a = FakeApi([finding()], {"an_1": [cell(consumers=["someone/else"])]})
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": a.url, "consumer": "faultline-demo/bisect-svc"})
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, SOURCE)
        assert diagnostics_for(c, uri)["diagnostics"] == []
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_closing_a_document_clears_its_diagnostics(client, api, tmp_path):
    init(client, api, tmp_path)
    uri = (tmp_path / "app.py").as_uri()
    client.open(uri, SOURCE)
    assert diagnostics_for(client, uri)["diagnostics"]
    client.notify("textDocument/didClose", {"textDocument": {"uri": uri}})
    assert client.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri and m["params"]["diagnostics"] == [])


def test_tc_13_7_5_the_pinned_libraries_implement_lsp_3_17():
    from importlib.metadata import version

    from lsprotocol import types
    assert version("pygls") == "2.1.1" and version("lsprotocol") == "2025.0.0"
    for name in ("TEXT_DOCUMENT_DIAGNOSTIC", "WORKSPACE_DIAGNOSTIC", "INLAY_HINT_RESOLVE", "TEXT_DOCUMENT_INLINE_VALUE", "TYPE_HIERARCHY_SUBTYPES"):
        assert hasattr(types, name), f"{name} is an LSP 3.17 method and is missing"
    out = subprocess.run([sys.executable, "scripts/check_pins.py"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "pins ok" in out.stdout
    toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pygls==2.1.1"' in toml and '"lsprotocol==2025.0.0"' in toml
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "pygls"' in lock and 'name = "lsprotocol"' in lock and "sha256:" in lock
