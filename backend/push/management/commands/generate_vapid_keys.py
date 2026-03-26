"""
Generate VAPID keys for Web Push Notifications.

VAPID (Voluntary Application Server Identification) keys are used by browsers
to verify that push notifications come from your server.

This command generates an EC256 (P-256 elliptic curve) key pair and outputs
them in URL-safe base64 format, ready to use in .env.

Usage:
    python manage.py generate_vapid_keys
    python manage.py generate_vapid_keys --output .env.local

No external services or Node.js required — uses Python's cryptography library.
"""

import argparse
import base64
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate VAPID keys for Web Push Notifications (P-256/EC256)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Optional file to append keys to (e.g., .env or .env.local)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(
            self.style.SUCCESS("Generating VAPID keys (P-256 elliptic curve)...\n")
        )

        # Generate P-256 (secp256r1) key pair — this is what VAPID uses
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()

        # Serialize private key — extract the raw value from the private int
        # P-256 private keys are 32 bytes (256 bits)
        private_value = private_key.private_numbers().private_value
        private_bytes = private_value.to_bytes(32, byteorder="big")

        # Serialize public key to raw bytes (65 bytes: 0x04 + 32 bytes X + 32 bytes Y)
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")
        public_bytes = b"\x04" + x_bytes + y_bytes

        # Encode to URL-safe base64 (without padding) — VAPID format
        private_key_b64 = base64.urlsafe_b64encode(private_bytes).decode().rstrip("=")
        public_key_b64 = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")

        # Display the keys
        output = (
            f"VAPID_PUBLIC_KEY={public_key_b64}\nVAPID_PRIVATE_KEY={private_key_b64}\n"
        )

        self.stdout.write(self.style.WARNING("⚠️  Keep VAPID_PRIVATE_KEY secret!"))
        self.stdout.write(self.style.WARNING("    Never commit it to git.\n"))
        self.stdout.write(self.style.SUCCESS("Add these to your .env file:\n"))
        self.stdout.write(output)

        # Optionally append to a file
        if options["output"]:
            try:
                with open(options["output"], "a") as f:
                    f.write(f"\n# Generated VAPID keys\n{output}")
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Keys appended to {options['output']}")
                )
            except OSError as e:
                self.stdout.write(
                    self.style.ERROR(f"Error writing to {options['output']}: {e}")
                )
