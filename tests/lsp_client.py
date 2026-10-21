"""A small LSP client for tests: it starts the real server process and speaks JSON-RPC over its stdio with Content-Length framing.

Everything is read as bytes, so a stray line on stdout, a wrong Content-Length or a changed line ending shows up as a failure here.
"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LspClient:
    def __init__(self, env: dict | None = None):
        self.stderr = tempfile.TemporaryFile()
        e = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), **(env or {})}
        self.proc = subprocess.Popen([sys.executable, "-m", "faultline.lsp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, env=e, cwd=str(ROOT))
        self.messages: queue.Queue = queue.Queue()
        self.raw = bytearray()                   # every byte the server wrote to stdout
        self.leftover = b""                      # bytes that were not part of a well-formed frame
        self._id = 0
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.log: list[dict] = []

    # ---- framing ---------------------------------------------------------------------------------------------------------------------

    def _read(self) -> None:
        out = self.proc.stdout
        while True:
            header = b""
            while not header.endswith(b"\r\n\r\n"):
                ch = out.read(1)
                if not ch:
                    return
                header += ch
                self.raw += ch
                if len(header) > 4096:
                    self.leftover = header
                    return
            length = None
            for line in header.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
            if length is None:
                self.leftover = header
                return
            body = b""
            while len(body) < length:
                chunk = out.read(length - len(body))
                if not chunk:
                    return
                body += chunk
                self.raw += chunk
            self.messages.put(json.loads(body.decode("utf-8")))

    @staticmethod
    def frame(obj: dict | bytes) -> bytes:
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        return b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body

    def send(self, obj: dict | bytes) -> None:
        self.proc.stdin.write(self.frame(obj))
        self.proc.stdin.flush()

    # ---- protocol --------------------------------------------------------------------------------------------------------------------

    def request(self, method: str, params: dict | None = None, timeout: float = 15.0) -> dict:
        self._id += 1
        rid = self._id
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return self.wait(lambda m: m.get("id") == rid and ("result" in m or "error" in m), timeout)

    def send_request(self, method: str, params: dict | None = None) -> int:
        """Send a request and return its id without waiting for the answer (for cancelling it)."""
        self._id += 1
        self.send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        return self._id

    def cancel(self, rid: int) -> None:
        self.notify("$/cancelRequest", {"id": rid})

    def response(self, rid: int, timeout: float = 20.0) -> dict:
        return self.wait(lambda m: m.get("id") == rid and ("result" in m or "error" in m), timeout)

    def notify(self, method: str, params: dict | None = None) -> None:
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def wait(self, pred, timeout: float = 15.0) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = self.messages.get(timeout=0.1)
            except queue.Empty:
                continue
            self.log.append(m)
            if pred(m):
                return m
        raise AssertionError(f"no matching message within {timeout} s; saw {json.dumps(self.log[-5:])[:600]}; stderr: {self.stderr_text()[-600:]}")

    def drain(self, seconds: float) -> list[dict]:
        end = time.time() + seconds
        got = []
        while time.time() < end:
            try:
                got.append(self.messages.get(timeout=0.1))
            except queue.Empty:
                pass
        self.log += got
        return got

    def initialize(self, root: Path | None = None, options: dict | None = None) -> dict:
        params = {"processId": os.getpid(), "rootUri": root.as_uri() if root else None, "capabilities": {},
                  "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}] if root else None, "initializationOptions": options or {}}
        r = self.request("initialize", params)
        self.notify("initialized", {})
        return r

    def open(self, uri: str, text: str, version: int = 1) -> None:
        self.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "python", "version": version, "text": text}})

    def stderr_text(self) -> str:
        self.stderr.seek(0)
        return self.stderr.read().decode("utf-8", "replace")

    def shutdown(self, clean: bool = True) -> int:
        if clean:
            self.request("shutdown")
        self.notify("exit")
        try:
            return self.proc.wait(timeout=15)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()

    def kill(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
