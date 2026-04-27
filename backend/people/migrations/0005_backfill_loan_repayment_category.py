from typing import Any

from django.db import migrations


def backfill_debt_payment_category(apps: Any, schema_editor: Any) -> None:
    Transaction = apps.get_model("transactions", "Transaction")
    Category = apps.get_model("categories", "Category")

    # Build a map of user_id → Debt Payment category id
    debt_cats = {
        str(c.user_id): c.id
        for c in Category.objects.filter(is_system=True, name__en="Debt Payment")
    }

    for user_id, cat_id in debt_cats.items():
        Transaction.objects.filter(
            user_id=user_id,
            type="loan_repayment",
            category_id__isnull=True,
        ).update(category_id=cat_id)


class Migration(migrations.Migration):
    dependencies = [
        ("people", "0004_remove_person_net_balance_and_more"),
        ("transactions", "0010_transaction_account_nullable"),
        ("categories", "0006_alter_category_name"),
    ]

    operations = [
        migrations.RunPython(
            backfill_debt_payment_category,
            migrations.RunPython.noop,
        ),
    ]
