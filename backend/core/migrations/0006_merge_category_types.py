"""Data migration: merge duplicate categories and normalize type to 'expense'.

Categories are now type-agnostic — any category works with any transaction type.
This migration:
1. Finds categories with the same user + name (case-insensitive) but different types
2. Keeps the one with more transactions (or the expense one if tied)
3. Reassigns all transactions and budgets from duplicates to the survivor
4. Deletes the duplicates
5. Normalizes all remaining categories to type='expense'
"""

from typing import Any

from django.db import connection, migrations


def merge_categories(apps: Any, schema_editor: Any) -> None:
    """Merge duplicate categories per user and normalize all to type='expense'."""
    with connection.cursor() as cursor:
        # Find categories that share user_id + lower(name) but have multiple rows
        cursor.execute("""
            SELECT user_id, lower(name) AS lname, array_agg(id ORDER BY type) AS ids
            FROM categories
            WHERE is_archived = false
            GROUP BY user_id, lower(name)
            HAVING count(*) > 1
        """)
        for user_id, _lname, ids in cursor.fetchall():
            # Count transactions per category to pick the survivor
            counts = {}
            for cat_id in ids:
                cursor.execute(
                    "SELECT count(*) FROM transactions WHERE category_id = %s",
                    [cat_id],
                )
                counts[cat_id] = cursor.fetchone()[0]

            # Survivor = most transactions (expense type wins ties since sorted first)
            survivor = max(ids, key=lambda i: counts[i])

            for dup_id in ids:
                if dup_id != survivor:
                    # Reassign transactions
                    cursor.execute(
                        "UPDATE transactions SET category_id = %s WHERE category_id = %s",
                        [survivor, dup_id],
                    )
                    # Reassign budgets (delete if it would create a duplicate)
                    cursor.execute(
                        """DELETE FROM budgets WHERE category_id = %s
                           AND EXISTS (
                               SELECT 1 FROM budgets b2
                               WHERE b2.category_id = %s
                               AND b2.user_id = budgets.user_id
                               AND b2.currency = budgets.currency
                           )""",
                        [dup_id, survivor],
                    )
                    cursor.execute(
                        "UPDATE budgets SET category_id = %s WHERE category_id = %s",
                        [survivor, dup_id],
                    )
                    # Delete the duplicate category
                    cursor.execute("DELETE FROM categories WHERE id = %s", [dup_id])

        # Normalize all categories to type='expense'
        cursor.execute("UPDATE categories SET type = 'expense'")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_totalbudget"),
    ]

    operations = [
        migrations.RunPython(merge_categories, migrations.RunPython.noop),
    ]
