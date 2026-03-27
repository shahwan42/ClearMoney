"""State-only migration: remove VirtualAccount from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. Also updates the FK in VirtualAccountAllocation
to point to virtual_accounts.VirtualAccount instead of core.VirtualAccount.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove VirtualAccount from core state; retarget VirtualAccountAllocation FK."""

    dependencies = [
        ("core", "0014_delete_person"),
        ("virtual_accounts", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget FK in VirtualAccountAllocation to point to virtual_accounts.VirtualAccount
                migrations.AlterField(
                    model_name="virtualaccountallocation",
                    name="virtual_account",
                    field=models.ForeignKey(
                        db_column="virtual_account_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="virtual_accounts.virtualaccount",
                    ),
                ),
                # Now safe to delete VirtualAccount from core state
                migrations.DeleteModel(
                    name="VirtualAccount",
                ),
            ],
        ),
    ]
