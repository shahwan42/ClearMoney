"""Seed default EGP fee presets (InstaPay, ATM) for all existing users.

Idempotent: skips users that already have a preset with the same name+currency.
"""

from decimal import Decimal
from typing import Any

from django.db import migrations

DEFAULTS = [
    {
        "name": "InstaPay",
        "currency": "EGP",
        "calc_type": "percent",
        "value": Decimal("0.001"),
        "min_fee": Decimal("0.50"),
        "max_fee": Decimal("20.00"),
        "sort_order": 1,
    },
    {
        "name": "ATM",
        "currency": "EGP",
        "calc_type": "flat",
        "value": Decimal("5.00"),
        "min_fee": None,
        "max_fee": None,
        "sort_order": 2,
    },
]


def seed_existing_users(apps: Any, schema_editor: Any) -> None:
    User = apps.get_model("auth_app", "User")
    FeePreset = apps.get_model("fee_presets", "FeePreset")
    for user in User.objects.all().iterator():
        for spec in DEFAULTS:
            FeePreset.objects.get_or_create(
                user_id=user.id,
                name=spec["name"],
                currency=spec["currency"],
                defaults={
                    "calc_type": spec["calc_type"],
                    "value": spec["value"],
                    "min_fee": spec["min_fee"],
                    "max_fee": spec["max_fee"],
                    "sort_order": spec["sort_order"],
                },
            )


def noop_reverse(apps: Any, schema_editor: Any) -> None:
    """Do not delete user data on rollback."""


class Migration(migrations.Migration):
    dependencies = [
        ("fee_presets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_existing_users, noop_reverse),
    ]
