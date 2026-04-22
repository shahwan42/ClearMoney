"""Transfer and exchange operations.

TransferMixin is mixed into TransactionService and relies on methods from
TransactionServiceBase (self._get_account, self.get_by_id, self.user_id, etc.).
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone as django_tz

from accounts.models import Account
from categories.models import Category
from exchange_rates.models import ExchangeRateLog
from transactions.models import Transaction

from .utils import resolve_exchange_fields

logger = logging.getLogger(__name__)


class TransferMixin:
    """Mixin providing transfer and exchange methods."""

    # -------------------------------------------------------------------
    # Transfers
    # -------------------------------------------------------------------

    def create_transfer(
        self,
        source_id: str,
        dest_id: str,
        amount: float,
        currency: str | None,
        note: str | None,
        tx_date: date | str | None,
        fee_amount: float | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a same-currency transfer between two accounts with optional fee.

        When fee_amount > 0, creates a separate fee transaction (expense) on the
        source account categorized as "Fees & Charges". Source is debited amount + fee.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if fee_amount is not None and fee_amount < 0:
            raise ValueError("Transfer fee cannot be negative")
        if not source_id or not dest_id:
            raise ValueError("Both source and destination account_id required")
        if source_id == dest_id:
            raise ValueError("Cannot transfer to the same account")

        src_acc = self._get_account(source_id)  # type: ignore[attr-defined]
        dest_acc = self._get_account(dest_id)  # type: ignore[attr-defined]
        if src_acc["currency"] != dest_acc["currency"]:
            raise ValueError(
                "Transfer requires same currency; use exchange for cross-currency"
            )

        actual_currency = src_acc["currency"]
        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        uid = self.user_id  # type: ignore[attr-defined]
        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            # Debit leg (source)
            Transaction.objects.create(
                id=debit_id,
                user_id=uid,
                type="transfer",
                amount=amount,
                currency=actual_currency,
                account_id=source_id,
                counter_account_id=dest_id,
                note=note,
                date=tx_date,
                balance_delta=-amount,
            )
            # Credit leg (destination)
            Transaction.objects.create(
                id=credit_id,
                user_id=uid,
                type="transfer",
                amount=amount,
                currency=actual_currency,
                account_id=dest_id,
                counter_account_id=source_id,
                note=note,
                date=tx_date,
                balance_delta=amount,
            )
            # Link bidirectionally
            Transaction.objects.for_user(uid).filter(id=debit_id).update(
                linked_transaction_id=credit_id
            )
            Transaction.objects.for_user(uid).filter(id=credit_id).update(
                linked_transaction_id=debit_id
            )
            # Optional fee transaction
            effective_fee = fee_amount if fee_amount and fee_amount > 0 else 0
            if effective_fee > 0:
                fees_cat = (
                    Category.objects.for_user(uid)
                    .filter(name__en="Fees & Charges")
                    .first()
                )
                fee_tx_id = str(uuid.uuid4())
                Transaction.objects.create(
                    id=fee_tx_id,
                    user_id=uid,
                    type="expense",
                    amount=effective_fee,
                    currency=actual_currency,
                    account_id=source_id,
                    category_id=fees_cat.id if fees_cat else None,
                    note="Transfer fee",
                    date=tx_date,
                    balance_delta=-effective_fee,
                    linked_transaction_id=debit_id,
                )

            # Atomic F() updates — two separate queries to avoid deadlocks
            # on concurrent transfers between the same accounts
            total_debit = Decimal(str(amount)) + Decimal(str(effective_fee))
            now = django_tz.now()
            Account.objects.for_user(uid).filter(id=source_id).update(
                current_balance=F("current_balance") - total_debit,
                updated_at=now,
            )
            Account.objects.for_user(uid).filter(id=dest_id).update(
                current_balance=F("current_balance") + Decimal(str(amount)),
                updated_at=now,
            )

        logger.info(
            "transaction.transfer_created currency=%s source=%s dest=%s user=%s",
            actual_currency,
            source_id,
            dest_id,
            self.user_id,  # type: ignore[attr-defined]
        )
        debit_tx = self.get_by_id(debit_id)  # type: ignore[attr-defined]
        credit_tx = self.get_by_id(credit_id)  # type: ignore[attr-defined]
        return debit_tx or {}, credit_tx or {}


    # -------------------------------------------------------------------
    # Exchange
    # -------------------------------------------------------------------

    def create_exchange(
        self,
        source_id: str,
        dest_id: str,
        amount: float | None,
        rate: float | None,
        counter_amount: float | None,
        note: str | None,
        tx_date: date | str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a cross-currency exchange between two accounts.

        Rate always stored as "EGP per 1 USD". When source=EGP, inverts
        before resolution and inverts back for storage/logging.
        """
        if not source_id or not dest_id:
            raise ValueError("Both source and destination account_id required")
        if source_id == dest_id:
            raise ValueError("Cannot exchange to the same account")

        src_acc = self._get_account(source_id)  # type: ignore[attr-defined]
        dest_acc = self._get_account(dest_id)  # type: ignore[attr-defined]
        if src_acc["currency"] == dest_acc["currency"]:
            raise ValueError(
                "Exchange requires different currencies; use transfer for same currency"
            )

        # Rate convention: user enters "EGP per 1 USD"
        # When source=EGP: invert before resolution, invert back after
        source_is_egp = src_acc["currency"] == "EGP"
        if source_is_egp and rate is not None and rate > 0:
            rate = 1.0 / rate

        resolved_amount, formula_rate, resolved_counter = resolve_exchange_fields(
            amount, rate, counter_amount
        )

        # Display rate: always EGP per 1 USD
        display_rate = formula_rate
        if source_is_egp:
            display_rate = 1.0 / formula_rate

        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        uid = self.user_id  # type: ignore[attr-defined]
        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            # Debit leg (source currency out)
            Transaction.objects.create(
                id=debit_id,
                user_id=uid,
                type="exchange",
                amount=resolved_amount,
                currency=src_acc["currency"],
                account_id=source_id,
                counter_account_id=dest_id,
                exchange_rate=round(display_rate, 6),
                counter_amount=round(resolved_counter, 2),
                note=note,
                date=tx_date,
                balance_delta=-resolved_amount,
            )
            # Credit leg (dest currency in)
            Transaction.objects.create(
                id=credit_id,
                user_id=uid,
                type="exchange",
                amount=resolved_counter,
                currency=dest_acc["currency"],
                account_id=dest_id,
                counter_account_id=source_id,
                exchange_rate=round(display_rate, 6),
                counter_amount=round(resolved_amount, 2),
                note=note,
                date=tx_date,
                balance_delta=resolved_counter,
            )
            # Link
            Transaction.objects.for_user(uid).filter(id=debit_id).update(
                linked_transaction_id=credit_id
            )
            Transaction.objects.for_user(uid).filter(id=credit_id).update(
                linked_transaction_id=debit_id
            )
            # Atomic F() updates — amounts differ because currencies differ
            now = django_tz.now()
            Account.objects.for_user(uid).filter(id=source_id).update(
                current_balance=F("current_balance") - Decimal(str(resolved_amount)),
                updated_at=now,
            )
            Account.objects.for_user(uid).filter(id=dest_id).update(
                current_balance=F("current_balance") + Decimal(str(resolved_counter)),
                updated_at=now,
            )

        # Log exchange rate (non-critical)
        try:
            source_label = f"{src_acc['currency']}/{dest_acc['currency']}"
            ExchangeRateLog.objects.create(
                date=tx_date,
                rate=round(display_rate, 6),
                source=source_label,
                note=note,
            )
        except Exception:
            logger.warning("Failed to log exchange rate (non-critical)", exc_info=True)

        logger.info(
            "transaction.exchange_created source=%s dest=%s user=%s",
            src_acc["currency"],
            dest_acc["currency"],
            self.user_id,  # type: ignore[attr-defined]
        )
        debit_tx = self.get_by_id(debit_id)  # type: ignore[attr-defined]
        credit_tx = self.get_by_id(credit_id)  # type: ignore[attr-defined]
        return debit_tx or {}, credit_tx or {}
