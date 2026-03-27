"""State-only migration: remove Budget and TotalBudget from core app state.

Uses SeparateDatabaseAndState with no database_operations — the tables
stay in the DB untouched. This just removes the models from core's
migration state now that budgets owns them.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove Budget and TotalBudget from core state (tables stay, ownership moves)."""

    dependencies = [
        ("core", "0012_delete_investment"),
        ("budgets", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="Budget",
                ),
                migrations.DeleteModel(
                    name="TotalBudget",
                ),
            ],
        ),
    ]
