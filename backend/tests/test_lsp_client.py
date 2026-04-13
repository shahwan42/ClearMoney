"""
Tests for the LSP client module.

Uses mocking to avoid spawning the actual language server subprocess.
The real integration is tested via manual smoke tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.lsp_client import (
    LANGSERVER_BIN,
    BasedPyrightClient,
    Diagnostic,
    HoverInfo,
    Location,
    LSPError,
)


class TestLocation:
    """Tests for the Location dataclass."""

    def test_repr(self) -> None:
        loc = Location(file_path="/foo/bar.py", line=10, character=5)
        assert "bar.py" in repr(loc)
        assert "line=10" in repr(loc)
        assert "character=5" in repr(loc)

    def test_attributes(self) -> None:
        loc = Location(file_path="/foo/bar.py", line=10, character=5)
        assert loc.file_path == "/foo/bar.py"
        assert loc.line == 10
        assert loc.character == 5


class TestHoverInfo:
    """Tests for the HoverInfo dataclass."""

    def test_repr_truncates_long_contents(self) -> None:
        hover = HoverInfo(
            contents="x" * 100,
            file_path="/foo/bar.py",
            line=10,
            character=5,
        )
        assert "x" * 50 in repr(hover)
        assert "x" * 100 not in repr(hover)

    def test_attributes(self) -> None:
        hover = HoverInfo(
            contents="SomeType",
            file_path="/foo/bar.py",
            line=10,
            character=5,
        )
        assert hover.contents == "SomeType"
        assert hover.file_path == "/foo/bar.py"
        assert hover.line == 10
        assert hover.character == 5


class TestDiagnostic:
    """Tests for the Diagnostic dataclass."""

    def test_repr(self) -> None:
        diag = Diagnostic(
            message="Undefined variable 'x'",
            file_path="/foo/bar.py",
            line=10,
            character=5,
            severity="error",
        )
        assert "error" in repr(diag)
        assert "Undefined variable" in repr(diag)

    def test_attributes(self) -> None:
        diag = Diagnostic(
            message="Some warning",
            file_path="/foo/bar.py",
            line=1,
            character=0,
            severity="warning",
        )
        assert diag.message == "Some warning"
        assert diag.severity == "warning"


class TestSingleton:
    """Tests for singleton behavior of BasedPyrightClient."""

    def test_singleton_same_instance(self) -> None:
        client1 = BasedPyrightClient()
        client2 = BasedPyrightClient()
        assert client1 is client2

    def test_proxy_delegates_to_singleton(self) -> None:
        with patch("core.lsp_client._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            from core import lsp_client

            lsp_client.basedpyright.goto_definition("foo.py", 0, 0)
            mock_client.goto_definition.assert_called_once_with("foo.py", 0, 0)


class TestBasedPyrightClient:
    """Tests for BasedPyrightClient methods with mocked subprocess."""

    @pytest.fixture
    def mock_client(self) -> BasedPyrightClient:
        """Create a mock client with mocked subprocess/connection."""
        client = BasedPyrightClient.__new__(BasedPyrightClient)
        client._proc = MagicMock()
        client._conn = MagicMock()
        client._request_id = 0
        client._initialized = True
        client._initialized_version = True
        return client

    def test_goto_definition_not_found(self, mock_client: BasedPyrightClient) -> None:
        """goto_definition returns None when no definition found."""
        with (
            patch.object(mock_client, "_send_request", return_value=None),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.goto_definition("core/models.py", 0, 0)
        assert result is None

    def test_goto_definition_found(self, mock_client: BasedPyrightClient) -> None:
        """goto_definition returns Location when definition found."""
        with (
            patch.object(
                mock_client,
                "_send_request",
                return_value=[
                    {
                        "uri": "file:///project/backend/core/models.py",
                        "range": {"start": {"line": 10, "character": 5}},
                    }
                ],
            ),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.goto_definition("core/models.py", 0, 0)
        assert result is not None
        assert result.line == 10
        assert result.character == 5

    def test_hover_not_found(self, mock_client: BasedPyrightClient) -> None:
        """hover returns None when no hover info available."""
        with (
            patch.object(mock_client, "_send_request", return_value=None),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.hover("core/models.py", 0, 0)
        assert result is None

    def test_hover_found_string_contents(self, mock_client: BasedPyrightClient) -> None:
        """hover returns HoverInfo with string contents."""
        with (
            patch.object(
                mock_client,
                "_send_request",
                return_value={
                    "contents": "class MyClass:",
                    "range": {"start": {"line": 1, "character": 0}},
                },
            ),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.hover("core/models.py", 0, 0)
        assert result is not None
        assert result.contents == "class MyClass:"

    def test_hover_found_marked_contents(self, mock_client: BasedPyrightClient) -> None:
        """hover returns HoverInfo with marked contents."""
        with (
            patch.object(
                mock_client,
                "_send_request",
                return_value={
                    "contents": {"value": "class MyClass:", "kind": "markdown"},
                    "range": {"start": {"line": 1, "character": 0}},
                },
            ),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.hover("core/models.py", 0, 0)
        assert result is not None
        assert result.contents == "class MyClass:"

    def test_find_references_empty(self, mock_client: BasedPyrightClient) -> None:
        """find_references returns empty list when no references found."""
        with (
            patch.object(mock_client, "_send_request", return_value=None),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.find_references("core/models.py", 0, 0)
        assert result == []

    def test_find_references_found(self, mock_client: BasedPyrightClient) -> None:
        """find_references returns list of Locations."""
        with (
            patch.object(
                mock_client,
                "_send_request",
                return_value=[
                    {
                        "uri": "file:///project/backend/core/models.py",
                        "range": {"start": {"line": 10, "character": 5}},
                    },
                    {
                        "uri": "file:///project/backend/core/models.py",
                        "range": {"start": {"line": 20, "character": 10}},
                    },
                ],
            ),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.find_references("core/models.py", 0, 0)
        assert len(result) == 2
        assert result[0].line == 10
        assert result[1].line == 20

    def test_diagnostics_empty(self, mock_client: BasedPyrightClient) -> None:
        """diagnostics returns empty list when no issues found."""
        with (
            patch.object(mock_client, "_send_request", return_value=None),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.diagnostics("core/models.py")
        assert result == []

    def test_diagnostics_found(self, mock_client: BasedPyrightClient) -> None:
        """diagnostics returns list of Diagnostic objects."""
        with (
            patch.object(
                mock_client,
                "_send_request",
                return_value={
                    "items": [
                        {
                            "message": "Undefined variable 'x'",
                            "severity": 1,
                            "range": {"start": {"line": 10, "character": 5}},
                        },
                        {
                            "message": "Unused import",
                            "severity": 2,
                            "range": {"start": {"line": 5, "character": 0}},
                        },
                    ]
                },
            ),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.diagnostics("core/models.py")
        assert len(result) == 2
        assert result[0].severity == "error"
        assert result[0].message == "Undefined variable 'x'"
        assert result[1].severity == "warning"
        assert result[1].message == "Unused import"

    def test_document_symbols_empty(self, mock_client: BasedPyrightClient) -> None:
        """document_symbols returns empty list when no symbols found."""
        with (
            patch.object(mock_client, "_send_request", return_value=None),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.document_symbols("core/models.py")
        assert result == []

    def test_document_symbols_found(self, mock_client: BasedPyrightClient) -> None:
        """document_symbols returns list of symbol dicts."""
        with (
            patch.object(
                mock_client,
                "_send_request",
                return_value=[
                    {
                        "name": "MyClass",
                        "kind": 11,
                        "location": {"range": {"start": {"line": 1, "character": 0}}},
                    },
                    {
                        "name": "my_function",
                        "kind": 12,
                        "location": {"range": {"start": {"line": 10, "character": 0}}},
                    },
                ],
            ),
            patch.object(mock_client, "_open_document"),
        ):
            result = mock_client.document_symbols("core/models.py")
        assert len(result) == 2
        assert result[0]["name"] == "MyClass"
        assert result[1]["name"] == "my_function"


class TestLangserverPath:
    """Tests for langserver binary path resolution."""

    def test_langserver_bin_exists(self) -> None:
        """LANGSERVER_BIN should resolve to a path in the venv."""
        assert ".venv" in LANGSERVER_BIN
        assert "basedpyright-langserver" in LANGSERVER_BIN


class TestLSPError:
    """Tests for the LSPError exception."""

    def test_lsp_error_message(self) -> None:
        err = LSPError("Test error message")
        assert str(err) == "Test error message"
        assert issubclass(LSPError, Exception)
