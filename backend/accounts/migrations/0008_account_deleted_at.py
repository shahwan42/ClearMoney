from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_remove_account_role_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
