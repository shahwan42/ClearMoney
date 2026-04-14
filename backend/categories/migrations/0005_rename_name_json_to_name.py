"""Remove old name CharField and rename name_json -> name."""

from django.db import migrations


class Migration(migrations.Migration):
    """Step 3 of 3: Drop old name, rename name_json to name."""

    dependencies = [
        ("categories", "0004_name_to_jsonb_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="category",
            name="name",
        ),
        migrations.RenameField(
            model_name="category",
            old_name="name_json",
            new_name="name",
        ),
    ]
