"""State-only migration: retarget Institution.user and Account.user to auth_app.user.

Uses SeparateDatabaseAndState with no database_operations — the DB column
stays unchanged (still user_id FK to the users table).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Retarget Institution.user and Account.user from core.user to auth_app.user (state only)."""

    dependencies = [
        ("accounts", "0002_state_only_account"),
        ("auth_app", "0002_state_only_user_session_authtoken"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="institution",
                    name="user",
                    field=models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth_app.user",
                    ),
                ),
                migrations.AlterField(
                    model_name="account",
                    name="user",
                    field=models.ForeignKey(
                        db_column="user_id",
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth_app.user",
                    ),
                ),
            ],
        ),
    ]
