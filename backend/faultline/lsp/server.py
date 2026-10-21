"""The Faultline language server (LSP 3.17 over stdio, pygls).

A thin client of the REST API: it reads findings, publishes them as diagnostics on the lines of the consumer's source files, and holds no
analysis logic. Nothing is ever executed. stdout carries protocol frames only (pygls writes to the binary stdout buffer); logs go to stderr.

Initialization options: {"api": "http://127.0.0.1:8000", "consumer": "owner/name"} ("repository" is the same). Without it the repository is read from the
workspace's `.git/config` (the origin URL). The repository may be a consumer of a pair (the diagnostic is on its import line) or the producer
(the diagnostic is on a call site checked by O-bind).
"""
import asyncio
import logging
import os
import re
from pathlib import Path

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .client_api import Api, ApiUnavailable, FindingInfo
from .code_actions import build_action, fix_from
from .diagnostics import to_diagnostics
from .locations import path_of, relative_path
from .severity import UnknownVerdict

log = logging.getLogger("faultline.lsp")
DEFAULT_API = "http://127.0.0.1:8000"


def repository_of(root: Path) -> str | None:
    """owner/name from the origin URL in `.git/config`, or None."""
    cfg = root / ".git" / "config"
    if not cfg.is_file():
        return None
    m = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', cfg.read_text(encoding="utf-8", errors="replace"), re.S)
    if not m:
        return None
    s = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", m.group(1).strip())
    return f"{s.group(1)}/{s.group(2)}" if s else None


class FaultlineServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("faultline", "0.1.0")
        self.api: Api = Api(os.environ.get("FAULTLINE_API", DEFAULT_API))
        self.consumer: str | None = None            # the workspace repository, owner/name
        self.roots: list[Path] = []
        self.findings: list[FindingInfo] | None = None
        self.available: bool | None = None
        self.shut_down = False                       # the exit code is 0 only after a shutdown request (LSP 3.17, lifecycle)

    def status(self, state: str, detail: str = "") -> None:
        if state != self.available:
            self.available = state == "ready"
            self.protocol.notify("faultline/status", {"state": state, "detail": detail})
            if state == "unavailable":
                self.window_show_message(types.ShowMessageParams(type=types.MessageType.Warning,
                                                                 message=f"Faultline: the API is not reachable ({detail}). No result is shown, which is not a clean result."))

    async def refresh_findings(self) -> list[FindingInfo] | None:
        """Read the findings of this consumer. None when the API cannot be reached (and the state says so)."""
        if not self.consumer:
            self.status("unavailable", "the consumer repository is not known: set initializationOptions.consumer or give the workspace a git origin")
            return None
        try:
            self.findings = await asyncio.to_thread(self.api.findings_for, self.consumer)
        except ApiUnavailable as e:
            log.warning("api unavailable: %s", e)
            self.status("unavailable", str(e))
            return None
        self.status("ready")
        return self.findings

    async def publish(self, uri: str, *, refresh: bool) -> None:
        doc = self.workspace.get_text_document(uri)
        if not doc.path or not doc.path.endswith(".py"):
            return
        rel = relative_path(uri, self.roots)
        if rel is None:                                                      # a file outside the workspace is not part of the analysed repository
            return
        found = (await self.refresh_findings()) if refresh or self.findings is None else self.findings
        if found is None:                                                    # the API is down: publish nothing, never an empty list
            return
        try:
            diagnostics = to_diagnostics(doc.source, rel, found)
        except UnknownVerdict as e:
            log.error("%s", e)
            self.status("unavailable", str(e))
            return
        self.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics, version=doc.version))


def build_server() -> FaultlineServer:
    server = FaultlineServer()

    @server.feature(types.INITIALIZE)
    def on_initialize(ls: FaultlineServer, params: types.InitializeParams) -> None:
        opts = params.initialization_options or {}
        if opts.get("api"):
            ls.api = Api(str(opts["api"]))
        ls.consumer = opts.get("repository") or opts.get("consumer")
        ls.roots = [path_of(r) for r in ([w.uri for w in (params.workspace_folders or [])] or ([params.root_uri] if params.root_uri else []))]
        if not ls.consumer:
            for r in ls.roots:
                ls.consumer = repository_of(r)
                if ls.consumer:
                    break
        log.info("initialize: api=%s consumer=%s", ls.api.base, ls.consumer)

    @server.feature(types.SHUTDOWN)
    def on_shutdown(ls: FaultlineServer, params: object = None) -> None:
        ls.shut_down = True

    @server.feature(types.TEXT_DOCUMENT_CODE_ACTION, types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]))
    async def on_code_action(ls: FaultlineServer, params: types.CodeActionParams) -> list[types.CodeAction]:
        """A verified fix for each Faultline diagnostic in the range; nothing when the fix is unverified, stale, missing or not for this repository."""
        def open_text(uri: str):
            if uri in ls.workspace.text_documents:
                d = ls.workspace.text_documents[uri]
                return d.source, d.version
            return None
        out: list[types.CodeAction] = []
        for diag in params.context.diagnostics:
            if diag.source != "faultline" or not isinstance(diag.data, dict) or not diag.data.get("finding_id"):
                continue
            try:
                raw = await asyncio.to_thread(ls.api.get_optional, f"/api/findings/{diag.data['finding_id']}/fix")
            except ApiUnavailable as e:
                log.warning("api unavailable while looking for a fix: %s", e)
                ls.status("unavailable", str(e))
                return []
            action = build_action(diag, fix_from(raw) if raw else None, ls.roots, open_text)
            if action is not None:
                out.append(action)
        return out

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    async def on_open(ls: FaultlineServer, params: types.DidOpenTextDocumentParams) -> None:
        await ls.publish(params.text_document.uri, refresh=True)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    async def on_change(ls: FaultlineServer, params: types.DidChangeTextDocumentParams) -> None:
        await ls.publish(params.text_document.uri, refresh=False)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    async def on_save(ls: FaultlineServer, params: types.DidSaveTextDocumentParams) -> None:
        await ls.publish(params.text_document.uri, refresh=True)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def on_close(ls: FaultlineServer, params: types.DidCloseTextDocumentParams) -> None:
        ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[]))

    return server
