"""Add name_json JSONField alongside existing name CharField."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 1 of 3: Add nullable name_json column."""

    dependencies = [
        ("categories", "0002_retarget_user_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="name_json",
            field=models.JSONField(default=dict, null=True),
        ),
    ]
