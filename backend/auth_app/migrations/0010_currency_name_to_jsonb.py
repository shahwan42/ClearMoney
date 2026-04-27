"""Convert Currency.name from CharField to JSONField with bilingual values.

Single-migration approach (safe for the 6-row global currencies table):

1. RunSQL alters the column type from text to jsonb, wrapping existing
   string values into `{"en": "..."}`.
2. RunPython populates Arabic translations for the seeded currencies.
3. `SeparateDatabaseAndState` mirrors the type change in Django's model
   state without re-running the ALTER (Django would otherwise issue a
   `USING name::jsonb` cast that fails on plain strings).
"""

from django.db import migrations, models

ARABIC_NAMES = {
    "EGP": "الجنيه المصري",
    "USD": "الدولار الأمريكي",
    "EUR": "اليورو",
    "GBP": "الجنيه الإسترليني",
    "AED": "الدرهم الإماراتي",
    "SAR": "الريال السعودي",
}


def add_arabic_names(apps, schema_editor):  # type: ignore[no-untyped-def]
    Currency = apps.get_model("auth_app", "Currency")
    for cur in Currency.objects.all():
        if not isinstance(cur.name, dict):
            continue
        en = cur.name.get("en") or cur.code
        ar = ARABIC_NAMES.get(cur.code, en)
        cur.name = {"en": en, "ar": ar}
        cur.save(update_fields=["name", "updated_at"])


def revert_to_english_only(apps, schema_editor):  # type: ignore[no-untyped-def]
    Currency = apps.get_model("auth_app", "Currency")
    for cur in Currency.objects.all():
        if isinstance(cur.name, dict):
            cur.name = {"en": cur.name.get("en") or cur.code}
            cur.save(update_fields=["name", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "auth_app",
            "0009_remove_dailysnapshot_daily_snapshots_user_date_unique_and_more",
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE currencies "
                        "ALTER COLUMN name TYPE jsonb "
                        "USING jsonb_build_object('en', name);"
                    ),
                    reverse_sql=(
                        "ALTER TABLE currencies "
                        "ALTER COLUMN name TYPE varchar(50) "
                        "USING (name->>'en');"
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="currency",
                    name="name",
                    field=models.JSONField(default=dict),
                ),
            ],
        ),
        migrations.RunPython(add_arabic_names, revert_to_english_only),
    ]
