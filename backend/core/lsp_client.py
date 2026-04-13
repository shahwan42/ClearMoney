"""basedpyright language server client for AI-assisted code exploration.

This module provides a singleton LSP client that communicates with basedpyright-langserver
over stdio using the sans-IO `lsp` package. It enables go-to-definition, hover,
find-references, and diagnostics without requiring an editor plugin.

Usage:
    from core.lsp_client import basedpyright

    loc = basedpyright.goto_definition("core/models.py", line=10, col=0)
    hover = basedpyright.hover("core/models.py", line=10, col=0)
    refs = basedpyright.find_references("core/models.py", line=10, col=0)
    diags = basedpyright.diagnostics("core/models.py")
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from lsp import NEED_DATA, Connection, DataReceived, MessageEnd

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENV_BIN = os.path.join(_BASE_DIR, ".venv", "bin")
LANGSERVER_BIN = os.path.join(_VENV_BIN, "basedpyright-langserver")


@dataclass
class Location:
    """Represents a location in a source file."""

    file_path: str
    line: int
    character: int

    def __repr__(self) -> str:
        return f"Location(file_path={self.file_path!r}, line={self.line}, character={self.character})"


@dataclass
class HoverInfo:
    """Represents hover information from the language server."""

    contents: str
    file_path: str
    line: int
    character: int

    def __repr__(self) -> str:
        return f"HoverInfo(contents={self.contents[:50]!r}..., file_path={self.file_path!r}, line={self.line}, character={self.character})"


@dataclass
class Diagnostic:
    """Represents a diagnostic (error/warning/info) from the language server."""

    message: str
    file_path: str
    line: int
    character: int
    severity: str

    def __repr__(self) -> str:
        return f"Diagnostic(severity={self.severity!r}, message={self.message[:30]!r}..., file_path={self.file_path!r}, line={self.line}, character={self.character})"


class LSPError(Exception):
    """Raised when LSP communication fails."""


class BasedPyrightClient:
    """Singleton LSP client for basedpyright-langserver.

    Communicates with the language server over stdio using the sans-IO `lsp` package.
    Thread-safe for concurrent requests from multiple agent threads.
    """

    _instance: BasedPyrightClient | None = None
    _lock = threading.Lock()

    def __new__(cls) -> BasedPyrightClient:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._proc: subprocess.Popen[bytes] | None = None
        self._conn: Connection | None = None
        self._request_id = 0
        self._initialized = True
        self._initialized_version: bool = False
        self._rw_lock = threading.RLock()

    def _get_proc(self) -> subprocess.Popen[bytes]:
        """Lazily start the langserver subprocess."""
        if self._proc is None:
            with self._rw_lock:
                if self._proc is None:
                    if not os.path.exists(LANGSERVER_BIN):
                        raise LSPError(
                            f"basedpyright-langserver not found at {LANGSERVER_BIN}. "
                            "Install basedpyright: uv pip install basedpyright"
                        )
                    self._proc = subprocess.Popen(
                        [LANGSERVER_BIN, "--stdio"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self._conn = Connection("client")
                    self._send_initialize()
                    self._initialized_version = True
        return self._proc

    def _send_initialize(self) -> None:
        """Send LSP initialize handshake and wait for response."""
        if self._conn is None or self._proc is None:
            raise LSPError("Connection not initialized")

        process_id = os.getpid()
        root_uri = f"file://{_BASE_DIR}"

        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "processId": process_id,
                "rootUri": root_uri,
                "capabilities": {},
                "workspaceFolders": [{"uri": root_uri, "name": "backend"}],
            },
        }

        data = self._conn.send_json(init_request)
        self._proc.stdin.write(data)  # type: ignore[union-attr]
        self._proc.stdin.flush()  # type: ignore[union-attr]
        self._read_response("initialize")

        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {},
        }
        data = self._conn.send_json(initialized_notification)
        self._proc.stdin.write(data)  # type: ignore[union-attr]
        self._proc.stdin.flush()  # type: ignore[union-attr]

    def _next_id(self) -> int:
        """Generate next request ID."""
        with self._rw_lock:
            self._request_id += 1
            return self._request_id

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a request and wait for response."""
        proc = self._get_proc()
        if self._conn is None:
            raise LSPError("Connection not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }

        data = self._conn.send_json(request)
        with self._rw_lock:
            proc.stdin.write(data)  # type: ignore[union-attr]
            proc.stdin.flush()  # type: ignore[union-attr]
            response = self._read_response(method)

        if "error" in response:
            raise LSPError(f"LSP error: {response['error']}")
        result_val: dict[str, Any] = response.get("result", {})
        return result_val

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a notification (no response expected)."""
        proc = self._get_proc()
        if self._conn is None:
            raise LSPError("Connection not initialized")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        data = self._conn.send_json(notification)
        with self._rw_lock:
            proc.stdin.write(data)  # type: ignore[union-attr]
            proc.stdin.flush()  # type: ignore[union-attr]

    def _read_response(self, method: str) -> dict[str, Any]:
        """Read and parse an LSP response."""
        proc = self._get_proc()
        if self._conn is None:
            raise LSPError("Connection not initialized")

        while True:
            if proc.stdout is None:
                raise LSPError("stdout closed")
            event = self._conn.next_event()
            if event is NEED_DATA:
                with self._rw_lock:
                    data = proc.stdout.read(4096)
                    if data == b"":
                        raise LSPError(f"stdout closed during {method}")
                    self._conn.receive(data)
            elif isinstance(event, DataReceived):
                pass
            elif isinstance(event, MessageEnd):
                break

        header, body = self._conn.get_received_data()
        if header.get("error"):
            return {"error": header["error"]}
        return {"result": body} if body else {}

    def _open_document(self, file_path: str, text: str | None = None) -> None:
        """Send textDocument/didOpen notification."""
        abs_path = os.path.abspath(file_path)
        if text is None:
            try:
                with open(abs_path, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                text = ""

        self._send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": f"file://{abs_path}",
                    "languageId": "python",
                    "version": 1,
                    "text": text,
                }
            },
        )

    def goto_definition(self, file_path: str, line: int, col: int) -> Location | None:
        """Jump to the definition of the symbol at the given position.

        Args:
            file_path: Path to the file (relative or absolute)
            line: 0-indexed line number
            col: 0-indexed column number

        Returns:
            Location of the definition, or None if not found
        """
        abs_path = os.path.abspath(file_path)
        self._open_document(abs_path)

        result = self._send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": f"file://{abs_path}"},
                "position": {"line": line, "character": col},
            },
        )

        if not result:
            return None

        locations = result if isinstance(result, list) else [result]
        if not locations:
            return None

        loc = locations[0]
        uri = loc.get("uri", "")
        start = loc.get("range", {}).get("start", {})

        file_uri_prefix = "file://"
        if uri.startswith(file_uri_prefix):
            loc_path = uri[len(file_uri_prefix) :]
        else:
            loc_path = uri

        return Location(
            file_path=loc_path,
            line=start.get("line", 0),
            character=start.get("character", 0),
        )

    def hover(self, file_path: str, line: int, col: int) -> HoverInfo | None:
        """Get hover information (type hints, docstrings) at the given position.

        Args:
            file_path: Path to the file (relative or absolute)
            line: 0-indexed line number
            col: 0-indexed column number

        Returns:
            HoverInfo with contents, or None if not found
        """
        abs_path = os.path.abspath(file_path)
        self._open_document(abs_path)

        result = self._send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": f"file://{abs_path}"},
                "position": {"line": line, "character": col},
            },
        )

        if not result:
            return None

        contents = result.get("contents", {})
        if isinstance(contents, str):
            value = contents
        else:
            value = contents.get("value", "")

        range_info = result.get("range", {})
        start = range_info.get("start", {}) if range_info else {}

        return HoverInfo(
            contents=value,
            file_path=abs_path,
            line=start.get("line", line),
            character=start.get("character", col),
        )

    def find_references(self, file_path: str, line: int, col: int) -> list[Location]:
        """Find all references to the symbol at the given position.

        Args:
            file_path: Path to the file (relative or absolute)
            line: 0-indexed line number
            col: 0-indexed column number

        Returns:
            List of locations where the symbol is referenced
        """
        abs_path = os.path.abspath(file_path)
        self._open_document(abs_path)

        result = self._send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": f"file://{abs_path}"},
                "position": {"line": line, "character": col},
                "context": {"includeDeclaration": True},
            },
        )

        if not result:
            return []

        locations: list[Location] = []
        file_uri_prefix = "file://"
        result_list: list[Any] = result if isinstance(result, list) else [result]

        for loc in result_list:
            uri = loc.get("uri", "")
            start = loc.get("range", {}).get("start", {})

            if uri.startswith(file_uri_prefix):
                loc_path = uri[len(file_uri_prefix) :]
            else:
                loc_path = uri

            locations.append(
                Location(
                    file_path=loc_path,
                    line=start.get("line", 0),
                    character=start.get("character", 0),
                )
            )

        return locations

    def diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Get all diagnostics (errors, warnings, info) for a file.

        Note: basedpyright reports diagnostics via the publishDiagnostics
        notification. This method triggers analysis and returns current diagnostics.

        Args:
            file_path: Path to the file (relative or absolute)

        Returns:
            List of diagnostics found in the file
        """
        abs_path = os.path.abspath(file_path)
        self._open_document(abs_path)

        result = self._send_request(
            "textDocument/diagnostic",
            {
                "textDocument": {"uri": f"file://{abs_path}"},
            },
        )

        if not result:
            return []

        items = result.get("items", []) if isinstance(result, dict) else result
        if not isinstance(items, list):
            return []

        diagnostics = []
        for item in items:
            severity = item.get("severity", 1)
            severity_map = {1: "error", 2: "warning", 3: "information", 4: "hint"}
            severity_str = severity_map.get(severity, "information")

            range_info = item.get("range", {})
            start = range_info.get("start", {})

            diagnostics.append(
                Diagnostic(
                    message=item.get("message", ""),
                    file_path=abs_path,
                    line=start.get("line", 0),
                    character=start.get("character", 0),
                    severity=severity_str,
                )
            )

        return diagnostics

    def document_symbols(self, file_path: str) -> list[dict[str, Any]]:
        """Get all symbols defined in a file.

        Args:
            file_path: Path to the file (relative or absolute)

        Returns:
            List of symbol information dicts with name, kind, location
        """
        abs_path = os.path.abspath(file_path)
        self._open_document(abs_path)

        result = self._send_request(
            "textDocument/documentSymbol",
            {
                "textDocument": {"uri": f"file://{abs_path}"},
            },
        )

        if not result:
            return []

        symbols: list[dict[str, Any]] = []
        result_list: list[Any] = result if isinstance(result, list) else [result]
        for item in result_list:
            location = item.get("location", {})
            range_info = location.get("range", {})
            start = range_info.get("start", {})

            symbols.append(
                {
                    "name": item.get("name", ""),
                    "kind": item.get("kind", 0),
                    "file_path": abs_path,
                    "line": start.get("line", 0),
                    "character": start.get("character", 0),
                }
            )

        return symbols

    def shutdown(self) -> None:
        """Gracefully shutdown the language server."""
        if self._proc is None:
            return

        try:
            self._send_request("shutdown", {})
        except LSPError:
            pass

        try:
            self._send_notification("exit", {})
        except LSPError:
            pass

        with self._rw_lock:
            if self._proc is not None:
                self._proc.stdin.close()  # type: ignore[union-attr]
                self._proc.wait(timeout=5)
                self._proc = None
                self._conn = None


_basedpyright_instance: BasedPyrightClient | None = None


def _get_client() -> BasedPyrightClient:
    """Get or create the singleton BasedPyrightClient instance."""
    global _basedpyright_instance
    if _basedpyright_instance is None:
        _basedpyright_instance = BasedPyrightClient()
    return _basedpyright_instance


class _BasedPyrightProxy:
    """Proxy object that delegates all attribute access to the singleton client."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_client(), name)

    def __repr__(self) -> str:
        return f"BasedPyrightProxy() -> {_get_client()!r}"


basedpyright: BasedPyrightClient = _BasedPyrightProxy()  # type: ignore[assignment]
"""Singleton proxy to the BasedPyrightClient instance.

All method calls are forwarded to the lazily-initialized singleton.
Usage:
    from core.lsp_client import basedpyright
    loc = basedpyright.goto_definition("core/models.py", line=10, col=0)
"""
