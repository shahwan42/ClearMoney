"""
Management command: reconcile_balances — verify account balances.

Compares cached current_balance against initial_balance + SUM(balance_delta) for every account.

Usage:
    python manage.py reconcile_balances          # Report only
    python manage.py reconcile_balances --fix    # Auto-fix discrepancies
"""

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from jobs.services.reconcile import ReconcileService


class Command(BaseCommand):
    help = "Verify that account balances match sum of transaction balance_deltas"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Auto-fix discrepancies by updating current_balance",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        auto_fix = bool(options.get("fix", False))
        svc = ReconcileService()
        discrepancies = svc.reconcile(auto_fix=auto_fix)

        if not discrepancies:
            self.stdout.write(self.style.SUCCESS("All balances match"))
            return

        for d in discrepancies:
            self.stdout.write(
                self.style.WARNING(
                    f"  {d.account_name}: cached={d.cached_balance:.2f}, "
                    f"expected={d.expected_balance:.2f}, diff={d.difference:+.2f}"
                )
            )

        action = "Fixed" if auto_fix else "Found"
        self.stdout.write(
            self.style.WARNING(f"{action} {len(discrepancies)} discrepancy(ies)")
        )
