"""Post-deployment smoke test for the live ClearMoney app."""

from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from http.cookies import SimpleCookie
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, Institution
from auth_app.models import AuthToken, Session, User, UserCurrencyPreference
from auth_app.services import seed_default_categories
from budgets.models import Budget, TotalBudget
from categories.models import Category
from transactions.models import Tag, Transaction

SMOKE_EMAIL = "smoke-deploy@clearmoney.app"
SMOKE_ISOLATION_EMAIL = "smoke-deploy-isolation@clearmoney.app"
SMOKE_PREFIX = "[SMOKE]"
SMOKE_INST_NAME = "[SMOKE] Test Bank"
SMOKE_ACCT_A = "[SMOKE] Main EGP"
SMOKE_ACCT_B = "[SMOKE] Savings EGP"
SMOKE_NOTE = "[SMOKE] expense"
SMOKE_TRANSFER_NOTE = "[SMOKE] transfer"
SMOKE_ISOLATION_NOTE = "[SMOKE] isolation secret"

SESSION_COOKIE_NAME = "clearmoney_session"
DEFAULT_TIMEOUT = 15
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5


class SmokeError(RuntimeError):
    """Raised when a smoke check fails."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirect responses to the caller instead of auto-following."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


@dataclass(frozen=True)
class SmokeSession:
    """Authenticated smoke-session state."""

    cookies: dict[str, str]
    csrf_token: str


class Command(BaseCommand):
    help = "Run a post-deploy smoke test against a live ClearMoney app."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--app-url",
            default=os.environ.get("APP_URL", "http://localhost:8000"),
            help="Base URL of the app under test (default: APP_URL env var).",
        )
        parser.add_argument(
            "--cleanup-only",
            action="store_true",
            help="Delete existing smoke data only; skip the HTTP smoke checks.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=DEFAULT_TIMEOUT,
            help="Per-request timeout in seconds (default: 15).",
        )
        parser.add_argument(
            "--no-cleanup",
            action="store_true",
            help="Keep smoke data after the run for debugging.",
        )

    def handle(self, *args: object, **options: object) -> None:
        app_url = _normalize_app_url(str(options["app_url"]))
        timeout = int(str(options["timeout"]))
        cleanup_only = bool(options["cleanup_only"])
        no_cleanup = bool(options["no_cleanup"])

        cleanup_needed = True
        try:
            _cleanup(self.stdout)
            cleanup_needed = False

            if cleanup_only:
                return

            cleanup_needed = True
            _run_smoke_tests(app_url=app_url, timeout=timeout, stdout=self.stdout)
        except SmokeError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            if cleanup_needed and not no_cleanup:
                _cleanup(self.stdout)


def _normalize_app_url(app_url: str) -> str:
    return app_url.rstrip("/")


def _smoke_emails() -> tuple[str, str]:
    return (SMOKE_EMAIL, SMOKE_ISOLATION_EMAIL)


def _cleanup(stdout: Any) -> None:
    emails = _smoke_emails()
    users = list(User.objects.filter(email__in=emails))
    token_count = AuthToken.objects.filter(email__in=emails).count()

    if not users and token_count == 0:
        stdout.write("Smoke cleanup: nothing to clean")
        return

    user_ids = [user.id for user in users]
    counts = {
        "users": len(users),
        "sessions": Session.objects.filter(user_id__in=user_ids).count(),
        "tokens": token_count,
        "transactions": Transaction.objects.filter(user_id__in=user_ids).count(),
        "budgets": Budget.objects.filter(user_id__in=user_ids).count(),
        "total_budgets": TotalBudget.objects.filter(user_id__in=user_ids).count(),
        "accounts": Account.objects.filter(user_id__in=user_ids).count(),
        "institutions": Institution.objects.filter(user_id__in=user_ids).count(),
        "categories": Category.objects.filter(user_id__in=user_ids).count(),
        "tags": Tag.objects.filter(user_id__in=user_ids).count(),
        "currency_prefs": UserCurrencyPreference.objects.filter(
            user_id__in=user_ids
        ).count(),
    }

    with transaction.atomic():
        if user_ids:
            Session.objects.filter(user_id__in=user_ids).delete()
            Transaction.objects.filter(user_id__in=user_ids).delete()
            Budget.objects.filter(user_id__in=user_ids).delete()
            TotalBudget.objects.filter(user_id__in=user_ids).delete()
            Account.objects.filter(user_id__in=user_ids).delete()
            Institution.objects.filter(user_id__in=user_ids).delete()
            Category.objects.filter(user_id__in=user_ids).delete()
            Tag.objects.filter(user_id__in=user_ids).delete()
            UserCurrencyPreference.objects.filter(user_id__in=user_ids).delete()
            User.objects.filter(id__in=user_ids).delete()

        AuthToken.objects.filter(email__in=emails).delete()

    stdout.write(
        "Smoke cleanup complete: "
        f"deleted {counts['users']} users, "
        f"{counts['accounts']} accounts, "
        f"{counts['transactions']} transactions, "
        f"{counts['budgets'] + counts['total_budgets']} budgets, "
        f"{counts['tokens']} tokens"
    )


def _run_smoke_tests(*, app_url: str, timeout: int, stdout: Any) -> None:
    stdout.write(f"Smoke test: checking {app_url}")
    _check_health(app_url=app_url, timeout=timeout)
    stdout.write("  PASS [health]")
    _check_auth_redirect(app_url=app_url, timeout=timeout)
    stdout.write("  PASS [auth-redirect]")

    smoke_user = _create_smoke_user(SMOKE_EMAIL)
    isolation_user = _create_smoke_user(SMOKE_ISOLATION_EMAIL)

    session = _authenticate_smoke_user(
        app_url=app_url,
        timeout=timeout,
        user=smoke_user,
    )
    stdout.write("  PASS [auth]")

    _check_authenticated_home(app_url=app_url, timeout=timeout, session=session)
    stdout.write("  PASS [auth-home]")

    category_budget = _get_category_id(smoke_user.id, "Food & Groceries")
    category_tx = _get_category_id(smoke_user.id, "Transport")

    institution_id = _create_institution(
        app_url=app_url,
        timeout=timeout,
        session=session,
    )
    account_a_id = _create_account(
        app_url=app_url,
        timeout=timeout,
        session=session,
        institution_id=institution_id,
        name=SMOKE_ACCT_A,
        initial_balance="10000.00",
    )
    account_b_id = _create_account(
        app_url=app_url,
        timeout=timeout,
        session=session,
        institution_id=institution_id,
        name=SMOKE_ACCT_B,
        initial_balance="0.00",
    )
    _create_budget(
        app_url=app_url,
        timeout=timeout,
        session=session,
        category_id=category_budget,
    )
    _create_transaction(
        app_url=app_url,
        timeout=timeout,
        session=session,
        account_id=account_a_id,
        category_id=category_tx,
        amount="500.00",
        note=SMOKE_NOTE,
    )
    balance_after_expense = _get_account_balance(
        app_url=app_url,
        timeout=timeout,
        session=session,
        account_id=account_a_id,
    )
    if balance_after_expense != Decimal("9500.00"):
        raise SmokeError(
            "FAIL [account-balance] account balance "
            f"{balance_after_expense} != expected 9500.00"
        )
    stdout.write("  PASS [cp-2]")

    _create_transfer(
        app_url=app_url,
        timeout=timeout,
        session=session,
        source_account_id=account_a_id,
        dest_account_id=account_b_id,
    )
    account_a_balance = _get_account_balance(
        app_url=app_url,
        timeout=timeout,
        session=session,
        account_id=account_a_id,
    )
    account_b_balance = _get_account_balance(
        app_url=app_url,
        timeout=timeout,
        session=session,
        account_id=account_b_id,
    )
    if account_a_balance != Decimal("4500.00") or account_b_balance != Decimal(
        "5000.00"
    ):
        raise SmokeError(
            "FAIL [transfer-balances] expected balances 4500.00 and 5000.00 "
            f"but got {account_a_balance} and {account_b_balance}"
        )
    stdout.write("  PASS [cp-3]")

    _create_transaction(
        app_url=app_url,
        timeout=timeout,
        session=session,
        account_id=account_a_id,
        category_id=category_budget,
        amount="500.00",
        note="[SMOKE] budget spend",
    )
    _check_budget_progress(app_url=app_url, timeout=timeout, session=session)
    stdout.write("  PASS [cp-4]")

    other_account_id, other_tx_id = _seed_isolation_data(isolation_user)
    _check_isolation(
        app_url=app_url,
        timeout=timeout,
        session=session,
        other_account_id=other_account_id,
        other_tx_id=other_tx_id,
    )
    stdout.write("  PASS [cp-6]")

    _check_dashboard_with_data(app_url=app_url, timeout=timeout, session=session)
    stdout.write("  PASS [cp-5]")
    stdout.write("Smoke test complete")


def _create_smoke_user(email: str) -> User:
    user = User.objects.create(email=email)
    seed_default_categories(str(user.id))
    UserCurrencyPreference.objects.get_or_create(
        user_id=user.id,
        defaults={
            "active_currency_codes": ["EGP"],
            "selected_display_currency": "EGP",
        },
    )
    return user


def _get_category_id(user_id: Any, label: str) -> str:
    category = Category.objects.filter(user_id=user_id, name__en=label).first()
    if category is None:
        raise SmokeError(f"FAIL [category-seed] category {label!r} not found")
    return str(category.id)


def _authenticate_smoke_user(*, app_url: str, timeout: int, user: User) -> SmokeSession:
    token = secrets.token_urlsafe(32)
    AuthToken.objects.create(
        email=user.email,
        token=token,
        purpose="login",
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    status, body, _headers, cookies = _request(
        "GET",
        f"{app_url}/auth/verify?token={urllib.parse.quote(token)}",
        timeout=timeout,
        allow_redirects=True,
    )
    if status != 200:
        raise SmokeError(
            f"FAIL [auth-verify] /auth/verify returned {status}, expected 200"
        )
    session_cookie = cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        raise SmokeError("FAIL [auth-verify] /auth/verify did not set session cookie")

    csrf_token = _ensure_csrf_cookie(
        app_url=app_url,
        timeout=timeout,
        cookies=cookies,
    )
    if "Net Worth" not in body and "Liquid Cash" not in body:
        status, dashboard_body, _headers, cookies = _request(
            "GET",
            f"{app_url}/",
            cookies=cookies,
            timeout=timeout,
        )
        if status != 200:
            raise SmokeError(
                "FAIL [auth-dashboard] authenticated dashboard did not load"
            )
        csrf_token = cookies.get("csrftoken", csrf_token)

    return SmokeSession(cookies=cookies, csrf_token=csrf_token)


def _ensure_csrf_cookie(*, app_url: str, timeout: int, cookies: dict[str, str]) -> str:
    status, _body, _headers, updated_cookies = _request(
        "GET",
        f"{app_url}/transactions/new",
        cookies=cookies,
        timeout=timeout,
    )
    if status != 200:
        raise SmokeError(
            f"FAIL [csrf-bootstrap] /transactions/new returned {status}, expected 200"
        )
    csrf_token = updated_cookies.get("csrftoken")
    if not csrf_token:
        raise SmokeError("FAIL [csrf-bootstrap] missing csrftoken cookie")
    return csrf_token


def _check_health(*, app_url: str, timeout: int) -> None:
    status, _body, _headers, _cookies = _request(
        "GET",
        f"{app_url}/healthz",
        timeout=timeout,
    )
    if status != 200:
        raise SmokeError(f"FAIL [health] /healthz returned {status}, expected 200")


def _check_auth_redirect(*, app_url: str, timeout: int) -> None:
    status, _body, headers, _cookies = _request(
        "GET",
        f"{app_url}/",
        timeout=timeout,
        allow_redirects=False,
    )
    location = headers.get("Location", "")
    if status not in REDIRECT_STATUSES or "/login" not in location:
        raise SmokeError("FAIL [auth-redirect] / should redirect to /login")


def _check_authenticated_home(
    *, app_url: str, timeout: int, session: SmokeSession
) -> None:
    status, body, _headers, _cookies = _request(
        "GET",
        f"{app_url}/",
        cookies=session.cookies,
        timeout=timeout,
    )
    if status != 200:
        raise SmokeError(f"FAIL [auth-home] authenticated home returned {status}")
    if "Sign in" in body and "email" in body.lower():
        raise SmokeError("FAIL [auth-home] authenticated request rendered login page")


def _check_dashboard_with_data(
    *, app_url: str, timeout: int, session: SmokeSession
) -> None:
    status, body, _headers, _cookies = _request(
        "GET",
        f"{app_url}/",
        cookies=session.cookies,
        timeout=timeout,
    )
    if status != 200:
        raise SmokeError(f"FAIL [dashboard-data] dashboard returned {status}")
    required = ("Net Worth", "Liquid Cash", SMOKE_NOTE)
    missing = [item for item in required if item not in body]
    if missing:
        raise SmokeError(
            "FAIL [dashboard-data] dashboard missing "
            + ", ".join(repr(item) for item in missing)
        )


def _create_institution(*, app_url: str, timeout: int, session: SmokeSession) -> str:
    status, body, _headers, _cookies = _request(
        "POST",
        f"{app_url}/api/institutions",
        json_data={"name": SMOKE_INST_NAME, "type": "bank"},
        cookies=session.cookies,
        timeout=timeout,
    )
    if status != 201:
        raise SmokeError(
            f"FAIL [institution-create] /api/institutions returned {status}: {body}"
        )
    payload = json.loads(body)
    return str(payload["id"])


def _create_account(
    *,
    app_url: str,
    timeout: int,
    session: SmokeSession,
    institution_id: str,
    name: str,
    initial_balance: str,
) -> str:
    status, body, _headers, _cookies = _request(
        "POST",
        f"{app_url}/api/accounts",
        json_data={
            "name": name,
            "institution_id": institution_id,
            "type": "current",
            "currency": "EGP",
            "initial_balance": initial_balance,
        },
        cookies=session.cookies,
        timeout=timeout,
    )
    if status != 201:
        raise SmokeError(
            f"FAIL [account-create] /api/accounts returned {status}: {body}"
        )
    payload = json.loads(body)
    return str(payload["id"])


def _create_budget(
    *, app_url: str, timeout: int, session: SmokeSession, category_id: str
) -> None:
    status, body, _headers, updated_cookies = _request(
        "POST",
        f"{app_url}/budgets/add",
        data={
            "csrfmiddlewaretoken": session.csrf_token,
            "category_id": category_id,
            "monthly_limit": "2000.00",
            "currency": "EGP",
        },
        cookies=session.cookies,
        headers=_csrf_headers(session.csrf_token, f"{app_url}/budgets"),
        timeout=timeout,
        allow_redirects=True,
    )
    session.cookies.update(updated_cookies)
    if status != 200 or "2000" not in body.replace(",", ""):
        raise SmokeError(
            "FAIL [budget-create] budget create flow did not render budget"
        )


def _create_transaction(
    *,
    app_url: str,
    timeout: int,
    session: SmokeSession,
    account_id: str,
    category_id: str,
    amount: str,
    note: str,
) -> None:
    status, body, _headers, updated_cookies = _request(
        "POST",
        f"{app_url}/transactions",
        data={
            "csrfmiddlewaretoken": session.csrf_token,
            "type": "expense",
            "amount": amount,
            "account_id": account_id,
            "category_id": category_id,
            "note": note,
            "date": str(timezone.localdate()),
        },
        cookies=session.cookies,
        headers={
            **_csrf_headers(session.csrf_token, f"{app_url}/transactions/new"),
            "HX-Request": "true",
        },
        timeout=timeout,
    )
    session.cookies.update(updated_cookies)
    if status != 200 or "Transaction saved!" not in body:
        raise SmokeError(f"FAIL [transaction-create] /transactions returned {status}")


def _create_transfer(
    *,
    app_url: str,
    timeout: int,
    session: SmokeSession,
    source_account_id: str,
    dest_account_id: str,
) -> None:
    status, _body, headers, updated_cookies = _request(
        "GET",
        f"{app_url}/transfers/new",
        cookies=session.cookies,
        timeout=timeout,
        allow_redirects=False,
    )
    session.cookies.update(updated_cookies)
    if status not in REDIRECT_STATUSES or "/transfer/new" not in headers.get(
        "Location", ""
    ):
        raise SmokeError(
            "FAIL [transfer-form] /transfers/new should redirect to /transfer/new"
        )

    status, body, _headers, updated_cookies = _request(
        "POST",
        f"{app_url}/transactions/transfer",
        data={
            "csrfmiddlewaretoken": session.csrf_token,
            "source_account_id": source_account_id,
            "dest_account_id": dest_account_id,
            "amount": "5000.00",
            "currency": "EGP",
            "note": SMOKE_TRANSFER_NOTE,
            "date": str(timezone.localdate()),
        },
        cookies=session.cookies,
        headers={
            **_csrf_headers(session.csrf_token, f"{app_url}/transfer/new"),
            "HX-Request": "true",
        },
        timeout=timeout,
    )
    session.cookies.update(updated_cookies)
    if status != 200 or "Transfer completed!" not in body:
        raise SmokeError("FAIL [transfer] /transactions/transfer did not succeed")


def _get_account_balance(
    *, app_url: str, timeout: int, session: SmokeSession, account_id: str
) -> Decimal:
    status, body, _headers, updated_cookies = _request(
        "GET",
        f"{app_url}/api/accounts/{account_id}",
        cookies=session.cookies,
        timeout=timeout,
    )
    session.cookies.update(updated_cookies)
    if status != 200:
        raise SmokeError(
            f"FAIL [account-fetch] /api/accounts/{account_id} returned {status}"
        )
    payload = json.loads(body)
    return Decimal(str(payload["current_balance"]))


def _check_budget_progress(
    *, app_url: str, timeout: int, session: SmokeSession
) -> None:
    status, body, _headers, updated_cookies = _request(
        "GET",
        f"{app_url}/budgets",
        cookies=session.cookies,
        timeout=timeout,
    )
    session.cookies.update(updated_cookies)
    normalized = body.replace(",", "")
    if (
        status != 200
        or "500.00" not in normalized
        or "1500.00 remaining" not in normalized
    ):
        raise SmokeError("FAIL [budget-progress] budget page missing expected usage")


def _seed_isolation_data(user: User) -> tuple[str, str]:
    institution = Institution.objects.create(
        user_id=user.id,
        name="[SMOKE] Isolation Bank",
        type="bank",
    )
    account = Account.objects.create(
        user_id=user.id,
        institution=institution,
        name="[SMOKE] Isolation Account",
        type="current",
        currency="EGP",
        current_balance=Decimal("1000.00"),
        initial_balance=Decimal("1000.00"),
    )
    category_id = _get_category_id(user.id, "Transport")
    tx = Transaction.objects.create(
        user_id=user.id,
        account=account,
        category_id=category_id,
        type="expense",
        amount=Decimal("100.00"),
        currency="EGP",
        balance_delta=Decimal("-100.00"),
        date=timezone.localdate(),
        note=SMOKE_ISOLATION_NOTE,
    )
    return str(account.id), str(tx.id)


def _check_isolation(
    *,
    app_url: str,
    timeout: int,
    session: SmokeSession,
    other_account_id: str,
    other_tx_id: str,
) -> None:
    status, body, _headers, updated_cookies = _request(
        "GET",
        f"{app_url}/transactions",
        cookies=session.cookies,
        timeout=timeout,
    )
    session.cookies.update(updated_cookies)
    if status != 200:
        raise SmokeError(f"FAIL [isolation-list] /transactions returned {status}")
    if SMOKE_ISOLATION_NOTE in body or SMOKE_NOTE not in body:
        raise SmokeError(
            "FAIL [isolation-list] transaction list leaked other user's data"
        )

    status, _body, _headers, updated_cookies = _request(
        "GET",
        f"{app_url}/api/transactions/{other_tx_id}",
        cookies=session.cookies,
        timeout=timeout,
        allow_redirects=False,
    )
    session.cookies.update(updated_cookies)
    if status != 404:
        raise SmokeError(
            f"FAIL [isolation-tx-detail] expected 404 for other tx, got {status}"
        )

    status, _body, _headers, updated_cookies = _request(
        "GET",
        f"{app_url}/accounts/{other_account_id}",
        cookies=session.cookies,
        timeout=timeout,
        allow_redirects=False,
    )
    session.cookies.update(updated_cookies)
    if status != 404:
        raise SmokeError(
            f"FAIL [isolation-account-detail] expected 404 for other account, got {status}"
        )


def _csrf_headers(csrf_token: str, referer: str) -> dict[str, str]:
    return {
        "X-CSRFToken": csrf_token,
        "Referer": referer,
    }


def _request(
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    allow_redirects: bool = True,
) -> tuple[int, str, dict[str, str], dict[str, str]]:
    if data is not None and json_data is not None:
        raise ValueError("data and json_data are mutually exclusive")

    cookie_state = dict(cookies or {})
    current_method = method.upper()
    current_url = url
    payload: bytes | None = _encode_body(data=data, json_data=json_data)
    request_headers = dict(headers or {})
    if json_data is not None:
        request_headers.setdefault("Content-Type", "application/json")
    elif data is not None:
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    opener = urllib.request.build_opener(NoRedirectHandler())

    for _ in range(MAX_REDIRECTS):
        merged_headers = dict(request_headers)
        if cookie_state:
            merged_headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in cookie_state.items()
            )
        request = urllib.request.Request(
            current_url,
            data=payload,
            headers=merged_headers,
            method=current_method,
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                status = response.getcode()
                body = response.read().decode("utf-8", errors="replace")
                response_headers = dict(response.headers.items())
                response_cookies = _parse_response_cookies(response.headers)
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8", errors="replace")
            response_headers = dict(exc.headers.items())
            response_cookies = _parse_response_cookies(exc.headers)
        except urllib.error.URLError as exc:
            raise SmokeError(
                f"FAIL [http] {current_method} {current_url} failed: {exc.reason}"
            ) from exc

        cookie_state.update(response_cookies)
        location = response_headers.get("Location", "")
        if allow_redirects and status in REDIRECT_STATUSES and location:
            current_url = urllib.parse.urljoin(current_url, location)
            if status == 303 or (
                status in {301, 302} and current_method not in {"GET", "HEAD"}
            ):
                current_method = "GET"
                payload = None
            continue
        return status, body, response_headers, cookie_state

    raise SmokeError(f"FAIL [http] Too many redirects for {url}")


def _encode_body(
    *, data: dict[str, Any] | None, json_data: dict[str, Any] | None
) -> bytes | None:
    if json_data is not None:
        return json.dumps(json_data).encode("utf-8")
    if data is not None:
        return urllib.parse.urlencode(data).encode("utf-8")
    return None


def _parse_response_cookies(headers: Any) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_cookie in headers.get_all("Set-Cookie", []):
        cookie = SimpleCookie()
        cookie.load(raw_cookie)
        for key, morsel in cookie.items():
            parsed[key] = morsel.value
    return parsed
