"""State-only migration: remove AccountSnapshot and DailySnapshot from jobs app state.

Both models have been moved to their owning apps:
- AccountSnapshot → accounts app (accounts/migrations/0004_state_only_account_snapshot.py)
- DailySnapshot → auth_app (auth_app/migrations/0003_state_only_daily_snapshot.py)

Uses SeparateDatabaseAndState with no database_operations — tables are unchanged.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove AccountSnapshot and DailySnapshot state from jobs app."""

    dependencies = [
        ("jobs", "0002_retarget_user_fk"),
        ("accounts", "0004_state_only_account_snapshot"),
        ("auth_app", "0003_state_only_daily_snapshot"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="AccountSnapshot"),
                migrations.DeleteModel(name="DailySnapshot"),
            ],
        ),
    ]
