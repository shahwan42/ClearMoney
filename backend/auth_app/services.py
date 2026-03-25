"""
Auth services — magic link authentication and email sending.

Handles token generation, rate limiting, session management, and
category seeding for new users.

Like Django's django-sesame with custom rate limiting, or Laravel's
Auth + PasswordBroker combined for magic links.
"""

import logging
import os
import secrets
from datetime import timedelta
from enum import IntEnum

from django.utils import timezone

from core.models import AuthToken, Category, Session, User

logger = logging.getLogger(__name__)

# --- Constants ---

SESSION_COOKIE_NAME = "clearmoney_session"
SESSION_MAX_AGE = timedelta(days=30)
SESSION_MAX_AGE_SECONDS = int(SESSION_MAX_AGE.total_seconds())
TOKEN_TTL_MINUTES = 15
EMAIL_COOLDOWN_MINUTES = 5
MAX_DAILY_PER_EMAIL = 3


class SendResult(IntEnum):
    """Outcome of a magic link request."""

    SENT = 0
    REUSED = 1
    COOLDOWN = 2
    DAILY_LIMIT = 3
    GLOBAL_CAP = 4
    SKIPPED = 5


def rate_limit_message(result: SendResult) -> str:
    """Return a user-facing message for a non-sent result."""
    messages = {
        SendResult.REUSED: (
            "A sign-in link was already sent. Please check your inbox."
        ),
        SendResult.COOLDOWN: (
            "Please wait a few minutes before requesting another link."
        ),
        SendResult.DAILY_LIMIT: (
            "You've reached the daily limit for sign-in links. "
            "Please try again tomorrow."
        ),
        SendResult.GLOBAL_CAP: (
            "Our email system is temporarily at capacity. Please try again later."
        ),
    }
    return messages.get(result, "Please try again later.")


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------


