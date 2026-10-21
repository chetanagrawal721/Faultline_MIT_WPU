"""The language server's view of Faultline: the REST API and nothing else. It never analyses anything and never runs analysed code."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


class ApiUnavailable(Exception):
    """The API did not answer. The server says so; it never shows a clean result because a backend is down."""


@dataclass(frozen=True)
class ImportSiteInfo:
    module: str
    file: str                                     # relative to the consumer repository root
    line: int                                     # one-based
    sha256: str | None                            # the file's hash at the analysed commit


@dataclass(frozen=True)
class BindSiteInfo:
    file: str                                     # relative to the producer repository root
    line: int                                     # one-based
    col: int                                      # zero-based, UTF-8 bytes (as the parser reports it)


@dataclass(frozen=True)
class FindingInfo:
    finding_id: str
    analysis_id: str
    cell_id: str
    verdict: str
    headline: str
    artifact: str
    role: str                                     # "consumer": the workspace repository is a consumer of the pair; "producer": it is the artifact
    consumers: tuple[str, ...]
    modules: tuple[str, ...]                      # the producer modules the consumer imports (the entry modules of the cell)
    sites: tuple[ImportSiteInfo, ...] = ()        # where the consumer imports them, from the analysis
    bind_sites: tuple[BindSiteInfo, ...] = ()     # call sites in the producer that were checked (O-bind)
    extra: dict = field(default_factory=dict, compare=False)


_BIND = re.compile(r"^bind:(.+):(\d+):(\d+)$")


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

    def get_optional(self, path: str):
        """Like get, but a 404 is an answer (None), not a failure of the API."""
        try:
            return self.get(path)
        except ApiUnavailable as e:
            if isinstance(e.__cause__, urllib.error.HTTPError) and e.__cause__.code == 404:
                return None
            raise

    def post(self, path: str, body: dict | None = None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body or {}).encode(), method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:                       # noqa: S310
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError) as e:
            raise ApiUnavailable(f"{self.base + path}: {e}") from e

    def latest_analysis(self, repo: str) -> dict | None:
        """The most recent analysis, over every project that contains this repository (owner/name), or None when no project does."""
        best = None
        try:
            projects = self.get("/api/projects")
        except ApiUnavailable:
            raise
        for p in projects if isinstance(projects, list) else []:
            if not any(f"{r['owner']}/{r['name']}" == repo for r in p.get("repositories", [])):
                continue
            view = self.get_optional(f"/api/projects/{urllib.parse.quote(p['id'])}/analysis")
            if view is not None and (best is None or (view.get("started_at") or "") > (best.get("started_at") or "")):
                best = view
        return best

    def findings_for(self, repo: str) -> list[FindingInfo]:
        """What the newest analysis says about this repository (owner/name), as a consumer of a pair or as the producer.

        Only the newest analysis counts: after a fix the pair no longer breaks, and an older finding must not keep showing. When no project of the API
        contains the repository, the newest finding of each pair that names it is used instead."""
        name = repo.rsplit("/", 1)[-1]
        summaries = {f["finding_id"]: f for f in self.get("/api/findings")}
        latest = self.latest_analysis(repo)
        views: dict[str, dict] = {}
        if latest is not None:
            views[latest["id"]] = latest
            wanted = [(f, latest["id"]) for f in summaries.values() if f["analysis_id"] == latest["id"]]
        else:
            wanted = [(f, f["analysis_id"]) for f in summaries.values()]                          # newest first
        imports: dict[str, list[dict]] = {}
        out: list[FindingInfo] = []
        seen: set[tuple[str, tuple[str, ...], str]] = set()
        for f, aid in wanted:
            if aid not in views:
                views[aid] = self.get(f"/api/analyses/{urllib.parse.quote(aid)}")
            if aid not in imports:
                try:
                    imports[aid] = self.get(f"/api/analyses/{urllib.parse.quote(aid)}/imports")
                except ApiUnavailable:
                    imports[aid] = []                                                         # an older API without the route: no stored sites
            cell = next((c for c in views[aid]["cells"] if c["id"] == f["cell_id"]), None)
            if cell is None:
                continue
            role = "consumer" if repo in cell["consumers"] else "producer" if f["artifact"] == name else None
            if role is None:
                continue
            key = (f["artifact"], tuple(cell["consumers"]), role)
            if key in seen:
                continue
            seen.add(key)
            sites = tuple(ImportSiteInfo(s["module"], s["file"], s["line"], s.get("sha256")) for i in imports[aid] if i["cell_id"] == cell["id"] and i["consumer"] == repo
                          for s in i["sites"])
            binds = []
            for step in cell.get("oracle_plan", []):
                if step.get("oracle") == "o_bind" and step.get("status") == "RAN":
                    for e in step.get("entries", []):
                        m = _BIND.match(e)
                        if m:
                            binds.append(BindSiteInfo(m.group(1), int(m.group(2)), int(m.group(3))))
            out.append(FindingInfo(f["finding_id"], aid, f["cell_id"], f["verdict"], f["headline"], f["artifact"], role, tuple(cell["consumers"]),
                                   tuple(cell["imported_modules"]), sites, tuple(binds)))
        return out
