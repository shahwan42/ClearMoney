"""State-only migration: remove UserConfig from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. This just removes the model from core's
migration state now that auth_app owns it.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove UserConfig from core state (table stays, ownership moves)."""

    dependencies = [
        ("core", "0009_delete_category"),
        ("auth_app", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="UserConfig",
                ),
            ],
        ),
    ]
