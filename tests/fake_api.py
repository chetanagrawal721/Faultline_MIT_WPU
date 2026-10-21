"""A stand-in for the Faultline REST API, for language-server tests: the routes the server reads, with fixed answers."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def finding(**kw) -> dict:
    base = {"finding_id": "fnd_1", "analysis_id": "an_1", "cell_id": "cell_1", "mode": "LIVE", "verdict": "BREAK_WITNESSED",
            "headline": "acme-bisect breaks bisect-svc: ImportError in acme_bisect.web (3 of 3 fresh runs)", "artifact": "acme-bisect",
            "consumer": "faultline-demo/bisect-svc", "created_at": "2026-10-21T00:00:00Z", "witness_ids": []}
    return {**base, **kw}


def fix(**kw) -> dict:
    base = {"finding_id": "fnd_1", "label": "VERIFIED", "constraint": "werkzeug<3", "consumer": "faultline-demo/bisect-svc", "target_path": "requirements.txt",
            "target_sha256": None, "diff": "", "reason": "verified", "fresh_runs": 6}
    return {**base, **kw}


def cell(**kw) -> dict:
    base = {"id": "cell_1", "state": "ANALYZED", "consumers": ["faultline-demo/bisect-svc"], "imported_modules": ["acme_bisect.web", "acme_bisect.util"]}
    return {**base, **kw}


class FakeApi:
    def __init__(self, findings: list[dict], analyses: dict[str, list[dict]], imports: dict[str, list[dict]] | None = None,
                 fixes: dict[str, dict] | None = None, projects: list[dict] | None = None, project_analyses: dict[str, dict] | None = None,
                 job_script: list[str] | None = None, create_delay: float = 0.0):
        self.findings, self.analyses, self.imports, self.fixes = findings, analyses, imports or {}, fixes or {}
        self.projects, self.project_analyses = projects or [], project_analyses or {}
        self.job_script, self.create_delay = list(job_script or ['DONE']), create_delay
        self.jobs_by_key: dict[str, str] = {}
        self.created: list[str] = []                   # job ids, in the order they were created
        self.cancelled: list[str] = []                 # job ids a cancel was sent for
        self.polls: dict[str, int] = {}
        self.requests: list[str] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):                                             # noqa: N802
                outer.requests.append(self.path)
                if self.path == "/api/findings":
                    body = outer.findings
                elif self.path.startswith("/api/jobs/"):
                    jid = self.path.split("/")[3]
                    n = outer.polls.get(jid, 0)
                    outer.polls[jid] = n + 1
                    status = "CANCELLED" if jid in outer.cancelled else outer.job_script[min(n, len(outer.job_script) - 1)]
                    body = {"job_id": jid, "status": status, "result": {"ok": True} if status == "DONE" else None, "error": None}
                elif self.path == "/api/projects":
                    body = outer.projects
                elif self.path.startswith("/api/projects/") and self.path.endswith("/analysis"):
                    view = outer.project_analyses.get(self.path.split("/")[3])
                    if view is None:
                        self.send_response(404)
                        self.end_headers()
                        return
                    body = view
                elif self.path.startswith("/api/findings/") and self.path.endswith("/fix"):
                    fix = outer.fixes.get(self.path.split("/")[3])
                    if fix is None:
                        self.send_response(404)
                        self.end_headers()
                        return
                    body = fix
                elif self.path.startswith("/api/analyses/") and self.path.endswith("/imports"):
                    body = outer.imports.get(self.path.split("/")[3], [])
                elif self.path.startswith("/api/analyses/"):
                    body = {"id": self.path.rsplit("/", 1)[1], "cells": outer.analyses.get(self.path.rsplit("/", 1)[1], [])}
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):                                            # noqa: N802
                outer.requests.append("POST " + self.path)
                if self.path.startswith("/api/projects/") and "/analyze" in self.path:
                    import time
                    from urllib.parse import parse_qs, urlparse
                    time.sleep(outer.create_delay)
                    key = parse_qs(urlparse(self.path).query).get("key", [f"auto{len(outer.created)}"])[0]
                    if key not in outer.jobs_by_key:
                        outer.jobs_by_key[key] = f"job_{len(outer.created) + 1}"
                        outer.created.append(outer.jobs_by_key[key])
                    body = {"job_id": outer.jobs_by_key[key], "status": "QUEUED"}
                elif self.path.startswith("/api/jobs/") and self.path.endswith("/cancel"):
                    jid = self.path.split("/")[3]
                    if jid not in outer.cancelled:
                        outer.cancelled.append(jid)
                    body = {"job_id": jid, "status": "CANCELLED"}
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = json.dumps(body).encode()
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):                                    # noqa: D401
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
