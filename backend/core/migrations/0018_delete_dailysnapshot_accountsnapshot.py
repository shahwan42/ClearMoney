"""State-only migration: remove DailySnapshot and AccountSnapshot from core app state.

Uses SeparateDatabaseAndState with no database_operations — the tables
stay in the DB untouched. This just removes the models from core's
migration state now that jobs owns them.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove DailySnapshot and AccountSnapshot from core state (tables stay)."""

    dependencies = [
        ("core", "0017_delete_account"),
        ("jobs", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="DailySnapshot",
                ),
                migrations.DeleteModel(
                    name="AccountSnapshot",
                ),
            ],
        ),
    ]
