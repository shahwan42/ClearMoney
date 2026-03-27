"""State-only migration: retarget Person.user to auth_app.user.

Uses SeparateDatabaseAndState with no database_operations.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Retarget Person.user from core.user to auth_app.user (state only)."""

    dependencies = [
        ("people", "0001_state_only"),
        ("auth_app", "0002_state_only_user_session_authtoken"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="person",
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
