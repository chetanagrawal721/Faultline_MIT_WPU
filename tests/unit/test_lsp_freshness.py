"""M13.8 (TC-13.8.4): a changed file is marked stale and moved to the right line, a reopened file does not collect duplicates, a file outside the workspace
gets nothing, and a producer workspace shows the call site that O-bind checked. Each test drives the real server process."""
from tests.fake_api import FakeApi, cell, finding
from tests.lsp_client import LspClient
from tests.unit.test_lsp_protocol import (  # noqa: F401  (fixtures and helpers shared with the protocol tests)
    SOURCE,
    api,
    client,
    diagnostics_for,
    init,
)

ANALYSED = "import os\nfrom acme_bisect.web import make_app\n"
EDITED = "# a new comment\n# another\nimport os\nimport sys\nfrom acme_bisect.web import make_app\n"


def stored_sites(text: str, file: str = "app.py", line: int = 2) -> dict:
    from faultline.lsp.locations import sha256_of
    return {"an_1": [{"cell_id": "cell_1", "consumer": "faultline-demo/bisect-svc", "commit": "a" * 40,
                      "sites": [{"module": "acme_bisect.web", "file": file, "line": line, "sha256": sha256_of(text)}]}]}


def published(c: LspClient, uri: str, version: int) -> list[dict]:
    return c.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri and m["params"].get("version") == version)["params"]["diagnostics"]


def test_an_edit_marks_the_diagnostic_stale_and_moves_it_to_the_right_line(tmp_path):
    a = FakeApi([finding()], {"an_1": [cell()]}, stored_sites(ANALYSED))
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": a.url, "consumer": "faultline-demo/bisect-svc"})
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, ANALYSED)
        first = published(c, uri, 1)
        assert len(first) == 1 and first[0]["range"]["start"]["line"] == 1 and first[0]["data"]["stale"] is False and "changed since" not in first[0]["message"]
        c.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": EDITED}]})
        second = published(c, uri, 2)
        assert len(second) == 1 and second[0]["range"]["start"]["line"] == 4 and second[0]["data"]["stale"] is True
        assert second[0]["message"].endswith("(this file has changed since the analysis)")
        c.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": 3}, "contentChanges": [{"text": ANALYSED}]})
        third = published(c, uri, 3)
        assert len(third) == 1 and third[0]["data"]["stale"] is False and third[0]["range"]["start"]["line"] == 1, "back to the analysed text: fresh again"
        c.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": 4}, "contentChanges": [{"text": "import os\n"}]})
        assert published(c, uri, 4) == [], "the import was removed: the finding has no line in this file"
        c.shutdown()
    finally:
        c.kill()
        a.close()


def test_reopening_a_file_does_not_collect_duplicates(client, api, tmp_path):  # noqa: F811
    init(client, api, tmp_path)
    uri = (tmp_path / "app.py").as_uri()
    for version in (1, 2, 3):
        client.open(uri, SOURCE, version)
        assert len(published(client, uri, version)) == 1
        client.notify("textDocument/didClose", {"textDocument": {"uri": uri}})
        client.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri and m["params"]["diagnostics"] == [])


def test_a_file_outside_the_workspace_gets_nothing(client, api, tmp_path):  # noqa: F811
    ws = tmp_path / "ws"
    ws.mkdir()
    init(client, api, ws)
    uri = (tmp_path / "outside.py").as_uri()
    client.open(uri, SOURCE)
    rest = client.drain(1.5)
    assert not [m for m in rest if m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uri]


def test_a_producer_workspace_shows_the_checked_call_site(tmp_path):
    f = finding(artifact="acme-http", headline="the call shape changed")
    c1 = cell(consumers=["faultline-demo/orders-svc"], imported_modules=["acme_http.retry"],
              oracle_plan=[{"oracle": "o_bind", "status": "RAN", "entries": ["bind:src/acme_http/retry.py:3:4"]}])
    a = FakeApi([f], {"an_1": [c1]})
    c = LspClient()
    try:
        (tmp_path / "src" / "acme_http").mkdir(parents=True)
        c.initialize(tmp_path, {"api": a.url, "repository": "faultline-demo/acme-http"})
        text = "import urllib3\nfrom urllib3.util.retry import Retry\nr = Retry(method_whitelist=[1])\n"
        uri = (tmp_path / "src" / "acme_http" / "retry.py").as_uri()
        c.open(uri, text)
        d = diagnostics_for(c, uri)["diagnostics"]
        assert len(d) == 1 and d[0]["range"]["start"] == {"line": 2, "character": 4} and d[0]["data"]["role"] == "producer" and d[0]["severity"] == 1
        c.shutdown()
    finally:
        c.kill()
        a.close()


def project_with(repo: str, view: dict) -> dict:
    owner, name = repo.split("/")
    return {"id": "ap_1", "repositories": [{"owner": owner, "name": name}], "_view": view}


def test_only_the_newest_analysis_counts_so_a_fixed_pair_stops_showing(tmp_path):
    old_finding = finding(finding_id="fnd_old", analysis_id="an_1", cell_id="cell_1")
    newest = {"id": "an_2", "started_at": "2026-10-22T00:10:00Z", "cells": []}                      # after the fix the pair has no drift: no finding
    older = {"id": "an_1", "started_at": "2026-10-22T00:00:00Z", "cells": [cell()]}
    a = FakeApi([old_finding], {"an_1": [cell()]}, None, None, [{"id": "ap_1", "repositories": [{"owner": "faultline-demo", "name": "bisect-svc"}]}], {"ap_1": newest})
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": a.url, "consumer": "faultline-demo/bisect-svc"})
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, SOURCE)
        assert published(c, uri, 1) == [], "the finding belongs to an older analysis of the same repository: it is not shown"
        c.shutdown()
        assert older["id"] == "an_1"
    finally:
        c.kill()
        a.close()


def test_the_newest_analysis_is_used_when_it_has_a_finding(tmp_path):
    f_new = finding(finding_id="fnd_new", analysis_id="an_2", cell_id="cell_2", headline="the newer result")
    f_old = finding(finding_id="fnd_old", analysis_id="an_1", cell_id="cell_1", headline="the older result")
    newest = {"id": "an_2", "started_at": "2026-10-22T00:10:00Z", "cells": [cell(id="cell_2")]}
    a = FakeApi([f_new, f_old], {"an_1": [cell()], "an_2": [cell(id="cell_2")]}, None, None,
                [{"id": "ap_1", "repositories": [{"owner": "faultline-demo", "name": "bisect-svc"}]}], {"ap_1": newest})
    c = LspClient()
    try:
        c.initialize(tmp_path, {"api": a.url, "consumer": "faultline-demo/bisect-svc"})
        uri = (tmp_path / "app.py").as_uri()
        c.open(uri, SOURCE)
        d = published(c, uri, 1)
        assert len(d) == 1 and d[0]["code"] == "fnd_new" and "the newer result" in d[0]["message"]
        c.shutdown()
    finally:
        c.kill()
        a.close()
