"""Transaction attachment upload/view/delete E2E tests — T070.

Tests the full attachment lifecycle:
  1. Create a transaction with a receipt image via POST API
  2. Verify the attachment appears in the transaction detail sheet
  3. Delete the attachment and verify it is removed

Note: The transaction_new.html form uses hx-boost which, for partial-only server
responses, falls back to a full page reload. We use page.request.post() directly
to avoid this and to keep tests fast and reliable.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    get_category_id,
    reset_database,
    create_transaction,
)

_account_id: str = ""
_user_id: str = ""

# Minimal valid 1×1 PNG bytes (correct MIME type — passes server validation)
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _account_id, _user_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


def _get_csrf(page: Page) -> str:
    """Return the current CSRF token from the page's cookies."""
    # Navigate to any page to ensure Django has set the csrftoken cookie
    page.goto("/transactions/new")
    cookies = {c["name"]: c["value"] for c in page.context.cookies()}
    return cookies.get("csrftoken", "")


def _post_transaction_with_attachment(page: Page, cat_id: str, amount: str, note: str) -> str:
    """Upload a new transaction with a PNG attachment. Returns the transaction ID from DB."""
    csrf = _get_csrf(page)
    resp = page.request.post(
        "/transactions",
        multipart={
            "csrfmiddlewaretoken": csrf,
            "type": "expense",
            "amount": amount,
            "account_id": _account_id,
            "category_id": cat_id,
            "note": note,
            "attachment": {
                "name": "receipt.png",
                "mimeType": "image/png",
                "buffer": _TINY_PNG,
            },
        },
        headers={"X-CSRFToken": csrf},
    )
    assert resp.ok, f"Transaction create failed: {resp.status} {resp.text()}"
    assert "deducted from" in resp.text(), f"Unexpected response: {resp.text()[:200]}"

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                (_user_id,),
            )
            row = cur.fetchone()
            assert row is not None
            return str(row[0])


class TestAttachments:
    def test_upload_attachment_with_new_transaction(self, page: Page) -> None:
        """Creating a transaction with an image attachment returns success response."""
        cat_id = get_category_id("expense", _user_id)
        csrf = _get_csrf(page)
        resp = page.request.post(
            "/transactions",
            multipart={
                "csrfmiddlewaretoken": csrf,
                "type": "expense",
                "amount": "100",
                "account_id": _account_id,
                "category_id": cat_id,
                "note": "Receipt upload test",
                "attachment": {
                    "name": "receipt.png",
                    "mimeType": "image/png",
                    "buffer": _TINY_PNG,
                },
            },
            headers={"X-CSRFToken": csrf},
        )
        assert resp.ok
        assert "deducted from" in resp.text()

    def test_attachment_stored_in_database(self, page: Page) -> None:
        """A transaction created with an attachment has a non-null attachment path in DB."""
        cat_id = get_category_id("expense", _user_id)
        _post_transaction_with_attachment(page, cat_id, "75", "DB attachment test")

        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT attachment FROM transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                    (_user_id,),
                )
                row = cur.fetchone()
                assert row is not None
                assert row[0] is not None, "Attachment path should be stored in DB"
                assert "receipt" in str(row[0]).lower() or ".png" in str(row[0]).lower()

    def test_attachment_visible_in_transaction_detail(self, page: Page) -> None:
        """A transaction with an uploaded attachment shows 'Attachment' section in detail view."""
        cat_id = get_category_id("expense", _user_id)
        tx_id = _post_transaction_with_attachment(page, cat_id, "75", "Detail view test")

        # Navigate to the transaction detail partial
        page.goto(f"/transactions/detail/{tx_id}")
        expect(page.locator("body")).to_contain_text("Attachment")

    def test_delete_attachment_removes_it_from_detail(self, page: Page) -> None:
        """Deleting an attachment via POST removes it and the detail no longer shows it."""
        cat_id = get_category_id("expense", _user_id)
        tx_id = _post_transaction_with_attachment(page, cat_id, "50", "Delete test")

        # Verify attachment shows in detail before deletion
        page.goto(f"/transactions/detail/{tx_id}")
        expect(page.locator("body")).to_contain_text("Attachment")

        # Delete attachment via direct POST (bypasses hx-confirm dialog)
        csrf = _get_csrf(page)
        del_resp = page.request.post(
            f"/transactions/{tx_id}/delete-attachment",
            headers={"X-CSRFToken": csrf},
            data={"csrfmiddlewaretoken": csrf},
        )
        assert del_resp.ok
        # After deletion the detail partial should NOT show the Attachment section
        assert "Attachment" not in del_resp.text()

    def test_invalid_attachment_type_rejected(self, page: Page) -> None:
        """Uploading a non-image file (e.g., .txt) returns a validation error response."""
        cat_id = get_category_id("expense", _user_id)
        csrf = _get_csrf(page)
        resp = page.request.post(
            "/transactions",
            multipart={
                "csrfmiddlewaretoken": csrf,
                "type": "expense",
                "amount": "25",
                "account_id": _account_id,
                "category_id": cat_id,
                "attachment": {
                    "name": "virus.txt",
                    "mimeType": "text/plain",
                    "buffer": b"evil content",
                },
            },
            headers={"X-CSRFToken": csrf},
        )
        # Server returns error HTML (swap target with error message)
        assert "JPEG, PNG" in resp.text() or "image" in resp.text().lower()
        assert "deducted from" not in resp.text()
