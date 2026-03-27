"""State-only migration: remove Transaction and VirtualAccountAllocation from core.

Uses SeparateDatabaseAndState with no database_operations — the tables
stay in the DB untouched. This just removes the models from core's
migration state now that transactions owns them.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove Transaction and VirtualAccountAllocation from core state."""

    dependencies = [
        ("core", "0018_delete_dailysnapshot_accountsnapshot"),
        ("transactions", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="VirtualAccountAllocation",
                ),
                migrations.DeleteModel(
                    name="Transaction",
                ),
            ],
        ),
    ]
