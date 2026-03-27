"""State-only migration: remove Account from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. Also retargets all FKs that pointed to
core.Account to now point to accounts.Account.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove Account from core state; retarget FKs in Transaction, VirtualAccount, AccountSnapshot."""

    dependencies = [
        ("core", "0016_delete_recurringrule"),
        ("accounts", "0002_state_only_account"),
        ("virtual_accounts", "0002_retarget_account_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget FKs in Transaction
                migrations.AlterField(
                    model_name="transaction",
                    name="account",
                    field=models.ForeignKey(
                        db_column="account_id",
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="accounts.account",
                    ),
                ),
                migrations.AlterField(
                    model_name="transaction",
                    name="counter_account",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="counter_account_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="accounts.account",
                    ),
                ),
                migrations.AlterField(
                    model_name="transaction",
                    name="fee_account",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="fee_account_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="accounts.account",
                    ),
                ),
                # Retarget FK in AccountSnapshot
                migrations.AlterField(
                    model_name="accountsnapshot",
                    name="account",
                    field=models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="accounts.account",
                    ),
                ),
                # Now safe to delete Account from core state
                migrations.DeleteModel(
                    name="Account",
                ),
            ],
        ),
    ]
