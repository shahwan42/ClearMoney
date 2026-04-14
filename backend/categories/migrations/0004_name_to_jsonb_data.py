"""Data migration: copy name char values into name_json as {"en": <value>}."""

from typing import Any

from django.db import migrations


def populate_name_json(apps: Any, schema_editor: Any) -> None:
    Category = apps.get_model("categories", "Category")
    db_alias = schema_editor.connection.alias
    for cat in Category.objects.using(db_alias).all():
        current = cat.name
        if isinstance(current, str):
            cat.name_json = {"en": current}
        elif isinstance(current, dict):
            cat.name_json = current
        else:
            cat.name_json = {"en": str(current)} if current else {"en": ""}
        cat.save(update_fields=["name_json"])


def reverse_populate(apps: Any, schema_editor: Any) -> None:
    pass


class Migration(migrations.Migration):
    """Step 2 of 3: Copy existing name values into name_json."""

    dependencies = [
        ("categories", "0003_add_name_json"),
    ]

    operations = [
        migrations.RunPython(populate_name_json, reverse_populate),
    ]