class EmailService:
    """Sends magic link emails via Resend API.

    Dev mode (no API key) logs emails to stdout instead of sending.
    Like Laravel's Mail::to()->send() with a configurable driver (smtp, log).
    """

    def __init__(self, api_key: str, from_addr: str, app_url: str) -> None:
        self.from_addr = from_addr
        self.app_url = app_url.rstrip("/")
        self.dev_mode = not api_key
        self._client: object | None = None

        if self.dev_mode:
            logger.warning(
                "email service running in dev mode "
                "(no RESEND_API_KEY) — emails will be logged, not sent"
            )
        else:
            import resend

            resend.api_key = api_key
            self._client = resend

    def link_url(self, token: str) -> str:
        """Return the full magic link URL for a given token."""
        return f"{self.app_url}/auth/verify?token={token}"

    def send_magic_link(self, to: str, token: str) -> None:
        """Send a magic link email to the given address."""
        link = self.link_url(token)

        subject = "Sign in to ClearMoney"
        html = (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, '
            "'Segoe UI', Roboto, sans-serif; max-width: 480px; "
            'margin: 0 auto; padding: 40px 20px;">'
            '<h2 style="color: #0d9488; margin-bottom: 24px;">ClearMoney</h2>'
            '<p style="color: #334155; font-size: 16px; line-height: 1.5;">'
            "Click the button below to sign in to your account. "
            "This link expires in 15 minutes.</p>"
            '<div style="margin: 32px 0;">'
            f'<a href="{link}" style="background-color: #0d9488; '
            "color: white; padding: 14px 32px; text-decoration: none; "
            "border-radius: 8px; font-size: 16px; font-weight: 600; "
            'display: inline-block;">Sign in to ClearMoney</a>'
            "</div>"
            '<p style="color: #94a3b8; font-size: 14px; line-height: 1.5;">'
            "If you didn't request this link, you can safely ignore "
            "this email.</p>"
            '<p style="color: #cbd5e1; font-size: 12px; margin-top: 32px;">'
            "If the button doesn't work, copy and paste this URL into "
            f"your browser:<br>{link}</p>"
            "</div>"
        )

        if self.dev_mode:
            logger.info(
                "magic link email (dev mode — not sent) to=%s link=%s",
                to,
                link,
            )
            return

        import resend

        resend.Emails.send(
            {
                "from": self.from_addr,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )
        logger.info("magic link email sent to=%s", to)


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------


class AuthService:
    """Handles magic-link authentication, sessions, and rate limiting.

    All DB access uses Django ORM via core.models.
    """

    def __init__(
        self,
        email_service: EmailService,
        max_daily_emails: int = 50,
    ) -> None:
        self.email_svc = email_service
        self.max_daily_emails = max_daily_emails if max_daily_emails > 0 else 50

    def request_login_link(self, email: str) -> tuple[SendResult, str | None]:
        """Send a magic link to an existing user's email.

        Returns (SendResult, error_message). Non-SENT results are not errors —
        the caller should still show "Check your email" (prevent enumeration).
        """
        email = email.strip().lower()
        if not email:
            return SendResult.SKIPPED, "Email is required"

        # Only send to existing users (prevent enumeration)
        if not User.objects.filter(email__iexact=email).exists():
            logger.info(
                "login request for unknown email (no email sent) email=%s",
                email,
            )
            return SendResult.SKIPPED, None

        return self._send_magic_link(email, "login")

    def request_registration_link(self, email: str) -> tuple[SendResult, str | None]:
        """Send a magic link for a new user registration.

        Returns an error message if the email is already registered.
        """
        email = email.strip().lower()
        if not email:
            return SendResult.SKIPPED, "Email is required"

        # Reject if already registered
        if User.objects.filter(email__iexact=email).exists():
            return (
                SendResult.SKIPPED,
                "An account with this email already exists",
            )

        return self._send_magic_link(email, "registration")

    def _send_magic_link(
        self, email: str, purpose: str
    ) -> tuple[SendResult, str | None]:
        """Shared logic for login + registration link requests."""
        now = timezone.now()

        # Token reuse: if an unexpired token exists, don't send a new email
        existing = AuthToken.objects.filter(
            email__iexact=email,
            purpose=purpose,
            used=False,
            expires_at__gt=now,
        ).first()
        if existing:
            if self.email_svc.dev_mode:
                logger.info(
                    "reusing existing token (dev mode) email=%s link=%s",
                    email,
                    self.email_svc.link_url(existing.token),
                )
            else:
                logger.info(
                    "reusing existing token (no email sent) email=%s purpose=%s",
                    email,
                    purpose,
                )
            return SendResult.REUSED, None

        # Per-email cooldown: 1 per 5 minutes
        cooldown_cutoff = now - timedelta(minutes=EMAIL_COOLDOWN_MINUTES)
        recent_count = AuthToken.objects.filter(
            email__iexact=email,
            created_at__gte=cooldown_cutoff,
        ).count()
        if recent_count > 0:
            logger.warning("email cooldown active (no email sent) email=%s", email)
            return SendResult.COOLDOWN, None

        # Per-email daily limit: 3 per day
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = AuthToken.objects.filter(
            email__iexact=email,
            created_at__gte=day_start,
        ).count()
        if daily_count >= MAX_DAILY_PER_EMAIL:
            logger.warning(
                "daily per-email limit reached (no email sent) email=%s count=%d",
                email,
                daily_count,
            )
            return SendResult.DAILY_LIMIT, None

        # Global daily cap
        global_count = AuthToken.objects.filter(
            created_at__gte=day_start,
        ).count()
        if global_count >= self.max_daily_emails:
            logger.error(
                "global daily email cap reached count=%d max=%d",
                global_count,
                self.max_daily_emails,
            )
            return SendResult.GLOBAL_CAP, None

        # Generate token
        token = secrets.token_urlsafe(32)

        # Store token in DB
        AuthToken.objects.create(
            email=email.lower(),
            token=token,
            purpose=purpose,
            expires_at=now + timedelta(minutes=TOKEN_TTL_MINUTES),
        )

        # Send email
        self.email_svc.send_magic_link(email, token)

        logger.info("auth.magic_link_sent email=%s purpose=%s", email, purpose)
        return SendResult.SENT, None

    def verify_magic_link(
        self, token: str
    ) -> tuple[dict[str, str | bool] | None, str | None]:
        """Validate a magic link token and create a session.

        Returns (result_dict, error_message).
        result_dict has keys: session_token, user_id, is_new_user.
        """
        token = token.strip()
        if not token:
            return None, "Token is required"

        # Look up token
        try:
            at = AuthToken.objects.get(token=token)
        except AuthToken.DoesNotExist:
            return None, "Invalid or expired link"

        # Check if already used
        if at.used:
            return None, "This link has already been used"

        # Check expiry
        if timezone.now() > at.expires_at:
            return None, "This link has expired"

        # Mark as used immediately (single-use)
        AuthToken.objects.filter(id=at.id).update(used=True)

        user_id: str
        is_new_user = False

        if at.purpose == "login":
            try:
                user = User.objects.get(email__iexact=at.email)
            except User.DoesNotExist:
                return None, "User not found"
            user_id = str(user.id)

        elif at.purpose == "registration":
            user = User.objects.create(email=at.email.lower())
            user_id = str(user.id)
            is_new_user = True

            # Seed default categories
            self._seed_default_categories(user_id)
            logger.info("auth.user_registered email=%s", at.email)

        else:
            return None, f"Unknown token purpose: {at.purpose}"

        # Create session
        session_token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + SESSION_MAX_AGE

        Session.objects.create(
            user_id=user_id,
            token=session_token,
            expires_at=expires_at,
        )

        logger.info("auth.login_success purpose=%s", at.purpose)

        return {
            "session_token": session_token,
            "user_id": user_id,
            "is_new_user": is_new_user,
        }, None

    def logout(self, token: str) -> None:
        """Delete session by token (server-side logout)."""
        deleted, _ = Session.objects.filter(token=token).delete()
        if deleted:
            logger.info("auth.logout")
        else:
            logger.warning("auth.logout session not found")

    def _seed_default_categories(self, user_id: str) -> None:
        """Insert default categories for a new user.

        Categories are type-agnostic — all stored as type='expense'.
        Any category can be used with any transaction type.
        """
        defaults = [
            # (name, icon, display_order)
            ("Household", "\U0001f3e0", 1),
            ("Food & Groceries", "\U0001f6d2", 2),
            ("Transport", "\U0001f697", 3),
            ("Health", "\U0001f3e5", 4),
            ("Education", "\U0001f4da", 5),
            ("Mobile", "\U0001f4f1", 6),
            ("Electricity", "\u26a1", 7),
            ("Gas", "\U0001f525", 8),
            ("Internet", "\U0001f310", 9),
            ("Gifts", "\U0001f381", 10),
            ("Entertainment", "\U0001f3ac", 11),
            ("Shopping", "\U0001f6cd\ufe0f", 12),
            ("Subscriptions", "\U0001f4fa", 13),
            ("Virtual Fund", "\U0001f3e6", 14),
            ("Insurance", "\U0001f6e1\ufe0f", 15),
            ("Fees & Charges", "\U0001f4b3", 16),
            ("Debt Payment", "\U0001f4b0", 17),
            ("Salary", "\U0001f4b5", 18),
            ("Freelance", "\U0001f4bb", 19),
            ("Investment Returns", "\U0001f4c8", 20),
            ("Refund", "\U0001f504", 21),
            ("Loan Repayment Received", "\U0001f91d", 22),
            ("Other", "\U0001f516", 23),
        ]
        try:
            for name, icon, order in defaults:
                Category.objects.create(
                    user_id=user_id,
                    name=name,
                    type="expense",
                    icon=icon,
                    is_system=True,
                    display_order=order,
                )
        except Exception:
            logger.exception(
                "failed to seed categories for new user user_id=%s", user_id
            )
            # Non-fatal: user can still use the app


# ---------------------------------------------------------------------------
# Module-level singleton — instantiated from environment variables
# ---------------------------------------------------------------------------

_email_service = EmailService(
    api_key=os.environ.get("RESEND_API_KEY", ""),
    from_addr=os.environ.get("EMAIL_FROM", "noreply@clearmoney.app"),
    app_url=os.environ.get("APP_URL", "http://localhost:8000"),
)

auth_service = AuthService(
    email_service=_email_service,
    max_daily_emails=int(os.environ.get("MAX_DAILY_EMAILS", "50")),
)
