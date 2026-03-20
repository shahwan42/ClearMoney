"""Tests for HTMX helper functions in core/htmx.py."""

from django.test import RequestFactory

from core.htmx import htmx_redirect, render_htmx_result


class TestHtmxRedirect:
    """htmx_redirect returns client redirect for HTMX, 302 for regular."""

    def test_htmx_request_returns_client_redirect(self) -> None:
        factory = RequestFactory()
        request = factory.get("/", HTTP_HX_REQUEST="true")
        # HtmxMiddleware isn't active, so set htmx attr manually
        request.htmx = True  # type: ignore[attr-defined]
        response = htmx_redirect(request, "/dashboard")
        # HttpResponseClientRedirect returns 200 with HX-Redirect header
        assert response.status_code == 200
        assert response["HX-Redirect"] == "/dashboard"

    def test_regular_request_returns_302(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")
        request.htmx = False  # type: ignore[attr-defined]
        response = htmx_redirect(request, "/dashboard")
        assert response.status_code == 302
        assert response["Location"] == "/dashboard"


class TestRenderHtmxResult:
    """render_htmx_result returns styled HTML fragments."""

    def test_success_result(self) -> None:
        response = render_htmx_result("success", "Account created")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Account created" in content
        assert "green" in content

    def test_error_result(self) -> None:
        response = render_htmx_result("error", "Invalid amount")
        content = response.content.decode()
        assert "Invalid amount" in content
        assert "red" in content

    def test_info_result(self) -> None:
        response = render_htmx_result("info", "No changes made")
        content = response.content.decode()
        assert "No changes made" in content
        assert "blue" in content

    def test_with_detail(self) -> None:
        response = render_htmx_result("error", "Failed", detail="Check input")
        content = response.content.decode()
        assert "Failed" in content
        assert "Check input" in content

    def test_empty_detail_omitted(self) -> None:
        response = render_htmx_result("success", "Done", detail="")
        content = response.content.decode()
        assert "Done" in content

    def test_unknown_type_defaults_to_info(self) -> None:
        response = render_htmx_result("warning", "Something happened")
        content = response.content.decode()
        assert "Something happened" in content
        assert "blue" in content
