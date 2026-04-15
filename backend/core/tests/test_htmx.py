"""Tests for HTMX helper functions in core/htmx.py."""

from django.test import RequestFactory

from core.htmx import (
    error_html,
    error_response,
    htmx_redirect,
    operational_error_response,
    render_htmx_result,
    success_html,
    success_response,
    validation_error_response,
)


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


class TestErrorHtml:
    """error_html returns styled error HTML string."""

    def test_contains_message(self) -> None:
        html = error_html("Something went wrong")
        assert "Something went wrong" in html
        assert "bg-red-50" in html

    def test_returns_string(self) -> None:
        assert isinstance(error_html("test"), str)

    def test_has_aria_live_assertive(self) -> None:
        """Error HTML must use aria-live='assertive' for screen readers."""
        html = error_html("Invalid amount")
        assert 'aria-live="assertive"' in html

    def test_has_error_icon(self) -> None:
        """Error HTML must include a visual error indicator."""
        html = error_html("Invalid amount")
        assert "svg" in html.lower() or "&#" in html or "⚠" in html

    def test_scrolls_into_view(self) -> None:
        """Error HTML must scroll into view when rendered."""
        html = error_html("Invalid amount")
        assert "scrollIntoView" in html


class TestSuccessHtml:
    """success_html returns styled success HTML string."""

    def test_contains_message(self) -> None:
        html = success_html("Transfer completed!")
        assert "Transfer completed!" in html
        assert "bg-teal-50" in html
        assert "animate-toast" in html

    def test_returns_string(self) -> None:
        assert isinstance(success_html("test"), str)

    def test_has_auto_dismiss(self) -> None:
        """Success toast must auto-dismiss after a timeout."""
        html = success_html("Saved!")
        assert "setTimeout" in html

    def test_has_dismiss_button(self) -> None:
        """Success toast must have a manual dismiss button."""
        html = success_html("Saved!")
        assert "Dismiss" in html


class TestFieldErrorHighlighting:
    """error_html with field param highlights the specific input."""

    def test_field_param_adds_highlight_script(self) -> None:
        """Passing a field name injects JS to mark the input as invalid."""
        html = error_html("Amount is required", field="amount")
        assert "aria-invalid" in html
        assert "amount" in html

    def test_field_param_adds_aria_describedby(self) -> None:
        """Error with field sets aria-describedby to connect input to error."""
        html = error_html("Amount is required", field="amount")
        assert "aria-describedby" in html

    def test_no_field_param_no_highlight(self) -> None:
        """Without field param, no field highlight script is added."""
        html = error_html("Something went wrong")
        assert "aria-invalid" not in html

    def test_error_response_with_field(self) -> None:
        """error_response passes field through to error_html."""
        response = error_response("Amount is required", field="amount")
        content = response.content.decode()
        assert "aria-invalid" in content
        assert response.status_code == 400


class TestErrorResponse:
    """error_response returns HttpResponse with status 400."""

    def test_status_400(self) -> None:
        response = error_response("Invalid amount")
        assert response.status_code == 400
        assert "Invalid amount" in response.content.decode()


class TestSuccessResponse:
    """success_response returns HttpResponse with status 200."""

    def test_status_200(self) -> None:
        response = success_response("Done!")
        assert response.status_code == 200
        assert "Done!" in response.content.decode()


class TestValidationErrorResponse:
    """validation_error_response returns HttpResponse with status 422."""

    def test_status_422(self) -> None:
        response = validation_error_response("Name is required")
        assert response.status_code == 422
        assert "Name is required" in response.content.decode()

    def test_returns_error_html(self) -> None:
        """Response body uses the shared error_html styling."""
        response = validation_error_response("Invalid date")
        content = response.content.decode()
        assert "bg-red-50" in content

    def test_field_param_propagated(self) -> None:
        """field= is forwarded to error_html to highlight the input."""
        response = validation_error_response("Required", field="name")
        content = response.content.decode()
        assert "aria-invalid" in content
        assert "name" in content


class TestOperationalErrorResponse:
    """operational_error_response returns HttpResponse with status 400."""

    def test_status_400(self) -> None:
        response = operational_error_response("Budget already exists")
        assert response.status_code == 400
        assert "Budget already exists" in response.content.decode()

    def test_returns_error_html(self) -> None:
        """Response body uses the shared error_html styling."""
        response = operational_error_response("Duplicate entry")
        content = response.content.decode()
        assert "bg-red-50" in content

    def test_field_param_propagated(self) -> None:
        """field= is forwarded to error_html."""
        response = operational_error_response("Invalid amount", field="amount")
        content = response.content.decode()
        assert "aria-invalid" in content
        assert "amount" in content
