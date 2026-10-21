"""M13.8 (TC-13.8.5): the language server on real analyses. Three consumers of one project are analysed on real sandboxes; the API serves the database;
the server process is started in each consumer's own folder and must show the verdict on the stored import line with the severity of the mapping.

The live pipeline produces BREAK WITNESSED, SILENT DIVERGENCE WITNESSED and INCONCLUSIVE from execution, and EXPOSED and POTENTIAL from static evidence where
execution settled nothing (analysis/static.py), so all four levels appear: Error, Warning, Information and Hint. billing-svc/H used to be INCONCLUSIVE; its
artifact (acme-models) does reference pydantic.BaseSettings, which pydantic 2 removed, so it is now EXPOSED (a warning). The Hint comes from a pair that no
static reading can add to (drivers-svc), and the Information from one whose reference to pydantic is only dynamic (plugins-svc).
"""
import json
import shutil
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from faultline.analysis.live import run_live_analysis
from faultline.api.main import create_app
from faultline.core.config import Settings
from faultline.core.enums import Mode
from faultline.lsp.locations import sha256_of
from tests.liveenv import ingest_all
from tests.livefix import fixture_repo
from tests.lsp_client import ROOT, LspClient

pytestmark = pytest.mark.docker

CASES = {          # remote tag -> (repository slug, fixture directory, expected severity code, expected verdict words)
    "models": ("faultline-demo/acme-models", "acme-models", None, None),
    "notify": ("faultline-demo/notify-svc", "notify-svc/D", 1, "BREAK WITNESSED"),
    "billing_h": ("faultline-demo/billing-svc-h", "billing-svc/H", 2, "EXPOSED"),
    "plugins_p": ("faultline-demo/acme-plugins", "acme-plugins", None, None),
    "plugins": ("faultline-demo/plugins-svc", "plugins-svc", 3, "POTENTIAL"),
    "drivers_p": ("faultline-demo/acme-drivers", "acme-drivers", None, None),
    "drivers": ("faultline-demo/drivers-svc", "drivers-svc", 4, "INCONCLUSIVE"),
    "contracts": ("faultline-demo/acme-contracts", "acme-contracts", None, None),
    "billing_e": ("faultline-demo/billing-svc-e", "billing-svc/E", 2, "SILENT DIVERGENCE WITNESSED"),
}


@pytest.fixture(scope="module")
def served(daemon, image, tmp_path_factory):
    from faultline.sandbox.client import SandboxClient
    from faultline.storage.db import connect
    from faultline.storage.migrate import migrate
    from tests.conftest import TOKEN
    d = tmp_path_factory.mktemp("lsp_live")
    conn = connect(d / "lsp.db")
    migrate(conn)
    sbx = SandboxClient(port=daemon.port, token=TOKEN, timeout=900)
    apid, _ = ingest_all(conn, sbx, image, daemon.store, {f"rm_lsp_{k}": (slug, fixture_repo(directory)) for k, (slug, directory, _s, _v) in CASES.items()})
    res = run_live_analysis(conn, sbx, image, daemon.store, apid)
    settings = Settings(db_path=d / "lsp.db", store_path=d / "api-store", mode=Mode.LIVE, admin_token=None, lease_seconds=30, heartbeat_seconds=10, poll_seconds=0.5)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started
    yield {"conn": conn, "res": res, "url": f"http://127.0.0.1:{port}"}
    server.should_exit = True
    t.join(timeout=10)
    conn.close()
    keep = ROOT / "var" / "lsp_live"                           # kept (var/ is not committed) so a real VS Code session can be run against these analyses
    shutil.rmtree(keep, ignore_errors=True)
    shutil.copytree(d, keep, ignore=shutil.ignore_patterns("api-store"))


def diagnostics_in(folder: Path, url: str, repo: str, rel: str) -> dict:
    c = LspClient()
    try:
        c.initialize(folder, {"api": url, "repository": repo})
        f = folder / rel
        c.open(f.as_uri(), f.read_text(encoding="utf-8"))
        return c.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == f.as_uri())["params"]
    finally:
        c.shutdown()
        c.kill()


def test_tc_13_8_5_four_live_severities_on_the_stored_import_lines(served):
    results = {}
    for tag, (slug, directory, severity, words) in CASES.items():
        if severity is None:
            continue
        folder = ROOT / "fixtures" / "repos" / directory
        p = diagnostics_in(folder, served["url"], slug, "app/main.py")
        assert len(p["diagnostics"]) == 1, (tag, p)
        d = p["diagnostics"][0]
        text = (folder / "app" / "main.py").read_text(encoding="utf-8").splitlines()
        assert d["severity"] == severity and d["message"].startswith(words + ": "), (tag, d["severity"], d["message"][:80])
        assert d["range"]["start"]["line"] == 1 and text[1].startswith("import "), "the import line of the consumer's file"
        assert d["data"]["stale"] is False and d["data"]["location"] == "the import site stored with the analysis" and d["source"] == "faultline"
        results[tag] = {"repository": slug, "file": f"{directory}/app/main.py", "line": d["range"]["start"]["line"] + 1, "severity": {1: "Error", 2: "Warning", 3: "Information", 4: "Hint"}[d["severity"]],
                        "words": words, "code": d["code"]}
    assert sorted(r["severity"] for r in results.values()) == ["Error", "Hint", "Information", "Warning", "Warning"]
    print("\nLIVE_SEVERITIES " + json.dumps(results, sort_keys=True))


def test_the_stored_import_sites_match_the_files_that_were_analysed(served):
    import urllib.request
    aid = served["res"].analysis_id
    with urllib.request.urlopen(f"{served['url']}/api/analyses/{aid}/imports") as r:
        imports = json.loads(r.read())
    assert imports and all(i["commit"] and i["sites"] for i in imports)
    by_repo = {i["consumer"]: i for i in imports}
    for _tag, (slug, directory, severity, _w) in CASES.items():
        if severity is None:
            continue
        site = by_repo[slug]["sites"][0]
        file = ROOT / "fixtures" / "repos" / directory / site["file"]
        assert site["sha256"] == sha256_of(file.read_text(encoding="utf-8")) and site["line"] == 2, (slug, site)


def test_static_findings_hold_no_witness_and_authorise_no_fix(served):
    """EXPOSED and POTENTIAL rest on source and API changes alone: no witness row, no witness evidence, no stored fix, and the stored evidence names what they rest on."""
    import urllib.error
    import urllib.request
    conn = served["conn"]
    rows = conn.execute("SELECT id, verdict, scope_json, analysis_id FROM finding WHERE verdict IN ('EXPOSED','POTENTIAL')").fetchall()
    assert {r["verdict"] for r in rows} == {"EXPOSED", "POTENTIAL"}, "both static verdicts occur in the live analysis"
    for r in rows:
        assert conn.execute("SELECT COUNT(*) FROM witness WHERE analysis_id=? AND cell_id=(SELECT cell_id FROM finding WHERE id=?)", (r["analysis_id"], r["id"])).fetchone()[0] == 0
        kinds = {k["evidence_kind"] for k in conn.execute("SELECT evidence_kind FROM finding_evidence WHERE finding_id=?", (r["id"],))}
        assert "WITNESS" not in kinds and ("EXPOSURE" in kinds or "API_CHANGE" in kinds), kinds
        scope = json.loads(r["scope_json"])
        assert scope["static_rule"] == "static-exposure/1" and scope["static"]["available"] is True
        try:
            urllib.request.urlopen(f"{served['url']}/api/findings/{r['id']}/fix")
            raise AssertionError("a static finding must not have a fix")
        except urllib.error.HTTPError as e:
            assert e.code == 404
