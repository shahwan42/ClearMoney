"""State-only migration: remove Investment from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. This just removes the model from core's
migration state now that investments owns it.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove Investment from core state (table stays, ownership moves)."""

    dependencies = [
        ("core", "0011_delete_institution"),
        ("investments", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="Investment",
                ),
            ],
        ),
    ]
