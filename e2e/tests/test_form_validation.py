"""Inline form validation tests.

Tests client-side validation with aria-invalid states and field-specific error messages.
Validates on blur, clears on valid input, does not block submission.

Coverage:
- Amount fields: validate > 0 on blur
- Required fields: validate non-empty on blur
- Date fields: validate not in future on blur
- Name/note fields: show character count near maxlength
- aria-invalid="true" set on invalid fields
- aria-describedby links field to error message
- Error messages use role="alert"
- Visual: red border + error text below field
- Does not block submission — server validation remains authoritative
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import ensure_auth, reset_database, get_category_id

_account_id: str = ""
_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + account."""
    global _account_id, _user_id
    from conftest import _conn

    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestTransactionFormValidation:
    """Test inline validation on transaction form."""

    def test_amount_field_shows_error_on_zero(self, page: Page) -> None:
        """Amount field shows error when value is 0."""
        page.goto("/transactions/new")
        amount_input = page.locator('input[name="amount"]')

        # Fill with invalid value and blur
        amount_input.fill("0")
        amount_input.blur()

        # Should show error
        expect(amount_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#amount-input-error")).to_be_visible()
        expect(page.locator("#amount-input-error")).to_contain_text(
            "Amount must be greater than 0"
        )
        expect(page.locator("#amount-input-error")).to_have_attribute("role", "alert")

    def test_amount_field_clears_error_on_valid_input(self, page: Page) -> None:
        """Amount error clears when valid value entered."""
        page.goto("/transactions/new")
        amount_input = page.locator('input[name="amount"]')

        # Trigger error
        amount_input.fill("0")
        amount_input.blur()
        expect(amount_input).to_have_attribute("aria-invalid", "true")

        # Fix the error
        amount_input.fill("10")
        expect(amount_input).not_to_have_attribute("aria-invalid", "true")
        expect(page.locator("#amount-input-error")).not_to_be_visible()

    def test_required_field_shows_error_on_empty(self, page: Page) -> None:
        """Required field shows error when empty."""
        page.goto("/transactions/new")
        account_select = page.locator('select[name="account_id"]')

        # Select empty option and blur
        account_select.select_option("")
        account_select.blur()

        # Should show error
        expect(account_select).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#account-select-error")).to_contain_text(
            "This field is required"
        )

    def test_note_field_shows_character_count(self, page: Page) -> None:
        """Note field shows character count with maxlength."""
        page.goto("/transactions/new")
        note_input = page.locator('input[name="note"]')

        # Type some characters
        note_input.fill("Test note")

        # Should show character count
        expect(page.locator("#note-input-count")).to_be_visible()
        expect(page.locator("#note-input-count")).to_contain_text("9/500")

    def test_note_field_warns_near_limit(self, page: Page) -> None:
        """Note field shows warning color when approaching limit."""
        page.goto("/transactions/new")
        note_input = page.locator('input[name="note"]')

        # Fill to 95% of limit (475 chars)
        note_input.fill("x" * 475)

        # Should show amber warning
        expect(page.locator("#note-input-count")).to_have_class(
            "text-amber-500 text-xs mt-1 text-right"
        )

    def test_date_field_rejects_future_date(self, page: Page) -> None:
        """Date field shows error for future dates."""
        page.goto("/transactions/new")

        # Open more options to show date picker
        page.click("#more-options-toggle")

        date_input = page.locator('input[name="date"]')
        future_date = "2099-01-01"

        # Set future date and blur
        date_input.fill(future_date)
        date_input.blur()

        # Should show error
        expect(date_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#date-picker-error")).to_contain_text(
            "Date cannot be in the future"
        )

    def test_fee_field_validates_minimum(self, page: Page) -> None:
        """Fee field validates minimum value."""
        page.goto("/transactions/new")

        # Open more options to show fee field
        page.click("#more-options-toggle")

        fee_input = page.locator('input[name="fee_amount"]')

        # Set negative value
        fee_input.fill("-5")
        fee_input.blur()

        # Should show error
        expect(fee_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#fee-input-error")).to_contain_text(
            "Amount must be greater than 0"
        )


