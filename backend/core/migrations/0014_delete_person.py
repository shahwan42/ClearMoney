"""State-only migration: remove Person from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. Also updates the FK in Transaction to point
to people.Person instead of core.Person.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove Person from core state; retarget Transaction FK."""

    dependencies = [
        ("core", "0013_delete_budget_totalbudget"),
        ("people", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget FK in Transaction to point to people.Person
                migrations.AlterField(
                    model_name="transaction",
                    name="person",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="person_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="people.person",
                    ),
                ),
                # Now safe to delete Person from core state
                migrations.DeleteModel(
                    name="Person",
                ),
            ],
        ),
    ]
