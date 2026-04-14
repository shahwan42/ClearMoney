import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "Create a Django admin superuser from environment variables"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--email",
            type=str,
            help="Superuser email (defaults to DJANGO_SUPERUSER_EMAIL env var)",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Superuser password (defaults to DJANGO_SUPERUSER_PASSWORD env var)",
        )

    def handle(self, *args: str, **options: str) -> None:
        email = options["email"] or os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = options.get("password") or os.environ.get(
            "DJANGO_SUPERUSER_PASSWORD"
        )

        if not email or not password:
            self.stderr.write(
                self.style.ERROR(
                    "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set"
                )
            )
            return

        if User.objects.filter(username=email).exists():
            self.stdout.write(self.style.WARNING(f"Superuser {email} already exists"))
            return

        User.objects.create_superuser(username=email, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superuser {email} created successfully"))
