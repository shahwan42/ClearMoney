"""
Unit tests for push app management commands.

Tests verify functionality, output format, error handling, and side effects
for all management commands in the push app.
"""

import base64
import tempfile
from io import StringIO
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management import call_command
from django.test import TestCase


class TestGenerateVapidKeysCommand(TestCase):
    """Test the generate_vapid_keys management command."""

    def test_command_executes_successfully(self):
        """Test that command runs without error."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        assert "Generating VAPID keys" in output
        assert "VAPID_PUBLIC_KEY=" in output
        assert "VAPID_PRIVATE_KEY=" in output

    def test_generates_non_empty_keys(self):
        """Test that command outputs actual keys (not empty strings)."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        lines = output.split("\n")
        public_line = [line for line in lines if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]
        private_line = [
            line for line in lines if line.startswith("VAPID_PRIVATE_KEY=")
        ][0]

        public_key = public_line.split("=", 1)[1]
        private_key = private_line.split("=", 1)[1]

        assert len(public_key) > 0
        assert len(private_key) > 0

    def test_keys_are_correct_length(self):
        """Test key lengths match P-256 specification."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        lines = output.split("\n")
        public_line = [line for line in lines if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]
        private_line = [
            line for line in lines if line.startswith("VAPID_PRIVATE_KEY=")
        ][0]

        public_key = public_line.split("=", 1)[1]
        private_key = private_line.split("=", 1)[1]

        # Public key: 65 bytes * 4/3 ≈ 87 chars (no padding)
        # Private key: 32 bytes * 4/3 ≈ 43 chars (no padding)
        assert 85 <= len(public_key) <= 90
        assert 40 <= len(private_key) <= 45

    def test_keys_are_url_safe_base64(self):
        """Test keys use URL-safe base64 alphabet without padding."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        lines = output.split("\n")
        public_line = [line for line in lines if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]
        private_line = [
            line for line in lines if line.startswith("VAPID_PRIVATE_KEY=")
        ][0]

        public_key = public_line.split("=", 1)[1]
        private_key = private_line.split("=", 1)[1]

        url_safe_chars = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )

        assert set(public_key).issubset(url_safe_chars)
        assert set(private_key).issubset(url_safe_chars)
        assert "=" not in public_key
        assert "=" not in private_key

    def test_keys_decode_from_base64(self):
        """Test keys can be decoded from URL-safe base64."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        lines = output.split("\n")
        public_line = [line for line in lines if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]
        private_line = [
            line for line in lines if line.startswith("VAPID_PRIVATE_KEY=")
        ][0]

        public_key_b64 = public_line.split("=", 1)[1]
        private_key_b64 = private_line.split("=", 1)[1]

        # Add padding for decoding
        public_padding = (4 - len(public_key_b64) % 4) % 4
        private_padding = (4 - len(private_key_b64) % 4) % 4

        public_bytes = base64.urlsafe_b64decode(public_key_b64 + "=" * public_padding)
        private_bytes = base64.urlsafe_b64decode(
            private_key_b64 + "=" * private_padding
        )

        assert len(public_bytes) == 65
        assert public_bytes[0] == 0x04  # Uncompressed point format
        assert len(private_bytes) == 32

    def test_keys_are_valid_ec_keys(self):
        """Test keys represent valid P-256 elliptic curve cryptography."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        lines = output.split("\n")
        public_line = [line for line in lines if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]
        private_line = [
            line for line in lines if line.startswith("VAPID_PRIVATE_KEY=")
        ][0]

        public_key_b64 = public_line.split("=", 1)[1]
        private_key_b64 = private_line.split("=", 1)[1]

        # Decode
        public_padding = (4 - len(public_key_b64) % 4) % 4
        private_padding = (4 - len(private_key_b64) % 4) % 4
        public_bytes = base64.urlsafe_b64decode(public_key_b64 + "=" * public_padding)
        private_bytes = base64.urlsafe_b64decode(
            private_key_b64 + "=" * private_padding
        )

        # Reconstruct keys
        private_value = int.from_bytes(private_bytes, byteorder="big")
        private_key = ec.derive_private_key(
            private_value, ec.SECP256R1(), default_backend()
        )

        x_bytes = public_bytes[1:33]
        y_bytes = public_bytes[33:65]
        x = int.from_bytes(x_bytes, byteorder="big")
        y = int.from_bytes(y_bytes, byteorder="big")
        public_numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1())
        public_key_reconstructed = public_numbers.public_key(default_backend())

        # Verify consistency
        private_key_public = private_key.public_key()
        assert (
            private_key_public.public_numbers().x
            == public_key_reconstructed.public_numbers().x
        )
        assert (
            private_key_public.public_numbers().y
            == public_key_reconstructed.public_numbers().y
        )

    def test_output_file_creation(self):
        """Test --output flag creates file with keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.env"

            call_command("generate_vapid_keys", output=str(output_file))

            assert output_file.exists()
            content = output_file.read_text()
            assert "VAPID_PUBLIC_KEY=" in content
            assert "VAPID_PRIVATE_KEY=" in content

    def test_output_file_appends_to_existing_file(self):
        """Test --output appends rather than overwriting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.env"
            output_file.write_text("EXISTING_KEY=value\n")

            call_command("generate_vapid_keys", output=str(output_file))

            content = output_file.read_text()
            assert "EXISTING_KEY=value" in content
            assert "VAPID_PUBLIC_KEY=" in content
            assert "VAPID_PRIVATE_KEY=" in content

    def test_output_file_handles_invalid_path(self):
        """Test command handles invalid output path gracefully."""
        invalid_path = "/nonexistent/directory/that/does/not/exist.env"

        out = StringIO()

        try:
            call_command("generate_vapid_keys", output=invalid_path, stdout=out)
        except SystemExit:
            pass

        # Keys should still be in stdout
        output = out.getvalue()
        assert "VAPID_PUBLIC_KEY=" in output
        assert "VAPID_PRIVATE_KEY=" in output

    def test_keys_are_random_each_invocation(self):
        """Test each run generates different keys (cryptographic randomness)."""
        out1 = StringIO()
        call_command("generate_vapid_keys", stdout=out1)
        output1 = out1.getvalue()

        out2 = StringIO()
        call_command("generate_vapid_keys", stdout=out2)
        output2 = out2.getvalue()

        lines1 = output1.split("\n")
        lines2 = output2.split("\n")

        public_key1 = [line for line in lines1 if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]
        public_key2 = [line for line in lines2 if line.startswith("VAPID_PUBLIC_KEY=")][
            0
        ]

        assert public_key1 != public_key2

    def test_displays_security_warning(self):
        """Test security warning about private key secrecy is shown."""
        out = StringIO()
        call_command("generate_vapid_keys", stdout=out)
        output = out.getvalue()

        assert "Keep VAPID_PRIVATE_KEY secret" in output
        assert "Never commit it to git" in output

    def test_stdout_and_file_output_match(self):
        """Test --output file contains identical keys as stdout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.env"

            out = StringIO()
            call_command("generate_vapid_keys", output=str(output_file), stdout=out)

            stdout_content = out.getvalue()
            file_content = output_file.read_text()

            stdout_public = [
                line
                for line in stdout_content.split("\n")
                if line.startswith("VAPID_PUBLIC_KEY=")
            ][0]
            file_public = [
                line
                for line in file_content.split("\n")
                if line.startswith("VAPID_PUBLIC_KEY=")
            ][0]

            stdout_private = [
                line
                for line in stdout_content.split("\n")
                if line.startswith("VAPID_PRIVATE_KEY=")
            ][0]
            file_private = [
                line
                for line in file_content.split("\n")
                if line.startswith("VAPID_PRIVATE_KEY=")
            ][0]

            assert stdout_public == file_public
            assert stdout_private == file_private
