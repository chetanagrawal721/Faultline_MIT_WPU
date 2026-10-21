"""A stand-in for the Faultline REST API, for language-server tests: the routes the server reads, with fixed answers."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def finding(**kw) -> dict:
    base = {"finding_id": "fnd_1", "analysis_id": "an_1", "cell_id": "cell_1", "mode": "LIVE", "verdict": "BREAK_WITNESSED",
            "headline": "acme-bisect breaks bisect-svc: ImportError in acme_bisect.web (3 of 3 fresh runs)", "artifact": "acme-bisect",
            "consumer": "faultline-demo/bisect-svc", "created_at": "2026-10-21T00:00:00Z", "witness_ids": []}
    return {**base, **kw}


def cell(**kw) -> dict:
    base = {"id": "cell_1", "state": "ANALYZED", "consumers": ["faultline-demo/bisect-svc"], "imported_modules": ["acme_bisect.web", "acme_bisect.util"]}
    return {**base, **kw}


class FakeApi:
    def __init__(self, findings: list[dict], analyses: dict[str, list[dict]]):
        self.findings, self.analyses = findings, analyses
        self.requests: list[str] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):                                             # noqa: N802
                outer.requests.append(self.path)
                if self.path == "/api/findings":
                    body = outer.findings
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
