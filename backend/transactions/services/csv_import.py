import csv
import hashlib
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from transactions.models import Transaction

logger = logging.getLogger(__name__)


class CsvImportService:
    def __init__(self, user_id: str, tz_name: str = "UTC"):
        self.user_id = user_id
        self.tz_name = tz_name
        from transactions.services import TransactionService

        self.tx_service = TransactionService(user_id, ZoneInfo("UTC"))

    def parse_headers(self, file_content: str) -> list[str]:
        f = io.StringIO(file_content)
        reader = csv.reader(f)
        try:
            return next(reader)
        except StopIteration:
            raise ValueError("CSV is empty")

    def _parse_date(self, val: str) -> str | None:
        # try a few common formats
        val = val.strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(val, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    def parse_rows(
        self, file_content: str, mapping: dict[str, str], account_id: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """
        Parses the CSV content using the given column mapping.
        mapping has keys like: 'col_date', 'col_amount', 'col_type', 'col_note'
        Returns: (parsed_transactions, duplicates, validation_errors)
        """
        f = io.StringIO(file_content)
        reader = csv.DictReader(f)

        parsed = []
        errors = []

        date_col = mapping.get("date")
        amount_col = mapping.get("amount")
        type_col = mapping.get("type")
        note_col = mapping.get("note")

        if not (date_col and amount_col):
            raise ValueError("Date and Amount mapping is required")

        row_index = 2  # 1-based index including header
        for row in reader:
            try:
                date_str = row.get(date_col, "")
                parsed_date = self._parse_date(date_str)
                if not parsed_date:
                    raise ValueError(f"Invalid date format: {date_str}")

                amount_str = row.get(amount_col, "").replace(",", "").strip()
                try:
                    amount = Decimal(amount_str)
                except InvalidOperation:
                    raise ValueError(f"Invalid amount format: {amount_str}")

                # Determine type
                tx_type = "expense"
                if type_col and row.get(type_col):
                    t = str(row.get(type_col)).lower()
                    if t in ("income", "credit", "cr", "+", "deposit"):
                        tx_type = "income"
                    elif t in ("expense", "debit", "dr", "-", "withdrawal"):
                        tx_type = "expense"
                    elif amount > 0:
                        tx_type = "income"
                    else:
                        tx_type = "expense"
                else:
                    if amount > 0:
                        tx_type = "income"
                    else:
                        tx_type = "expense"

                final_amount = abs(amount)

                note = row.get(note_col, "") if note_col else ""

                # Auto-categorize
                category_id = self.tx_service.suggest_category(note)

                parsed.append(
                    {
                        "date": parsed_date,
                        "amount": str(final_amount),
                        "type": tx_type,
                        "note": note,
                        "account_id": account_id,
                        "category_id": category_id,
                        "row_index": row_index,
                    }
                )
            except Exception as e:
                errors.append(f"Row {row_index}: {str(e)}")
            row_index += 1

        # duplicate detection
        duplicates = []
        if parsed:
            min_date = min(str(p["date"]) for p in parsed)
            max_date = max(str(p["date"]) for p in parsed)

            existing = (
                Transaction.objects.for_user(self.user_id)
                .filter(
                    date__gte=min_date,
                    date__lte=max_date,
                )
                .values("date", "amount", "note")
            )

            existing_hashes = set()
            for ex in existing:
                amount_str = f"{float(ex['amount']):.2f}"
                note = ex["note"] or ""
                date_str = ex["date"].strftime("%Y-%m-%d")
                hash_base = f"{date_str}_{amount_str}_{note}"
                h = hashlib.sha256(hash_base.encode()).hexdigest()
                existing_hashes.add(h)

            for p in parsed:
                amount_str = f"{float(str(p['amount'])):.2f}"
                h = hashlib.sha256(
                    f"{p['date']}_{amount_str}_{p['note']}".encode()
                ).hexdigest()
                p["hash"] = h
                if h in existing_hashes:
                    duplicates.append(p)
                    p["is_duplicate"] = True
                else:
                    p["is_duplicate"] = False

        return parsed, duplicates, errors
