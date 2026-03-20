"""Transfer, exchange, and Fawry cashout operations.

TransferMixin is mixed into TransactionService and relies on methods from
TransactionServiceBase (self._get_account, self.get_by_id, self.user_id, etc.).
"""

import logging
import uuid
from datetime import date, datetime
from typing import Any

from django.db import connection, transaction

from .utils import calculate_instapay_fee, resolve_exchange_fields

logger = logging.getLogger(__name__)


class TransferMixin:
    """Mixin providing transfer, InstaPay, exchange, and Fawry cashout methods."""

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
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a same-currency transfer between two accounts.

        6-step atomic: debit + credit + link + update source + update dest + commit.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
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

        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Debit leg (source)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [
                        debit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        amount,
                        actual_currency,
                        source_id,
                        dest_id,
                        note,
                        tx_date,
                        -amount,
                    ],
                )
                # Credit leg (destination)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [
                        credit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        amount,
                        actual_currency,
                        dest_id,
                        source_id,
                        note,
                        tx_date,
                        amount,
                    ],
                )
                # Link bidirectionally
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, debit_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [debit_id, credit_id, self.user_id],  # type: ignore[attr-defined]
                )
                # Update balances
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, source_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, dest_id, self.user_id],  # type: ignore[attr-defined]
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

    def create_instapay_transfer(
        self,
        source_id: str,
        dest_id: str,
        amount: float,
        currency: str | None,
        note: str | None,
        tx_date: date | str | None,
        fees_category_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], float]:
        """Create an InstaPay transfer with automatic fee.

        Source loses amount + fee, dest gains amount.
        Returns (debit_tx, credit_tx, fee_amount).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if not source_id or not dest_id:
            raise ValueError("Both source and destination account_id required")
        if source_id == dest_id:
            raise ValueError("Cannot transfer to the same account")

        src_acc = self._get_account(source_id)  # type: ignore[attr-defined]
        dest_acc = self._get_account(dest_id)  # type: ignore[attr-defined]
        if src_acc["currency"] != dest_acc["currency"]:
            raise ValueError("InstaPay requires same currency")

        actual_currency = src_acc["currency"]
        fee = calculate_instapay_fee(amount)

        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        instapay_note = "InstaPay transfer"
        if note:
            instapay_note = f"{note} (InstaPay)"

        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())
        fee_tx_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Debit leg
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, fee_amount, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s)""",
                    [
                        debit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        amount,
                        actual_currency,
                        source_id,
                        dest_id,
                        instapay_note,
                        fee,
                        tx_date,
                        -amount,
                    ],
                )
                # Credit leg
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [
                        credit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        amount,
                        actual_currency,
                        dest_id,
                        source_id,
                        instapay_note,
                        tx_date,
                        amount,
                    ],
                )
                # Link
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, debit_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [debit_id, credit_id, self.user_id],  # type: ignore[attr-defined]
                )
                # Fee transaction (separate expense)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        category_id, note, date, balance_delta)
                       VALUES (%s, %s, 'expense'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [
                        fee_tx_id,
                        self.user_id,  # type: ignore[attr-defined]
                        fee,
                        actual_currency,
                        source_id,
                        fees_category_id,
                        "InstaPay fee",
                        tx_date,
                        -fee,
                    ],
                )
                # Update balances: source loses amount + fee
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount + fee, source_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, dest_id, self.user_id],  # type: ignore[attr-defined]
                )

        logger.info(
            "transaction.instapay_created currency=%s user=%s",
            actual_currency,
            self.user_id,  # type: ignore[attr-defined]
        )
        debit_tx = self.get_by_id(debit_id)  # type: ignore[attr-defined]
        credit_tx = self.get_by_id(credit_id)  # type: ignore[attr-defined]
        return debit_tx or {}, credit_tx or {}, fee

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

        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Debit leg (source currency out)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, exchange_rate, counter_amount,
                        note, date, balance_delta)
                       VALUES (%s, %s, 'exchange'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        debit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        resolved_amount,
                        src_acc["currency"],
                        source_id,
                        dest_id,
                        round(display_rate, 6),
                        round(resolved_counter, 2),
                        note,
                        tx_date,
                        -resolved_amount,
                    ],
                )
                # Credit leg (dest currency in)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, exchange_rate, counter_amount,
                        note, date, balance_delta)
                       VALUES (%s, %s, 'exchange'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        credit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        resolved_counter,
                        dest_acc["currency"],
                        dest_id,
                        source_id,
                        round(display_rate, 6),
                        round(resolved_amount, 2),
                        note,
                        tx_date,
                        resolved_counter,
                    ],
                )
                # Link
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, debit_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [debit_id, credit_id, self.user_id],  # type: ignore[attr-defined]
                )
                # Update balances
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [resolved_amount, source_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [resolved_counter, dest_id, self.user_id],  # type: ignore[attr-defined]
                )

        # Log exchange rate (non-critical)
        try:
            source_label = f"{src_acc['currency']}/{dest_acc['currency']}"
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO exchange_rate_log (id, date, rate, source, note, created_at)
                       VALUES (%s, %s, %s, %s, %s, NOW())""",
                    [
                        str(uuid.uuid4()),
                        tx_date,
                        round(display_rate, 6),
                        source_label,
                        note,
                    ],
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
    # Fawry Cashout
    # -------------------------------------------------------------------

    def create_fawry_cashout(
        self,
        credit_card_id: str,
        prepaid_id: str,
        amount: float,
        fee: float,
        currency: str | None,
        note: str | None,
        tx_date: date | str | None,
        fees_category_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a Fawry credit card cash-out.

        CC charged amount+fee (expense), prepaid gets amount (income).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if fee < 0:
            raise ValueError("Fee cannot be negative")
        if not credit_card_id or not prepaid_id:
            raise ValueError("Both credit card and prepaid account IDs are required")
        if credit_card_id == prepaid_id:
            raise ValueError("Credit card and prepaid account must be different")

        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        total_charge = amount + fee
        cc_acc = self._get_account(credit_card_id)  # type: ignore[attr-defined]
        actual_currency = cc_acc["currency"]

        charge_note = "Fawry cash-out"
        if note:
            charge_note = f"{note} (Fawry cash-out)"
        credit_note = "Fawry top-up"
        if note:
            credit_note = f"{note} (Fawry top-up)"

        charge_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # CC charge (expense: amount + fee)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, category_id, fee_amount, note, date,
                        balance_delta)
                       VALUES (%s, %s, 'expense'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        charge_id,
                        self.user_id,  # type: ignore[attr-defined]
                        total_charge,
                        actual_currency,
                        credit_card_id,
                        prepaid_id,
                        fees_category_id,
                        fee,
                        charge_note,
                        tx_date,
                        -total_charge,
                    ],
                )
                # Prepaid credit (income: net amount)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'income'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [
                        credit_id,
                        self.user_id,  # type: ignore[attr-defined]
                        amount,
                        actual_currency,
                        prepaid_id,
                        credit_card_id,
                        credit_note,
                        tx_date,
                        amount,
                    ],
                )
                # Link
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, charge_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [charge_id, credit_id, self.user_id],  # type: ignore[attr-defined]
                )
                # Update balances
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [total_charge, credit_card_id, self.user_id],  # type: ignore[attr-defined]
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, prepaid_id, self.user_id],  # type: ignore[attr-defined]
                )

        logger.info(
            "transaction.fawry_cashout_created currency=%s user=%s",
            actual_currency,
            self.user_id,  # type: ignore[attr-defined]
        )
        charge_tx = self.get_by_id(charge_id)  # type: ignore[attr-defined]
        credit_tx = self.get_by_id(credit_id)  # type: ignore[attr-defined]
        return charge_tx or {}, credit_tx or {}
