"""State-only migration: retarget VirtualAccount.user to auth_app.user.

Uses SeparateDatabaseAndState with no database_operations.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Retarget VirtualAccount.user from core.user to auth_app.user (state only)."""

    dependencies = [
        ("virtual_accounts", "0002_retarget_account_fk"),
        ("auth_app", "0002_state_only_user_session_authtoken"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="virtualaccount",
                    name="user",
                    field=models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth_app.user",
                    ),
                ),
            ],
        ),
    ]
