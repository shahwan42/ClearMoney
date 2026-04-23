"""Migration tests for generalized person currency balances."""

from __future__ import annotations

import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_backfill_person_currency_balances_from_legacy_fields():
    executor = MigrationExecutor(connection)
    migrate_from = [("people", "0002_retarget_user_fk")]
    migrate_to = [("people", "0003_personcurrencybalance")]

    executor.migrate(migrate_from)
    old_apps = executor.loader.project_state(migrate_from).apps

    Person = old_apps.get_model("people", "Person")

    user_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "users" ("id", "email", "language") VALUES (%s, %s, %s)',
            [user_id, f"migration-{uuid.uuid4().hex}@example.com", "en"],
        )
        cursor.execute(
            """
            INSERT INTO "currencies" ("code", "name", "symbol", "is_enabled", "display_order")
            VALUES
                ('EGP', 'Egyptian Pound', 'EGP', TRUE, 0),
                ('USD', 'US Dollar', '$', TRUE, 1)
            ON CONFLICT ("code") DO NOTHING
            """
        )
    person = Person.objects.create(
        user_id=user_id,
        name="Legacy Balance",
        net_balance=175,
        net_balance_egp=250,
        net_balance_usd=-75,
    )

    executor = MigrationExecutor(connection)
    executor.migrate(migrate_to)
    new_apps = executor.loader.project_state(migrate_to).apps
    PersonCurrencyBalance = new_apps.get_model("people", "PersonCurrencyBalance")

    balances = {
        row.currency_id: float(row.balance)
        for row in PersonCurrencyBalance.objects.filter(person_id=person.id)
    }

    assert balances == {"EGP": 250.0, "USD": -75.0}
