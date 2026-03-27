"""State-only migration: register User, Session, AuthToken in auth_app.

Uses SeparateDatabaseAndState with no database_operations — the tables
already exist. This just tells Django's migration state that the models
live here now.
"""

import uuid

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Register User, Session, and AuthToken in auth_app (state only, no DB ops)."""

    dependencies = [
        ("auth_app", "0001_state_only"),
        ("core", "0019_delete_transaction_virtualaccountallocation"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="User",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                primary_key=True,
                                default=uuid.uuid4,
                                db_default=Func(function="gen_random_uuid"),
                                serialize=False,
                            ),
                        ),
                        ("email", models.CharField(max_length=255, unique=True)),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                        (
                            "updated_at",
                            models.DateTimeField(
                                auto_now=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "users",
                    },
                ),
                migrations.CreateModel(
                    name="Session",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                primary_key=True,
                                default=uuid.uuid4,
                                db_default=Func(function="gen_random_uuid"),
                                serialize=False,
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                db_column="user_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                to="auth_app.user",
                            ),
                        ),
                        ("token", models.CharField(max_length=255, unique=True)),
                        ("expires_at", models.DateTimeField()),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "sessions",
                    },
                ),
                migrations.CreateModel(
                    name="AuthToken",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                primary_key=True,
                                default=uuid.uuid4,
                                db_default=Func(function="gen_random_uuid"),
                                serialize=False,
                            ),
                        ),
                        ("email", models.CharField(max_length=255)),
                        ("token", models.CharField(max_length=255, unique=True)),
                        (
                            "purpose",
                            models.CharField(
                                max_length=20,
                                default="login",
                                db_default="login",
                            ),
                        ),
                        ("expires_at", models.DateTimeField()),
                        (
                            "used",
                            models.BooleanField(default=False, db_default=False),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "auth_tokens",
                    },
                ),
            ],
        ),
    ]
