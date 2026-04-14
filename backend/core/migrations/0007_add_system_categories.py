"""Data migration: add Travel, Cafe, Restaurant, Car system categories.

Adds 4 new system categories for all existing users. Idempotent — skips
users who already have a category with the same name (case-insensitive).
"""

from typing import Any

from django.db import connection, migrations

NEW_CATEGORIES: list[dict[str, Any]] = [
    {"name": {"en": "Travel", "ar": "سفر"}, "icon": "✈️", "display_order": 24},
    {"name": {"en": "Cafe", "ar": "مقهى"}, "icon": "☕", "display_order": 25},
    {"name": {"en": "Restaurant", "ar": "مطعم"}, "icon": "🍽️", "display_order": 26},
    {"name": {"en": "Car", "ar": "سيارة"}, "icon": "🚙", "display_order": 27},
]


def add_system_categories(apps: Any, schema_editor: Any) -> None:
    """Add Travel, Cafe, Restaurant, Car to all existing users."""
    import json

    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users")
        user_ids = [row[0] for row in cursor.fetchall()]

        for user_id in user_ids:
            for cat in NEW_CATEGORIES:
                # Skip if user already has this category (case-insensitive on English name)
                cursor.execute(
                    "SELECT 1 FROM categories WHERE user_id = %s AND name->>'en' ILIKE %s",
                    [user_id, cat["name"]["en"]],
                )
                if cursor.fetchone():
                    continue

                cursor.execute(
                    """INSERT INTO categories
                       (id, user_id, name, type, icon, is_system, is_archived,
                        display_order, created_at, updated_at)
                       VALUES (gen_random_uuid(), %s, %s, 'expense', %s, true, false,
                               %s, now(), now())""",
                    [
                        user_id,
                        json.dumps(cat["name"]),
                        cat["icon"],
                        cat["display_order"],
                    ],
                )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_merge_category_types"),
    ]

    operations = [
        migrations.RunPython(add_system_categories, migrations.RunPython.noop),
    ]
