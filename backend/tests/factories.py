"""
Central factory_boy factories for all Django models.

Like Laravel's database/factories/ directory — one factory per model,
importable by any app's test file.

Usage:
    from tests.factories import UserFactory, AccountFactory
    user = UserFactory()
    account = AccountFactory(user_id=user.id)

See conftest.py for the auth_user / auth_client fixtures that wrap UserFactory
+ SessionFactory into ready-to-use pytest fixtures.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import factory
from django.utils import timezone

from accounts.models import Account, AccountSnapshot, Institution
from auth_app.models import (
    AuthToken,
    Currency,
    HistoricalSnapshot,
    Session,
    User,
    UserConfig,
    UserCurrencyPreference,
)
from budgets.models import Budget
from categories.models import Category
from exchange_rates.models import ExchangeRateLog
from investments.models import Investment
from people.models import Person, PersonCurrencyBalance
from recurring.models import RecurringRule
from transactions.models import Transaction, VirtualAccountAllocation
from virtual_accounts.models import VirtualAccount
from fee_presets.models import FeePreset


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for the users table. Generates a unique email per instance."""

    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyFunction(lambda: f"pytest-{uuid.uuid4().hex[:8]}@example.com")
    language = "en"


class SessionFactory(factory.django.DjangoModelFactory):
    """Factory for the sessions table — creates a valid 30-day session."""

    class Meta:
        model = Session

    id = factory.LazyFunction(uuid.uuid4)
    user = factory.SubFactory(UserFactory)
    token = factory.LazyFunction(lambda: str(uuid.uuid4()))
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))


class AuthTokenFactory(factory.django.DjangoModelFactory):
    """Factory for the auth_tokens table — creates a valid magic link token."""

    class Meta:
        model = AuthToken

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyFunction(lambda: f"pytest-{uuid.uuid4().hex[:8]}@example.com")
    token = factory.LazyFunction(lambda: str(uuid.uuid4()))
    purpose = "login"
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))
    used = False


class InstitutionFactory(factory.django.DjangoModelFactory):
    """Factory for the institutions table.

    user_id must be passed in: InstitutionFactory(user_id=user.id)
    """

    class Meta:
        model = Institution

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)  # override with real user_id in tests
    name = factory.Sequence(lambda n: f"Test Bank {n}")
    type = "bank"
    color = "#0d9488"
    display_order = factory.Sequence(lambda n: n)


