"""State-only migration: remove Category from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. This just removes the model from core's
migration state now that categories owns it.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove Category from core state (table stays, ownership moves)."""

    dependencies = [
        ("core", "0008_delete_exchangeratelog"),
        ("categories", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="Category",
                ),
            ],
        ),
    ]
