"""The language server's view of Faultline: the REST API and nothing else. It never analyses anything and never runs analysed code."""
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


class ApiUnavailable(Exception):
    """The API did not answer. The server says so; it never shows a clean result because a backend is down."""


@dataclass(frozen=True)
class FindingInfo:
    finding_id: str
    analysis_id: str
    cell_id: str
    verdict: str
    headline: str
    artifact: str
    consumers: tuple[str, ...]
    modules: tuple[str, ...]                      # the producer modules the consumer imports (the entry modules of the cell)
    extra: dict = field(default_factory=dict, compare=False)


class Api:
    def __init__(self, base: str, timeout: float = 5.0):
        self.base, self.timeout = base.rstrip("/"), timeout

    def get(self, path: str):
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as r:                      # noqa: S310  (the URL is the configured Faultline API)
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError) as e:
            raise ApiUnavailable(f"{url}: {e}") from e

    def post(self, path: str, body: dict | None = None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body or {}).encode(), method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:                       # noqa: S310
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError) as e:
            raise ApiUnavailable(f"{self.base + path}: {e}") from e

    def findings_for(self, consumer: str) -> list[FindingInfo]:
        """The newest finding of each producer-consumer pair of this consumer repository (owner/name)."""
        views: dict[str, dict] = {}
        out: list[FindingInfo] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for f in self.get("/api/findings"):                                                  # newest first
            if f["analysis_id"] not in views:
                views[f["analysis_id"]] = self.get(f"/api/analyses/{urllib.parse.quote(f['analysis_id'])}")
            cell = next((c for c in views[f["analysis_id"]]["cells"] if c["id"] == f["cell_id"]), None)
            if cell is None or consumer not in cell["consumers"]:
                continue
            key = (f["artifact"], tuple(cell["consumers"]))
            if key in seen:
                continue
            seen.add(key)
            out.append(FindingInfo(f["finding_id"], f["analysis_id"], f["cell_id"], f["verdict"], f["headline"], f["artifact"], tuple(cell["consumers"]),
                                   tuple(cell["imported_modules"])))
        return out