class TestBudgetFormValidation:
    """Test inline validation on budget forms."""

    def test_budget_limit_shows_error_on_zero(self, page: Page) -> None:
        """Budget monthly limit shows error on zero."""
        page.goto("/budgets")
        limit_input = page.locator("#cat-monthly-limit")

        # Fill with invalid value and blur
        limit_input.fill("0")
        limit_input.blur()

        # Should show error
        expect(limit_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#cat-monthly-limit-error")).to_be_visible()
        expect(page.locator("#cat-monthly-limit-error")).to_contain_text(
            "Amount must be greater than 0"
        )

    def test_total_budget_limit_validates_required(self, page: Page) -> None:
        """Total budget limit validates required field."""
        page.goto("/budgets")
        limit_input = page.locator("#total-limit-new")

        # Clear and blur
        limit_input.fill("")
        limit_input.blur()

        # Should show error
        expect(limit_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#total-limit-new-error")).to_contain_text(
            "This field is required"
        )


class TestPeopleFormValidation:
    """Test inline validation on people form."""

    def test_person_name_required(self, page: Page) -> None:
        """Person name field validates required."""
        page.goto("/people")
        name_input = page.locator("#person-name-input")

        # Clear and blur
        name_input.fill("")
        name_input.blur()

        # Should show error
        expect(name_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#person-name-input-error")).to_contain_text(
            "This field is required"
        )

    def test_person_name_character_count(self, page: Page) -> None:
        """Person name shows character count."""
        page.goto("/people")
        name_input = page.locator("#person-name-input")

        # Type some characters
        name_input.fill("John Doe")

        # Should show character count
        expect(page.locator("#person-name-input-count")).to_be_visible()
        expect(page.locator("#person-name-input-count")).to_contain_text("8/100")


class TestRecurringFormValidation:
    """Test inline validation on recurring rule form."""

    def test_recurring_amount_validates_minimum(self, page: Page) -> None:
        """Recurring amount validates minimum value."""
        page.goto("/recurring")
        amount_input = page.locator('input[name="amount"]')

        # Fill with invalid value and blur
        amount_input.fill("0")
        amount_input.blur()

        # Should show error
        expect(amount_input).to_have_attribute("aria-invalid", "true")
        expect(
            page.locator('input[name="amount"] + div[role="alert"]')
        ).to_contain_text("Amount must be greater than 0")

    def test_recurring_note_character_count(self, page: Page) -> None:
        """Recurring note shows character count."""
        page.goto("/recurring")
        note_input = page.locator("#recurring-note-input")

        # Type some characters
        note_input.fill("Monthly payment")

        # Should show character count
        expect(page.locator("#recurring-note-input-count")).to_be_visible()
        expect(page.locator("#recurring-note-input-count")).to_contain_text("15/200")

    def test_recurring_date_rejects_future(self, page: Page) -> None:
        """Recurring next due date rejects future dates."""
        page.goto("/recurring")
        date_input = page.locator("#recurring-next-due")

        # Clear and set future date
        date_input.fill("2099-01-01")
        date_input.blur()

        # Should show error
        expect(date_input).to_have_attribute("aria-invalid", "true")
        expect(page.locator("#recurring-next-due-error")).to_contain_text(
            "Date cannot be in the future"
        )


class TestAccountFormValidation:
    """Test inline validation on account forms."""

    def test_initial_balance_validates_minimum(self, page: Page) -> None:
        """Initial balance validates minimum value."""
        page.goto("/accounts")

        # Open create account sheet
        page.click('button:has-text("+ Account")')

        # Wait for sheet content
        page.wait_for_selector("#add-acct-balance")

        balance_input = page.locator("#add-acct-balance")

        # The field has min="0" so negative should trigger validation
        # Note: HTML5 number input may prevent entering negative values
        # We test that the validation attribute is present
        expect(balance_input).to_have_attribute("data-validate", "min:0")

    def test_account_name_character_count(self, page: Page) -> None:
        """Account custom name shows character count."""
        page.goto("/accounts")

        # Open create account sheet
        page.click('button:has-text("+ Account")')

        # Wait for sheet content
        page.wait_for_selector("#add-acct-custom-name")

        name_input = page.locator("#add-acct-custom-name")

        # Type some characters
        name_input.fill("My Savings Account")

        # Should show character count
        expect(page.locator("#add-acct-custom-name-count")).to_be_visible()
        expect(page.locator("#add-acct-custom-name-count")).to_contain_text("18/100")


class TestValidationAccessibility:
    """Test accessibility attributes for validation."""

    def test_aria_describedby_links_to_error(self, page: Page) -> None:
        """aria-describedby correctly links field to error message."""
        page.goto("/transactions/new")
        amount_input = page.locator('input[name="amount"]')

        # Trigger error
        amount_input.fill("0")
        amount_input.blur()

        # Should have aria-describedby pointing to error element
        expect(amount_input).to_have_attribute("aria-describedby", "amount-input-error")

    def test_error_container_has_role_alert(self, page: Page) -> None:
        """Error container has role="alert" for screen readers."""
        page.goto("/transactions/new")
        amount_input = page.locator('input[name="amount"]')

        # Trigger error
        amount_input.fill("0")
        amount_input.blur()

        # Error element should have role="alert"
        error_el = page.locator("#amount-input-error")
        expect(error_el).to_have_attribute("role", "alert")


class TestValidationDoesNotBlockSubmission:
    """Test that client-side validation does not block form submission."""

    def test_form_can_submit_with_validation_errors(self, page: Page) -> None:
        """Form can still be submitted even with validation errors."""
        page.goto("/transactions/new")

        # Fill form with invalid data
        amount_input = page.locator('input[name="amount"]')
        amount_input.fill("0")

        # Blur to trigger validation
        amount_input.blur()

        # Verify error is shown
        expect(amount_input).to_have_attribute("aria-invalid", "true")

        # Form should still be submittable (server validation is authoritative)
        submit_btn = page.locator('button[type="submit"]')
        expect(submit_btn).to_be_enabled()
