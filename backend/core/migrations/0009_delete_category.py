"""State-only migration: remove Category from core app state.

Uses SeparateDatabaseAndState with no database_operations — the table
stays in the DB untouched. This removes the model from core's migration
state now that categories owns it, and updates FK references in Budget
and Transaction to point to categories.Category.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove Category from core state; retarget FKs to categories.Category."""

    dependencies = [
        ("core", "0008_delete_exchangeratelog"),
        ("categories", "0001_state_only"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                # Retarget FK in Budget to point to categories.Category
                migrations.AlterField(
                    model_name="budget",
                    name="category",
                    field=models.ForeignKey(
                        db_column="category_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="categories.category",
                    ),
                ),
                # Retarget FK in Transaction to point to categories.Category
                migrations.AlterField(
                    model_name="transaction",
                    name="category",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="category_id",
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="categories.category",
                    ),
                ),
                # Now safe to delete Category from core state
                migrations.DeleteModel(
                    name="Category",
                ),
            ],
        ),
    ]