class AccountFactory(factory.django.DjangoModelFactory):
    """Factory for the accounts table.

    user_id must be passed in: AccountFactory(user_id=user.id)
    institution_id is optional (None = cash/wallet account).
    """

    class Meta:
        model = Account

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)  # override with real user_id in tests
    institution_id = None  # no institution by default — like a cash account
    name = factory.Sequence(lambda n: f"Test Account {n}")
    type = "savings"
    currency = "EGP"
    current_balance = 0
    initial_balance = 0
    is_dormant = False
    display_order = factory.Sequence(lambda n: n)


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for the categories table.

    user_id must be passed in: CategoryFactory(user_id=user.id)
    """

    class Meta:
        model = Category

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)  # override with real user_id in tests
    name = factory.Sequence(lambda n: {"en": f"Category {n}"})
    type = "expense"


class TransactionFactory(factory.django.DjangoModelFactory):
    """Factory for the transactions table.

    user_id and account_id must be passed in.
    """

    class Meta:
        model = Transaction

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)  # override with real user_id
    account_id = factory.LazyFunction(uuid.uuid4)  # override with real account_id
    type = "expense"
    amount = 100
    currency = "EGP"
    date = factory.LazyFunction(lambda: timezone.now().date())
    balance_delta = -100

    @factory.post_generation
    def tags(self, create: bool, extracted: list[str], **kwargs: Any) -> None:
        if not create or not extracted:
            return

        from transactions.models import Tag

        for name in extracted:
            tag, _ = Tag.objects.get_or_create(
                user_id=self.user_id, name=name, defaults={"color": "#64748b"}
            )
            self.tags.add(tag)


class BudgetFactory(factory.django.DjangoModelFactory):
    """Factory for the budgets table.

    user_id and category_id must be passed in.
    """

    class Meta:
        model = Budget

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    category_id = factory.LazyFunction(uuid.uuid4)
    monthly_limit = 1000
    currency = "EGP"
    is_active = True


class TotalBudgetFactory(factory.django.DjangoModelFactory):
    """Factory for the total_budgets table.

    user_id must be passed in.
    """

    class Meta:
        model = "budgets.TotalBudget"

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    monthly_limit = Decimal("15000")
    currency = "EGP"
    is_active = True


class VirtualAccountFactory(factory.django.DjangoModelFactory):
    """Factory for the virtual_accounts table.

    user_id must be passed in.
    """

    class Meta:
        model = VirtualAccount

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Virtual Account {n}")
    current_balance = 0
    icon = "💰"
    color = "#0d9488"
    is_archived = False
    exclude_from_net_worth = False
    display_order = factory.Sequence(lambda n: n)


class VirtualAccountAllocationFactory(factory.django.DjangoModelFactory):
    """Factory for virtual_account_allocations.

    virtual_account_id must be passed in.
    """

    class Meta:
        model = VirtualAccountAllocation

    id = factory.LazyFunction(uuid.uuid4)
    virtual_account_id = factory.LazyFunction(uuid.uuid4)
    amount = 100


class InvestmentFactory(factory.django.DjangoModelFactory):
    """Factory for the investments table."""

    class Meta:
        model = Investment

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    platform = "Thndr"
    fund_name = factory.Sequence(lambda n: f"Fund {n}")
    units = 100
    last_unit_price = 1
    currency = "EGP"
    last_updated = factory.LazyFunction(timezone.now)


class RecurringRuleFactory(factory.django.DjangoModelFactory):
    """Factory for the recurring_rules table."""

    class Meta:
        model = RecurringRule

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    template_transaction = {
        "type": "expense",
        "amount": 100,
        "currency": "EGP",
        "account_id": str(uuid.uuid4()),
    }
    frequency = "monthly"
    day_of_month = 1
    next_due_date = factory.LazyFunction(lambda: timezone.now().date())
    is_active = True
    auto_confirm = False


class PersonFactory(factory.django.DjangoModelFactory):
    """Factory for the persons table.

    user_id must be passed in: PersonFactory(user_id=user.id)
    """

    class Meta:
        model = Person

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)  # override with real user_id in tests
    name = factory.Sequence(lambda n: f"Person {n}")


class UserConfigFactory(factory.django.DjangoModelFactory):
    """Factory for legacy user_config table (brute-force protection)."""

    class Meta:
        model = UserConfig

    id = factory.LazyFunction(uuid.uuid4)


class CurrencyFactory(factory.django.DjangoModelFactory):
    """Factory for supported currency registry entries."""

    class Meta:
        model = Currency
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"X{n:02d}"[-3:])
    name = factory.Sequence(lambda n: f"Currency {n}")
    symbol = ""
    is_enabled = True
    display_order = factory.Sequence(int)


class UserCurrencyPreferenceFactory(factory.django.DjangoModelFactory):
    """Factory for per-user currency preferences."""

    class Meta:
        model = UserCurrencyPreference

    user = factory.SubFactory(UserFactory)
    active_currency_codes = ["EGP"]
    selected_display_currency = "EGP"


class PersonCurrencyBalanceFactory(factory.django.DjangoModelFactory):
    """Factory for per-person-per-currency balances."""

    class Meta:
        model = PersonCurrencyBalance

    id = factory.LazyFunction(uuid.uuid4)
    person = factory.SubFactory(PersonFactory)
    currency = factory.SubFactory(CurrencyFactory, code="EGP")
    balance = 0


class HistoricalSnapshotFactory(factory.django.DjangoModelFactory):
    """Factory for per-currency historical snapshots."""

    class Meta:
        model = HistoricalSnapshot

    id = factory.LazyFunction(uuid.uuid4)
    user = factory.SubFactory(UserFactory)
    date = factory.LazyFunction(lambda: timezone.now().date())
    currency = "EGP"
    net_worth = factory.LazyFunction(lambda: Decimal("50000.00"))
    daily_spending = factory.LazyFunction(lambda: Decimal("250.00"))
    daily_income = factory.LazyFunction(lambda: Decimal("0.00"))


class AccountSnapshotFactory(factory.django.DjangoModelFactory):
    """Factory for per-account daily balance snapshots."""

    class Meta:
        model = AccountSnapshot

    id = factory.LazyFunction(uuid.uuid4)
    user = factory.SubFactory(UserFactory)
    date = factory.LazyFunction(lambda: timezone.now().date())
    account = factory.SubFactory(AccountFactory)
    balance = factory.LazyFunction(lambda: Decimal("10000.00"))


class ExchangeRateLogFactory(factory.django.DjangoModelFactory):
    """Factory for exchange rate log entries (global, no user_id)."""

    class Meta:
        model = ExchangeRateLog

    id = factory.LazyFunction(uuid.uuid4)
    date = factory.LazyFunction(lambda: timezone.now().date())
    rate = factory.Sequence(
        lambda n: Decimal("50.00") + Decimal(str(n)) * Decimal("0.10")
    )
    source = "test"
    note = ""


class FeePresetFactory(factory.django.DjangoModelFactory):
    """Factory for fee_presets table.

    user_id must be passed in: FeePresetFactory(user_id=user.id)
    """

    class Meta:
        model = FeePreset

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)  # override with real user_id in tests
    name = factory.Sequence(lambda n: f"Fee Preset {n}")
    currency = "EGP"
    calc_type = "flat"
    value = Decimal("5.00")
    min_fee = None
    max_fee = None
    archived = False
    sort_order = 0
