"""State-only migration: remove RecurringRule from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. Also updates the FK in Transaction to point
to recurring.RecurringRule instead of core.RecurringRule.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove RecurringRule from core state; retarget Transaction FK."""

    dependencies = [
        ("core", "0015_delete_virtualaccount"),
        ("recurring", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget FK in Transaction to point to recurring.RecurringRule
                migrations.AlterField(
                    model_name="transaction",
                    name="recurring_rule",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="recurring_rule_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="recurring.recurringrule",
                    ),
                ),
                # Now safe to delete RecurringRule from core state
                migrations.DeleteModel(
                    name="RecurringRule",
                ),
            ],
        ),
    ]
