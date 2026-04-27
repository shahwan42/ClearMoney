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

    # -------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------

    def update_transfer(
        self,
        tx_id: str,
        amount: float | int | Decimal,
        note: str | None,
        tx_date: date,
        fee_amount: float | None,
        source_id: str | None = None,
        dest_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Update both legs of a transfer atomically, including optional fee.

        source_id / dest_id: pass new account IDs to reassign the transfer.
        If omitted, the existing accounts are kept.

        Returns (debit_leg, credit_leg) dicts after update.
        """
        uid = self.user_id  # type: ignore[attr-defined]

        tx = self.get_by_id(tx_id)  # type: ignore[attr-defined]
        if not tx:
            raise ValueError(f"Transaction not found: {tx_id}")
        if tx.get("type") != "transfer":
            raise ValueError(f"Transaction {tx_id} is not a transfer")

        linked_id = tx.get("linked_transaction_id")
        if not linked_id:
            raise ValueError(f"Transfer {tx_id} has no linked leg")

        linked_tx = self.get_by_id(linked_id)  # type: ignore[attr-defined]
        if not linked_tx:
            raise ValueError(f"Linked leg not found: {linked_id}")

        # Normalize: always work in terms of debit (source) and credit (dest) legs
        if Decimal(str(tx["balance_delta"])) < 0:
            debit_tx, credit_tx = tx, linked_tx
            debit_id, credit_id = tx_id, str(linked_id)
        else:
            debit_tx, credit_tx = linked_tx, tx
            debit_id, credit_id = str(linked_id), tx_id

        old_source_id = str(debit_tx["account_id"])
        old_dest_id = str(credit_tx["account_id"])
        new_source_id = source_id or old_source_id
        new_dest_id = dest_id or old_dest_id

        if new_source_id == new_dest_id:
            raise ValueError("Cannot transfer to the same account")

        source_changing = new_source_id != old_source_id
        dest_changing = new_dest_id != old_dest_id

        if source_changing or dest_changing:
            src_acc = self._get_account(new_source_id)  # type: ignore[attr-defined]
            dest_acc = self._get_account(new_dest_id)  # type: ignore[attr-defined]
            if src_acc["currency"] != dest_acc["currency"]:
                raise ValueError(
                    "Transfer requires same currency; use exchange for cross-currency"
                )

        new_amount = Decimal(str(amount))
        old_amount = Decimal(str(debit_tx["amount"]))
        amount_delta = new_amount - old_amount

        now = django_tz.now()

        with transaction.atomic():
            Transaction.objects.filter(user_id=uid, id=debit_id).update(
                amount=new_amount,
                balance_delta=-new_amount,
                account_id=new_source_id,
                counter_account_id=new_dest_id,
                note=note,
                date=tx_date,
                updated_at=now,
            )
            Transaction.objects.filter(user_id=uid, id=credit_id).update(
                amount=new_amount,
                balance_delta=new_amount,
                account_id=new_dest_id,
                counter_account_id=new_source_id,
                note=note,
                date=tx_date,
                updated_at=now,
            )

            if source_changing or dest_changing:
                # "Undo old state, apply new state" — handles all combinations
                existing_fee_tx = Transaction.objects.filter(
                    user_id=uid,
                    linked_transaction_id=debit_id,  # type: ignore[misc]
                    note="Transfer fee",
                ).first()
                old_fee = (
                    Decimal(str(existing_fee_tx.amount))
                    if existing_fee_tx
                    else Decimal("0")
                )

                # Restore old source (transfer amount + fee that sat there)
                Account.objects.filter(user_id=uid, id=old_source_id).update(
                    current_balance=F("current_balance") + old_amount + old_fee,
                    updated_at=now,
                )
                # Restore old dest
                Account.objects.filter(user_id=uid, id=old_dest_id).update(
                    current_balance=F("current_balance") - old_amount,
                    updated_at=now,
                )
                # Delete old fee (balance already restored above)
                if existing_fee_tx:
                    existing_fee_tx.delete()

                # Debit new source
                Account.objects.filter(user_id=uid, id=new_source_id).update(
                    current_balance=F("current_balance") - new_amount,
                    updated_at=now,
                )
                # Credit new dest
                Account.objects.filter(user_id=uid, id=new_dest_id).update(
                    current_balance=F("current_balance") + new_amount,
                    updated_at=now,
                )
                # Recreate fee on new source
                self._update_fee_in_atomic(
                    uid, debit_id, new_source_id, fee_amount, tx_date, now
                )
            else:
                if amount_delta != 0:
                    Account.objects.filter(user_id=uid, id=old_source_id).update(
                        current_balance=F("current_balance") - amount_delta,
                        updated_at=now,
                    )
                    Account.objects.filter(user_id=uid, id=old_dest_id).update(
                        current_balance=F("current_balance") + amount_delta,
                        updated_at=now,
                    )
                self._update_fee_in_atomic(
                    uid, debit_id, old_source_id, fee_amount, tx_date, now
                )

        debit = self.get_by_id(debit_id)  # type: ignore[attr-defined]
        credit = self.get_by_id(credit_id)  # type: ignore[attr-defined]
        logger.info("transfer.updated id=%s user=%s", tx_id, uid)
        return debit or {}, credit or {}

    def update_exchange(
        self,
        tx_id: str,
        amount: float | None,
        rate: float | None,
        counter_amount: float | None,
        note: str | None,
        tx_date: date,
        source_id: str | None = None,
        dest_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Update both legs of an exchange atomically.

        source_id / dest_id: pass new account IDs to reassign the exchange.
        If omitted, the existing accounts are kept.
        Performs undo/redo balance reconciliation when accounts change.
        Returns (debit_leg, credit_leg) dicts after update.
        """
        uid = self.user_id  # type: ignore[attr-defined]

        tx = self.get_by_id(tx_id)  # type: ignore[attr-defined]
        if not tx:
            raise ValueError(f"Transaction not found: {tx_id}")
        if tx.get("type") != "exchange":
            raise ValueError(f"Transaction {tx_id} is not an exchange")

        linked_id = tx.get("linked_transaction_id")
        if not linked_id:
            raise ValueError(f"Exchange {tx_id} has no linked leg")

        linked_tx = self.get_by_id(linked_id)  # type: ignore[attr-defined]
        if not linked_tx:
            raise ValueError(f"Linked leg not found: {linked_id}")

        # Normalize: always work in terms of debit (source) and credit (dest) legs
        if Decimal(str(tx["balance_delta"])) < 0:
            debit_tx, credit_tx = tx, linked_tx
            debit_id, credit_id = tx_id, str(linked_id)
        else:
            debit_tx, credit_tx = linked_tx, tx
            debit_id, credit_id = str(linked_id), tx_id

        old_source_id = str(debit_tx["account_id"])
        old_dest_id = str(credit_tx["account_id"])
        new_source_id = source_id or old_source_id
        new_dest_id = dest_id or old_dest_id

        source_changing = new_source_id != old_source_id
        dest_changing = new_dest_id != old_dest_id

        if source_changing or dest_changing:
            new_src_acc = self._get_account(new_source_id)  # type: ignore[attr-defined]
            new_dest_acc = self._get_account(new_dest_id)  # type: ignore[attr-defined]
            if new_src_acc["currency"] == new_dest_acc["currency"]:
                raise ValueError(
                    "Exchange requires different currencies; accounts have the same currency"
                )
            src_currency = new_src_acc["currency"]
            dest_currency = new_dest_acc["currency"]
        else:
            src_currency = debit_tx["currency"]
            dest_currency = credit_tx["currency"]

        source_is_egp = src_currency == "EGP"
        adj_rate = rate
        if source_is_egp and adj_rate is not None and adj_rate > 0:
            adj_rate = 1.0 / adj_rate

        resolved_amount, formula_rate, resolved_counter = resolve_exchange_fields(
            amount, adj_rate, counter_amount
        )

        display_rate = formula_rate
        if source_is_egp:
            display_rate = 1.0 / formula_rate

        old_debit_delta = Decimal(str(debit_tx["balance_delta"]))
        old_credit_delta = Decimal(str(credit_tx["balance_delta"]))

        new_debit_delta = -Decimal(str(resolved_amount))
        new_credit_delta = Decimal(str(resolved_counter))

        now = django_tz.now()

        with transaction.atomic():
            Transaction.objects.filter(user_id=uid, id=debit_id).update(
                amount=Decimal(str(resolved_amount)),
                currency=src_currency,
                account_id=new_source_id,
                counter_account_id=new_dest_id,
                balance_delta=new_debit_delta,
                exchange_rate=round(display_rate, 6),
                counter_amount=round(resolved_counter, 2),
                note=note,
                date=tx_date,
                updated_at=now,
            )
            Transaction.objects.filter(user_id=uid, id=credit_id).update(
                amount=Decimal(str(resolved_counter)),
                currency=dest_currency,
                account_id=new_dest_id,
                counter_account_id=new_source_id,
                balance_delta=new_credit_delta,
                exchange_rate=round(display_rate, 6),
                counter_amount=round(resolved_amount, 2),
                note=note,
                date=tx_date,
                updated_at=now,
            )

            if source_changing or dest_changing:
                # Undo old state: restore old account balances
                Account.objects.filter(user_id=uid, id=old_source_id).update(
                    current_balance=F("current_balance") - old_debit_delta,
                    updated_at=now,
                )
                Account.objects.filter(user_id=uid, id=old_dest_id).update(
                    current_balance=F("current_balance") - old_credit_delta,
                    updated_at=now,
                )
                # Apply new state: debit/credit new accounts
                Account.objects.filter(user_id=uid, id=new_source_id).update(
                    current_balance=F("current_balance") + new_debit_delta,
                    updated_at=now,
                )
                Account.objects.filter(user_id=uid, id=new_dest_id).update(
                    current_balance=F("current_balance") + new_credit_delta,
                    updated_at=now,
                )
            else:
                debit_adjustment = new_debit_delta - old_debit_delta
                if debit_adjustment != 0:
                    Account.objects.filter(user_id=uid, id=old_source_id).update(
                        current_balance=F("current_balance") + debit_adjustment,
                        updated_at=now,
                    )
                credit_adjustment = new_credit_delta - old_credit_delta
                if credit_adjustment != 0:
                    Account.objects.filter(user_id=uid, id=old_dest_id).update(
                        current_balance=F("current_balance") + credit_adjustment,
                        updated_at=now,
                    )

        # Log rate (non-critical)
        try:
            source_label = f"{src_currency}/{dest_currency}"
            ExchangeRateLog.objects.create(
                date=tx_date,
                rate=round(display_rate, 6),
                source=source_label,
                note=note,
            )
        except Exception:
            logger.warning(
                "Failed to log exchange rate on update (non-critical)", exc_info=True
            )

        debit = self.get_by_id(debit_id)  # type: ignore[attr-defined]
        credit = self.get_by_id(credit_id)  # type: ignore[attr-defined]
        logger.info("exchange.updated id=%s user=%s", tx_id, uid)
        return debit or {}, credit or {}

    def _update_fee_in_atomic(
        self,
        uid: str,
        tx_id: str,
        account_id: str,
        fee_amount: float | None,
        tx_date: date,
        now: Any,
    ) -> None:
        """Add, change, or remove fee inside an already-open atomic block."""
        existing_fee = Transaction.objects.filter(
            user_id=uid,
            linked_transaction_id=tx_id,
            note="Transfer fee",  # type: ignore[misc]
        ).first()
        new_fee = Decimal(str(fee_amount)) if fee_amount and fee_amount > 0 else None
        old_fee = Decimal(str(existing_fee.amount)) if existing_fee else None

        if old_fee == new_fee:
            return

        if existing_fee:
            Account.objects.filter(user_id=uid, id=account_id).update(
                current_balance=F("current_balance")
                + Decimal(str(existing_fee.amount)),
                updated_at=now,
            )
            existing_fee.delete()

        if new_fee:
            fees_cat = (
                Category.objects.filter(user_id=uid, name__en__icontains="fee")
                .order_by("name")
                .first()
            )
            acc = Account.objects.get(id=account_id)
            Transaction.objects.create(
                id=str(uuid.uuid4()),
                user_id=uid,
                type="expense",
                amount=new_fee,
                currency=acc.currency,
                account_id=account_id,
                linked_transaction_id=tx_id,
                category_id=fees_cat.id if fees_cat else None,
                note="Transfer fee",
                date=tx_date,
                balance_delta=-new_fee,
            )
            Account.objects.filter(user_id=uid, id=account_id).update(
                current_balance=F("current_balance") - new_fee,
                updated_at=now,
            )
