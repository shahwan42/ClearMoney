"""State-only migration: remove User, Session, AuthToken from core.

Uses SeparateDatabaseAndState with no database_operations — the tables
stay in the DB untouched. This just removes the models from core's
migration state now that auth_app owns them.

All FK references from other apps have been retargeted to auth_app.user
via per-app retargeting migrations before this deletion runs.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove User, Session, and AuthToken from core state."""

    dependencies = [
        ("core", "0019_delete_transaction_virtualaccountallocation"),
        ("auth_app", "0002_state_only_user_session_authtoken"),
        # All per-app user FK retargeting migrations must complete first
        ("accounts", "0003_retarget_user_fk"),
        ("budgets", "0002_retarget_user_fk"),
        ("categories", "0002_retarget_user_fk"),
        ("investments", "0002_retarget_user_fk"),
        ("jobs", "0002_retarget_user_fk"),
        ("people", "0002_retarget_user_fk"),
        ("recurring", "0002_retarget_user_fk"),
        ("transactions", "0002_retarget_user_fk"),
        ("virtual_accounts", "0003_retarget_user_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget Session.user in core state before deleting User
                migrations.AlterField(
                    model_name="session",
                    name="user",
                    field=models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth_app.user",
                    ),
                ),
                migrations.DeleteModel(
                    name="Session",
                ),
                migrations.DeleteModel(
                    name="AuthToken",
                ),
                migrations.DeleteModel(
                    name="User",
                ),
            ],
        ),
    ]
