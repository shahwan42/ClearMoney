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

import factory
from django.utils import timezone

from core.models import (
    Account,
    AuthToken,
    Budget,
    Category,
    InstallmentPlan,
    Institution,
    Investment,
    Person,
    RecurringRule,
    Session,
    Transaction,
    User,
    VirtualAccount,
    VirtualAccountAllocation,
)


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for the users table. Generates a unique email per instance."""

    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyFunction(lambda: f"pytest-{uuid.uuid4().hex[:8]}@example.com")


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
    name = factory.Sequence(lambda n: f"Category {n}")
    type = "expense"


class TransactionFactory(factory.django.DjangoModelFactory):
    """Factory for the transactions table.

    user_id and account_id must be passed in.
    """

    class Meta:
        model = Transaction

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)   # override with real user_id
    account_id = factory.LazyFunction(uuid.uuid4)  # override with real account_id
    type = "expense"
    amount = 100
    currency = "EGP"
    date = factory.LazyFunction(lambda: timezone.now().date())
    balance_delta = -100


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


class InstallmentPlanFactory(factory.django.DjangoModelFactory):
    """Factory for the installment_plans table."""

    class Meta:
        model = InstallmentPlan

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    account_id = factory.LazyFunction(uuid.uuid4)
    description = factory.Sequence(lambda n: f"Plan {n}")
    total_amount = 12000
    num_installments = 12
    monthly_amount = 1000
    start_date = factory.LazyFunction(lambda: timezone.now().date())
    remaining_installments = 12


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
    net_balance = 0
    net_balance_egp = 0
    net_balance_usd = 0
