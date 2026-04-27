"""Data migration: rename system 'Gas' category to 'Fuel' (⛽, وقود)."""

from django.db import migrations


def rename_gas_to_fuel(apps: object, schema_editor: object) -> None:
    Category = apps.get_model("categories", "Category")  # type: ignore[attr-defined]
    Category.objects.filter(
        name__en="Gas",
        is_system=True,
    ).update(
        name={"en": "Fuel", "ar": "وقود"},
        icon="⛽",
    )


def rename_fuel_to_gas(apps: object, schema_editor: object) -> None:
    Category = apps.get_model("categories", "Category")  # type: ignore[attr-defined]
    Category.objects.filter(
        name__en="Fuel",
        is_system=True,
    ).update(
        name={"en": "Gas", "ar": "غاز"},
        icon="\U0001f525",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("categories", "0007_fix_income_category_types"),
    ]

    operations = [
        migrations.RunPython(rename_gas_to_fuel, reverse_code=rename_fuel_to_gas),
    ]
