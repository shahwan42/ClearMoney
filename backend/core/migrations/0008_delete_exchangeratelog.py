"""State-only migration: remove ExchangeRateLog from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. This just removes the model from core's
migration state now that exchange_rates owns it.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove ExchangeRateLog from core state (table stays, ownership moves)."""

    dependencies = [
        ("core", "0007_add_system_categories"),
        ("exchange_rates", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="ExchangeRateLog",
                ),
            ],
        ),
    ]
