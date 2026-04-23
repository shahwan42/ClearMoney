import uuid
from typing import Any

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models


def backfill_person_currency_balances(apps: Any, schema_editor: Any) -> None:
    """Seed generalized balance rows from legacy EGP/USD columns."""
    Currency = apps.get_model("auth_app", "Currency")
    Person = apps.get_model("people", "Person")
    PersonCurrencyBalance = apps.get_model("people", "PersonCurrencyBalance")

    for code, name, symbol, display_order in (
        ("EGP", "Egyptian Pound", "EGP", 0),
        ("USD", "US Dollar", "$", 1),
    ):
        Currency.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "symbol": symbol,
                "is_enabled": True,
                "display_order": display_order,
            },
        )

    batch: list[Any] = []
    for person in Person.objects.all().only("id", "net_balance_egp", "net_balance_usd"):
        if person.net_balance_egp != 0:
            batch.append(
                PersonCurrencyBalance(
                    person_id=person.id,
                    currency_id="EGP",
                    balance=person.net_balance_egp,
                )
            )
        if person.net_balance_usd != 0:
            batch.append(
                PersonCurrencyBalance(
                    person_id=person.id,
                    currency_id="USD",
                    balance=person.net_balance_usd,
                )
            )
    if batch:
        PersonCurrencyBalance.objects.bulk_create(batch)


class Migration(migrations.Migration):
    dependencies = [
        ("auth_app", "0007_currency_registry_and_preferences"),
        ("people", "0002_retarget_user_fk"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonCurrencyBalance",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_default=models.Func(function="gen_random_uuid"),
                        default=uuid.uuid4,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "balance",
                    models.DecimalField(
                        db_default=0, decimal_places=2, default=0, max_digits=15
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_default=django.db.models.functions.datetime.Now(),
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        db_default=django.db.models.functions.datetime.Now(),
                    ),
                ),
                (
                    "currency",
                    models.ForeignKey(
                        db_column="currency_code",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="person_balances",
                        to="auth_app.currency",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        db_column="person_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="currency_balances",
                        to="people.person",
                    ),
                ),
            ],
            options={
                "db_table": "person_currency_balances",
                "ordering": ["currency_id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("person", "currency"),
                        name="person_currency_balances_person_currency_unique",
                    )
                ],
            },
        ),
        migrations.RunPython(
            backfill_person_currency_balances,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
