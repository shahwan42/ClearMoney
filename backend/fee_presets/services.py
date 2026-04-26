"""Fee preset services — seeding, listing, CRUD helpers."""

import logging
from decimal import Decimal
from typing import Any, TypedDict

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction as db_transaction

from .models import (
    CALC_TYPE_CHOICES,
    CALC_TYPE_FLAT,
    CALC_TYPE_PERCENT,
    FeePreset,
    compute_fee,
)

logger = logging.getLogger(__name__)


class DefaultPresetSpec(TypedDict):
    name: str
    currency: str
    calc_type: str
    value: Decimal
    min_fee: Decimal | None
    max_fee: Decimal | None
    sort_order: int


# Egyptian-rail defaults seeded for new users.
DEFAULT_EGP_PRESETS: list[DefaultPresetSpec] = [
    {
        "name": "InstaPay",
        "currency": "EGP",
        "calc_type": CALC_TYPE_PERCENT,
        "value": Decimal("0.001"),
        "min_fee": Decimal("0.50"),
        "max_fee": Decimal("20.00"),
        "sort_order": 1,
    },
    {
        "name": "ATM",
        "currency": "EGP",
        "calc_type": CALC_TYPE_FLAT,
        "value": Decimal("5.00"),
        "min_fee": None,
        "max_fee": None,
        "sort_order": 2,
    },
]


def seed_default_fee_presets(user_id: str) -> int:
    """Create default fee presets for a user. Idempotent.

    Returns count of presets newly created.
    """
    created = 0
    try:
        with db_transaction.atomic():
            for spec in DEFAULT_EGP_PRESETS:
                _, was_created = FeePreset.objects.get_or_create(
                    user_id=user_id,
                    name=spec["name"],
                    currency=spec["currency"],
                    defaults={
                        "calc_type": spec["calc_type"],
                        "value": spec["value"],
                        "min_fee": spec["min_fee"],
                        "max_fee": spec["max_fee"],
                        "sort_order": spec["sort_order"],
                    },
                )
                if was_created:
                    created += 1
    except Exception:
        logger.exception("fee_presets.seed_failed user_id=%s", user_id)
    return created


class FeePresetService:
    """User-scoped fee preset operations."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    def _qs(self) -> Any:
        return FeePreset.objects.for_user(self.user_id)

    def list_active(self, currency: str | None = None) -> list[dict[str, Any]]:
        """Return non-archived presets, optionally filtered by currency."""
        qs = self._qs().filter(archived=False)
        if currency:
            qs = qs.filter(currency=currency)
        return [_to_dict(p) for p in qs.order_by("sort_order", "name")]

    def list_all(self) -> list[dict[str, Any]]:
        """Return all presets including archived (for settings page)."""
        return [
            _to_dict(p) for p in self._qs().order_by("archived", "sort_order", "name")
        ]

    def get(self, preset_id: str) -> FeePreset:
        try:
            obj: FeePreset = self._qs().get(id=preset_id)
            return obj
        except FeePreset.DoesNotExist as e:
            raise ObjectDoesNotExist(f"Fee preset not found: {preset_id}") from e

    def create(
        self,
        *,
        name: str,
        currency: str,
        calc_type: str,
        value: Decimal | float | str,
        min_fee: Decimal | float | str | None = None,
        max_fee: Decimal | float | str | None = None,
        sort_order: int = 0,
    ) -> FeePreset:
        _validate(
            calc_type=calc_type,
            value=Decimal(str(value)),
            min_fee=Decimal(str(min_fee)) if min_fee not in (None, "") else None,
            max_fee=Decimal(str(max_fee)) if max_fee not in (None, "") else None,
        )
        preset = FeePreset.objects.create(
            user_id=self.user_id,
            name=name.strip(),
            currency=currency.strip().upper(),
            calc_type=calc_type,
            value=Decimal(str(value)),
            min_fee=Decimal(str(min_fee)) if min_fee not in (None, "") else None,
            max_fee=Decimal(str(max_fee)) if max_fee not in (None, "") else None,
            sort_order=sort_order,
        )
        logger.info("fee_preset.created id=%s user=%s", preset.id, self.user_id)
        return preset

    def update(self, preset_id: str, **fields: Any) -> FeePreset:
        preset = self.get(preset_id)
        for key in (
            "name",
            "currency",
            "calc_type",
            "value",
            "min_fee",
            "max_fee",
            "sort_order",
        ):
            if key in fields:
                setattr(preset, key, fields[key])
        _validate(
            calc_type=preset.calc_type,
            value=Decimal(str(preset.value)),
            min_fee=preset.min_fee,
            max_fee=preset.max_fee,
        )
        preset.save()
        return preset

    def archive(self, preset_id: str) -> None:
        preset = self.get(preset_id)
        preset.archived = True
        preset.save(update_fields=["archived", "updated_at"])

    def unarchive(self, preset_id: str) -> None:
        preset = self.get(preset_id)
        preset.archived = False
        preset.save(update_fields=["archived", "updated_at"])

    def compute(self, preset_id: str, amount: Decimal | float | int) -> Decimal:
        return compute_fee(self.get(preset_id), amount)


def _validate(
    *,
    calc_type: str,
    value: Decimal,
    min_fee: Decimal | None,
    max_fee: Decimal | None,
) -> None:
    valid_types = {ct[0] for ct in CALC_TYPE_CHOICES}
    if calc_type not in valid_types:
        raise ValueError(f"Invalid calc_type: {calc_type}")
    if value <= 0:
        raise ValueError("Fee value must be greater than zero")
    if calc_type == CALC_TYPE_PERCENT and value > 1:
        raise ValueError("Percent value must be a fraction (e.g. 0.001 = 0.1%)")
    if min_fee is not None and min_fee < 0:
        raise ValueError("min_fee cannot be negative")
    if max_fee is not None and max_fee < 0:
        raise ValueError("max_fee cannot be negative")
    if min_fee is not None and max_fee is not None and min_fee > max_fee:
        raise ValueError("min_fee cannot exceed max_fee")


def _to_dict(p: FeePreset) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "currency": p.currency,
        "calc_type": p.calc_type,
        "value": p.value,
        "min_fee": p.min_fee,
        "max_fee": p.max_fee,
        "archived": p.archived,
        "sort_order": p.sort_order,
    }
