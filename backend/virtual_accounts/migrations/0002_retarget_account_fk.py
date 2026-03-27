"""State-only migration: retarget VirtualAccount.account FK to accounts.Account.

Now that Account has been moved from core to accounts app (batch 10),
we need to update the FK reference in VirtualAccount's migration state.
No database operations needed — the FK column already exists.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Retarget VirtualAccount.account FK from core.Account to accounts.Account."""

    dependencies = [
        ("virtual_accounts", "0001_state_only"),
        ("accounts", "0002_state_only_account"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="virtualaccount",
                    name="account",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="account_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="accounts.account",
                    ),
                ),
            ],
        ),
    ]
