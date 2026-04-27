"""Allow account_id to be NULL for single-entry (memo) loan transactions."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0009_transaction_fee_preset"),
        ("accounts", "0007_remove_account_role_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="account",
            field=models.ForeignKey(
                "accounts.Account",
                on_delete=django.db.models.deletion.CASCADE,
                db_column="account_id",
                db_index=True,
                null=True,
                blank=True,
                related_name="transactions",
            ),
        ),
    ]
