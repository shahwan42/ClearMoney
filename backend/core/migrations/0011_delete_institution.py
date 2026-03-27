"""State-only migration: remove Institution from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. Also updates the FK in Account to point to
accounts.Institution instead of core.Institution.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove Institution from core state; retarget Account FK."""

    dependencies = [
        ("core", "0010_delete_userconfig"),
        ("accounts", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget FK in Account to point to accounts.Institution
                migrations.AlterField(
                    model_name="account",
                    name="institution",
                    field=models.ForeignKey(
                        db_column="institution_id",
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accounts",
                        to="accounts.institution",
                    ),
                ),
                # Now safe to delete Institution from core state
                migrations.DeleteModel(
                    name="Institution",
                ),
            ],
        ),
    ]
