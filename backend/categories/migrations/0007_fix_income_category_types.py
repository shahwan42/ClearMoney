"""Data migration: set type='income' on system income categories for all users."""

from typing import Any

from django.db import migrations

INCOME_CATEGORY_NAMES = {
    "Salary",
    "Freelance",
    "Investment Returns",
    "Refund",
    "Loan Repayment Received",
}


def fix_income_types(apps: Any, schema_editor: Any) -> None:
    Category = apps.get_model("categories", "Category")
    for name in INCOME_CATEGORY_NAMES:
        Category.objects.filter(
            name__en=name,
            is_system=True,
            type="expense",
        ).update(type="income")


def reverse_income_types(apps: Any, schema_editor: Any) -> None:
    Category = apps.get_model("categories", "Category")
    Category.objects.filter(
        is_system=True,
        type="income",
    ).update(type="expense")


class Migration(migrations.Migration):
    dependencies = [
        ("categories", "0006_alter_category_name"),
    ]

    operations = [
        migrations.RunPython(fix_income_types, reverse_code=reverse_income_types),
    ]
