"""
Management command: qa_seed

Seeds a standard set of test data for a QA user.
Idempotent — safe to run multiple times; uses get_or_create.

Usage:
    python manage.py qa_seed --email qa@clearmoney.app
    make qa-seed EMAIL=qa@clearmoney.app
"""

from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Account, Institution
from auth_app.models import User
from budgets.services import BudgetService
from categories.models import Category
from transactions.services import TransactionService


class Command(BaseCommand):
    help = "Seed standard QA test data for a given user (idempotent)."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(
            "--email",
            default="qa@clearmoney.app",
            help="Email of the user to seed data for (default: qa@clearmoney.app)",
        )

    def handle(self, *args: object, **options: object) -> None:
        email: str = options["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(
                f"User {email!r} not found. Run `make qa-user EMAIL={email}` first."
            )

        uid = str(user.id)
        tz = ZoneInfo("Africa/Cairo")
        today = date.today()

        self.stdout.write(f"Seeding QA data for {email}...")

        # ── Institution ──────────────────────────────────────────────────────
        inst, created = Institution.objects.get_or_create(
            user_id=uid,
            name="QA Test Bank",
            defaults={"color": "#10b981"},
        )
        self.stdout.write(f"  Institution: {inst.name} ({'created' if created else 'exists'})")

        # ── Accounts ─────────────────────────────────────────────────────────
        egp1, _ = Account.objects.get_or_create(
            user_id=uid,
            name="Main Checking EGP",
            defaults={
                "institution": inst,
                "type": "current",
                "currency": "EGP",
                "current_balance": Decimal("10000.00"),
                "initial_balance": Decimal("10000.00"),
            },
        )
        egp2, _ = Account.objects.get_or_create(
            user_id=uid,
            name="Savings EGP",
            defaults={
                "institution": inst,
                "type": "savings",
                "currency": "EGP",
                "current_balance": Decimal("0.00"),
                "initial_balance": Decimal("0.00"),
            },
        )
        usd, _ = Account.objects.get_or_create(
            user_id=uid,
            name="USD Account",
            defaults={
                "institution": inst,
                "type": "current",
                "currency": "USD",
                "current_balance": Decimal("500.00"),
                "initial_balance": Decimal("500.00"),
            },
        )
        cc, _ = Account.objects.get_or_create(
            user_id=uid,
            name="Credit Card EGP",
            defaults={
                "institution": inst,
                "type": "credit_card",
                "currency": "EGP",
                "current_balance": Decimal("-2000.00"),
                "initial_balance": Decimal("0.00"),
                "credit_limit": Decimal("20000.00"),
            },
        )
        self.stdout.write(
            f"  Accounts: {egp1.name} ({egp1.current_balance}), "
            f"{egp2.name} ({egp2.current_balance}), "
            f"{usd.name} ({usd.current_balance}), "
            f"{cc.name} ({cc.current_balance})"
        )

        # ── Categories (by name, from seeded defaults) ───────────────────────
        def get_cat(name_en: str) -> str | None:
            for cat in Category.objects.filter(user_id=uid):
                n = cat.name
                label = n.get("en", "") if isinstance(n, dict) else str(n)
                if name_en.lower() in label.lower():
                    return str(cat.id)
            return None

        food_id = get_cat("Food")
        transport_id = get_cat("Transport")
        salary_id = get_cat("Salary")

        if not food_id or not transport_id or not salary_id:
            self.stdout.write(self.style.WARNING(
                "  Warning: some categories not found — skipping transactions/budgets. "
                "Categories are seeded during user registration."
            ))
            return

        # ── Transactions ─────────────────────────────────────────────────────
        svc = TransactionService(uid, tz)
        existing_notes = set(
            Transaction.objects.filter(user_id=uid).values_list("note", flat=True)
        )

        tx_data = [
            {"account_id": str(egp1.id), "type": "income", "amount": Decimal("5000.00"),
             "category_id": salary_id, "note": "Monthly salary April", "date": today, "tags": []},
            {"account_id": str(egp1.id), "type": "expense", "amount": Decimal("500.00"),
             "category_id": food_id, "note": "Grocery shopping", "date": today, "tags": []},
            {"account_id": str(egp1.id), "type": "expense", "amount": Decimal("200.00"),
             "category_id": transport_id, "note": "Uber rides", "date": today, "tags": []},
            {"account_id": str(egp1.id), "type": "expense", "amount": Decimal("1000.00"),
             "category_id": food_id, "note": "Restaurant dinner", "date": today, "tags": []},
        ]

        tx_count = 0
        for data in tx_data:
            if data["note"] not in existing_notes:
                svc.create(data)
                tx_count += 1

        self.stdout.write(f"  Transactions: {tx_count} created (skipped {len(tx_data) - tx_count} existing)")

        # ── Budgets ───────────────────────────────────────────────────────────
        bsvc = BudgetService(uid, tz)
        from budgets.models import Budget

        budget_data = [
            (food_id, 3000.0, "EGP"),
            (transport_id, 500.0, "EGP"),
        ]
        budget_count = 0
        for cat_id, limit, currency in budget_data:
            exists = Budget.objects.filter(
                user_id=uid,
                category_id=cat_id,
                currency=currency,
                month=today.replace(day=1),
            ).exists()
            if not exists:
                bsvc.create(cat_id, limit, currency)
                budget_count += 1

        self.stdout.write(f"  Budgets: {budget_count} created")
        self.stdout.write(self.style.SUCCESS(f"\nQA seed complete for {email}"))
        self.stdout.write(
            f"  → Login: make qa-login EMAIL={email}\n"
            f"  → App:   http://localhost:8000/"
        )


# Lazy import inside handle to avoid circular imports at module load
from transactions.models import Transaction  # noqa: E402
