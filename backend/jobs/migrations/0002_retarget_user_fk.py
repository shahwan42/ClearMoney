"""State-only migration: retarget DailySnapshot.user and AccountSnapshot.user to auth_app.user.

Uses SeparateDatabaseAndState with no database_operations.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Retarget DailySnapshot.user and AccountSnapshot.user from core.user to auth_app.user."""

    dependencies = [
        ("jobs", "0001_state_only"),
        ("auth_app", "0002_state_only_user_session_authtoken"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="dailysnapshot",
                    name="user",
                    field=models.ForeignKey(
                        db_column="user_id",
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth_app.user",
                    ),
                ),
                migrations.AlterField(
                    model_name="accountsnapshot",
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
