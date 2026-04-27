"""
Transaction views — all /transactions/*, /transfers/*, /exchange/*, /transfer/new/*,
/batch-entry, and /sync/transactions routes.

Like Laravel's TransactionController — thin views that delegate to services.
"""

import json
import logging
from datetime import date

from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import Account
from core.decorators import inject_service
from core.htmx import error_response, render_htmx_result
from core.ratelimit import api_rate, general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none, parse_json_body
from people.models import Person
from transactions.models import Transaction, VirtualAccountAllocation

from .services import TransactionService

logger = logging.getLogger(__name__)

_ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_ATTACHMENT_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
}


def _validate_attachment(file: UploadedFile | None) -> str | None:
    """Return an error string if the uploaded file is invalid, else None."""
    if file is None:
        return None
    if file.size and file.size > _ATTACHMENT_MAX_BYTES:
        return "Attachment must be 5 MB or smaller."
    ct = getattr(file, "content_type", "") or ""
    if ct not in _ATTACHMENT_ALLOWED_TYPES:
        return "Attachment must be a JPEG, PNG, GIF, WebP image or PDF."
    return None


# ---------------------------------------------------------------------------
# Page Views
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET", "POST"])
def transactions_list(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transactions — full page. POST /transactions — create (HTMX)."""
    if request.method == "POST":
        return transaction_create(request)
    offset = int(request.GET.get("offset", 0))
    filters = {
        "account_id": request.GET.get("account_id", ""),
        "category_id": request.GET.get("category_id", ""),
        "type": request.GET.get("type", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "search": request.GET.get("search", ""),
        "tag": request.GET.get("tag", ""),
        "limit": 50,
        "offset": offset,
    }
    transactions, has_more = svc.get_filtered_enriched(filters)
    accounts = svc.get_accounts()
    categories = svc.get_categories()

    logger.info("page viewed: transactions, user=%s", request.user_email)
    return render(
        request,
        "transactions/transactions.html",
        {
            "data": {
                "transactions": transactions,
                "accounts": accounts,
                "categories": categories,
                "has_more": has_more,
                "next_offset": offset + 50,
                "account_id": filters["account_id"],
                "category_id": filters["category_id"],
                "type": filters["type"],
                "date_from": filters["date_from"],
                "date_to": filters["date_to"],
                "search": filters["search"],
                "tag": filters["tag"],
            },
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def transactions_list_partial(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transactions/list — HTMX partial for filter updates."""
    offset = int(request.GET.get("offset", 0))
    filters = {
        "account_id": request.GET.get("account_id", ""),
        "category_id": request.GET.get("category_id", ""),
        "type": request.GET.get("type", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "search": request.GET.get("search", ""),
        "tag": request.GET.get("tag", ""),
        "limit": 50,
        "offset": offset,
    }
    transactions, has_more = svc.get_filtered_enriched(filters)

    logger.info("partial loaded: transaction-list, user=%s", request.user_email)
    return render(
        request,
        "transactions/_transaction_list.html",
        {
            "data": {
                "transactions": transactions,
                "has_more": has_more,
                "next_offset": offset + 50,
                "account_id": filters["account_id"],
                "category_id": filters["category_id"],
                "type": filters["type"],
                "date_from": filters["date_from"],
                "date_to": filters["date_to"],
                "search": filters["search"],
                "tag": filters["tag"],
            },
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def transaction_new(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transactions/new — full transaction form page. Supports ?dup=<id>."""
    from transactions.services import TagService

    prefill = None
    dup_id = request.GET.get("dup")
    if dup_id:
        prefill = svc.get_by_id(dup_id)
        if prefill and prefill.get("type") in ("transfer", "exchange"):
            return HttpResponseRedirect(f"/transfer/new?dup={dup_id}")

    selected_type = (
        "income" if prefill and prefill.get("type") == "income" else "expense"
    )
    expense_accounts = svc.get_accounts("expense")
    income_accounts = svc.get_accounts("income")
    accounts = income_accounts if selected_type == "income" else expense_accounts
    categories = svc.get_categories()
    virtual_accounts = svc.get_virtual_accounts()
    tag_names = [
        t["name"] for t in TagService(request.user_id, request.tz).get_all_with_usage()
    ]

    logger.info("page viewed: transaction-new, user=%s", request.user_email)
    return render(
        request,
        "transactions/transaction_new.html",
        {
            "accounts": accounts,
            "expense_accounts": expense_accounts,
            "income_accounts": income_accounts,
            "categories": categories,
            "virtual_accounts": virtual_accounts,
            "today": date.today(),
            "prefill": prefill,
            "tag_names": tag_names,
        },
    )


# ---------------------------------------------------------------------------
# CRUD Mutations
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["POST"])
def transaction_create(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /transactions — create expense/income transaction (HTMX)."""
    try:
        attachment = request.FILES.get("attachment")
        att_err = _validate_attachment(attachment)
        if att_err:
            return error_response(att_err)
        data = {
            "type": request.POST.get("type", ""),
            "amount": request.POST.get("amount", "0"),
            "account_id": request.POST.get("account_id", ""),
            "category_id": request.POST.get("category_id", ""),
            "note": request.POST.get("note", ""),
            "date": request.POST.get("date", ""),
            "tags": request.POST.get("tags", ""),
            "attachment": attachment,
        }
        tx, new_balance = svc.create(data)

        # Optional fee → separate linked expense transaction
        fee_raw = request.POST.get("fee_amount", "")
        fee_preset_id = request.POST.get("fee_preset_id", "")
        fee_tx = None
        if fee_raw:
            fee = parse_float_or_none(fee_raw)
            if fee and fee > 0:
                fee_tx = svc.create_fee_for_transaction(
                    parent_tx=tx,
                    fee_amount=fee,
                    tx_date=request.POST.get("date") or None,
                    fee_preset_id=fee_preset_id if fee_preset_id else None,
                )

        # Virtual account allocation
        va_id = request.POST.get("virtual_account_id", "")
        if va_id:
            alloc_amount = float(request.POST.get("amount", "0"))
            if tx["type"] == "expense":
                alloc_amount = -alloc_amount
            try:
                svc.allocate_to_virtual_account(tx["id"], va_id, alloc_amount)
            except ValueError as e:
                logger.warning("VA allocation failed: %s", e)
            # Also allocate fee tx to same VA
            if fee_tx:
                try:
                    svc.allocate_to_virtual_account(
                        fee_tx["id"], va_id, -float(fee_tx["amount"])
                    )
                except ValueError as e:
                    logger.warning("VA fee allocation failed: %s", e)

        return render(
            request,
            "transactions/_transaction_success.html",
            {
                "tx": tx,
                "new_balance": new_balance,
                "currency": tx["currency"],
            },
        )
    except ValueError as e:
        return error_response(str(e))


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def transaction_edit_form(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """GET /transactions/edit/<id> — inline edit form partial (HTMX)."""
    from decimal import Decimal as _Decimal

    tx = svc.get_by_id(str(tx_id))
    if not tx:
        return HttpResponse("Not found", status=404)

    categories = svc.get_categories()
    virtual_accounts = svc.get_virtual_accounts()
    selected_va_id = svc.get_allocation_for_tx(str(tx_id))

    # Look up existing linked fee transaction (covers both "Transaction fee" and "Transfer fee")
    fee_tx = (
        Transaction.objects.for_user(request.user_id)
        .filter(
            linked_transaction_id=str(tx_id),
            note__in=["Transaction fee", "Transfer fee"],
        )
        .first()
    )

    # For transfers: normalize to debit leg to determine source/dest account IDs
    transfer_source_id = None
    transfer_dest_id = None
    transfer_accounts: list[dict] = []
    if tx.get("type") == "transfer":
        linked_id = tx.get("linked_transaction_id")
        linked_tx = svc.get_by_id(str(linked_id)) if linked_id else None
        if linked_tx:
            balance_delta = tx.get("balance_delta") or 0
            if _Decimal(str(balance_delta)) < 0:
                # tx is the debit (source) leg
                transfer_source_id = str(tx["account_id"])
                transfer_dest_id = str(linked_tx["account_id"])
                debit_leg_id = str(tx_id)
            else:
                # tx is the credit (dest) leg; linked_tx is debit
                transfer_source_id = str(linked_tx["account_id"])
                transfer_dest_id = str(tx["account_id"])
                debit_leg_id = str(linked_id)
            # Fee is always linked to the debit leg
            if not fee_tx:
                fee_tx = (
                    Transaction.objects.for_user(request.user_id)
                    .filter(
                        linked_transaction_id=debit_leg_id,
                        note="Transfer fee",
                    )
                    .first()
                )
        transfer_accounts = svc.get_accounts()

    # For exchanges: resolve source/dest accounts and build dropdown lists
    counter_account = None
    exchange_source_id = ""
    exchange_dest_id = ""
    exchange_accounts: list[dict] = []
    exchange_dest_accounts: list[dict] = []
    exchange_rate_label = ""
    if tx.get("type") == "exchange":
        all_exchange_accounts = svc.get_accounts()
        # Normalize to debit/credit legs
        linked_id = tx.get("linked_transaction_id")
        linked_ex = svc.get_by_id(str(linked_id)) if linked_id else None
        if linked_ex:
            balance_delta = tx.get("balance_delta") or 0
            if _Decimal(str(balance_delta)) < 0:
                ex_debit, ex_credit = tx, linked_ex
            else:
                ex_debit, ex_credit = linked_ex, tx
            exchange_source_id = str(ex_debit["account_id"])
            exchange_dest_id = str(ex_credit["account_id"])
        src_currency = ex_debit["currency"] if linked_ex else tx.get("currency", "")
        dest_currency = ex_credit["currency"] if linked_ex else ""
        exchange_rate_label = (
            f"{dest_currency} per 1 {src_currency}" if dest_currency else ""
        )
        exchange_accounts = all_exchange_accounts
        exchange_dest_accounts = [
            a for a in all_exchange_accounts if a["currency"] != src_currency
        ]
        # Normalize tx to debit leg so form shows debit-leg amount/currency
        if linked_ex:
            tx = ex_debit
        # Legacy counter_account for backward compat
        if tx.get("counter_account_id"):
            from accounts.models import Account as _Acc

            counter_account = (
                _Acc.objects.for_user(request.user_id)
                .filter(id=tx["counter_account_id"])
                .values("name", "currency")
                .first()
            )

    from transactions.services import TagService

    tag_names = [
        t["name"] for t in TagService(request.user_id, request.tz).get_all_with_usage()
    ]

    logger.info("partial loaded: transaction-edit-form, user=%s", request.user_email)
    return render(
        request,
        "transactions/_transaction_edit_form.html",
        {
            "tx": tx,
            "categories": categories,
            "selected_category_id": tx.get("category_id", ""),
            "virtual_accounts": virtual_accounts,
            "selected_va_id": selected_va_id or "",
            "existing_fee_amount": fee_tx.amount if fee_tx else "",
            "tag_names": tag_names,
            "today": date.today(),
            "counter_account": counter_account,
            "transfer_source_id": transfer_source_id or "",
            "transfer_dest_id": transfer_dest_id or "",
            "transfer_accounts": transfer_accounts,
            "exchange_source_id": exchange_source_id,
            "exchange_dest_id": exchange_dest_id,
            "exchange_accounts": exchange_accounts,
            "exchange_dest_accounts": exchange_dest_accounts,
            "exchange_rate_label": exchange_rate_label,
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def exchange_edit_dest_partial(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """GET /transactions/edit/<id>/exchange-dest — HTMX partial.

    Re-renders dest dropdown + rate section when source account changes.
    Query params: source_id (new source), current_dest_id (optional, for pre-selection).
    """
    from decimal import Decimal as _D

    source_id = request.GET.get("exchange_source_id", "")
    current_dest_id = request.GET.get("exchange_dest_id", "")

    all_accounts = svc.get_accounts()
    src_currency = ""
    if source_id:
        src_acc = next((a for a in all_accounts if str(a["id"]) == source_id), None)
        src_currency = src_acc["currency"] if src_acc else ""

    dest_accounts = (
        [a for a in all_accounts if a["currency"] != src_currency]
        if src_currency
        else all_accounts
    )

    # Detect if currency pair changed relative to original tx
    tx = svc.get_by_id(str(tx_id))
    pair_changed = False
    if tx and source_id:
        linked_id = tx.get("linked_transaction_id")
        linked_ex = svc.get_by_id(str(linked_id)) if linked_id else None
        if linked_ex:
            bal = tx.get("balance_delta") or 0
            orig_debit = tx if _D(str(bal)) < 0 else linked_ex
            orig_credit = linked_ex if _D(str(bal)) < 0 else tx
            orig_src_currency = orig_debit["currency"]
            orig_dest_id = str(orig_credit["account_id"])
            # pair changed if new source has different currency
            pair_changed = src_currency != orig_src_currency
            # pre-select current dest if compatible, else first dest account
            if not current_dest_id:
                current_dest_id = orig_dest_id

    dest_currency = ""
    if current_dest_id:
        dest_acc = next(
            (a for a in dest_accounts if str(a["id"]) == current_dest_id), None
        )
        dest_currency = (
            dest_acc["currency"]
            if dest_acc
            else (dest_accounts[0]["currency"] if dest_accounts else "")
        )

    if not dest_currency and dest_accounts:
        dest_currency = dest_accounts[0]["currency"]

    rate_label = (
        f"{dest_currency} per 1 {src_currency}"
        if src_currency and dest_currency
        else ""
    )

    return render(
        request,
        "transactions/_exchange_dest_partial.html",
        {
            "dest_accounts": dest_accounts,
            "exchange_dest_id": current_dest_id,
            "rate_label": rate_label,
            "pair_changed": pair_changed,
            "src_currency": src_currency,
            "dest_currency": dest_currency,
            "tx": tx,
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def transaction_detail_sheet(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """GET /transactions/detail/<id> — bottom sheet detail partial."""
    tx = svc.get_by_id_enriched(str(tx_id))
    if not tx:
        return HttpResponse("Not found", status=404)

    context: dict[str, object] = {
        "tx": tx,
        "counter_currency": None,
        "counter_account_name": None,
    }

    # Counter account name + currency (transfers/exchanges)
    if tx.get("counter_account_id"):
        counter = (
            Account.objects.for_user(request.user_id)
            .filter(id=tx["counter_account_id"])
            .values("name", "currency")
            .first()
        )
        if counter:
            context["counter_account_name"] = counter["name"]
            context["counter_currency"] = counter["currency"]

    # Person name (loans)
    if tx.get("person_id"):
        person_name = (
            Person.objects.for_user(request.user_id)
            .filter(id=tx["person_id"])
            .values_list("name", flat=True)
            .first()
        )
        context["person_name"] = person_name

    # Virtual account allocation
    va_alloc = (
        VirtualAccountAllocation.objects.filter(transaction_id=str(tx_id))
        .select_related("virtual_account")
        .values("virtual_account__name")
        .first()
    )
    if va_alloc:
        context["va_name"] = va_alloc["virtual_account__name"]

    # Linked fee transaction
    fee_tx = (
        Transaction.objects.for_user(request.user_id)
        .filter(linked_transaction_id=str(tx_id), note="Transaction fee")
        .values("amount", "currency")
        .first()
    )
    if fee_tx:
        context["fee_amount"] = fee_tx["amount"]
        context["fee_currency"] = fee_tx["currency"]

    # Recurring rule info
    if tx.get("recurring_rule_id"):
        from recurring.models import RecurringRule

        rule = (
            RecurringRule.objects.for_user(request.user_id)
            .filter(id=tx["recurring_rule_id"])
            .first()
        )
        if rule:
            context["recurring_rule_name"] = (
                rule.template_transaction.get("note") or rule.frequency.capitalize()
            )

    logger.info("partial loaded: transaction-detail-sheet, user=%s", request.user_email)
    return render(request, "transactions/_transaction_detail_sheet.html", context)


@csrf_exempt  # JSON API — authenticated via session, called by e2e helpers and HTMX (which sends X-CSRFToken anyway)
@general_rate
@require_http_methods(["PUT", "DELETE", "POST"])
def transaction_detail(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """PUT/DELETE /transactions/<id> — dispatches to update or delete."""
    if request.method == "DELETE":
        return transaction_delete(request, tx_id)
    # POST used for update-with-files since some browsers/HTMX setups have issues with PUT + multipart
    return transaction_update(request, tx_id)


@inject_service(TransactionService)
def transaction_update(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """PUT /transactions/<id> — update transaction (HTMX inline edit)."""
    # If POST, files are in request.FILES. If PUT, we have to be careful.
    # We'll support both.
    if request.method == "POST":
        data_source = request.POST
    else:
        body = (
            request.body.decode("utf-8")
            if isinstance(request.body, bytes)
            else str(request.body)
        )
        data_source = QueryDict(body)

    try:
        attachment = request.FILES.get("attachment")
        att_err = _validate_attachment(attachment)
        if att_err:
            return error_response(att_err)

        # Fetch existing tx to determine type before branching
        existing = svc.get_by_id(str(tx_id))
        if not existing:
            return HttpResponse("Not found", status=404)

        tx_type = existing["type"]
        tx_date_raw = data_source.get("date", "")
        tx_date = date.fromisoformat(tx_date_raw) if tx_date_raw else date.today()
        note = data_source.get("note", "") or None

        if tx_type == "transfer":
            amount = parse_float_or_none(data_source.get("amount", ""))
            if not amount:
                return error_response("Amount is required")
            fee_amount = parse_float_or_none(data_source.get("fee_amount", ""))
            source_id = data_source.get("source_id") or None
            dest_id = data_source.get("dest_id") or None
            debit, credit = svc.update_transfer(
                str(tx_id),
                amount=amount,
                note=note,
                tx_date=tx_date,
                fee_amount=fee_amount,
                source_id=source_id,
                dest_id=dest_id,
            )
            linked_id = debit.get("linked_transaction_id") or credit.get(
                "linked_transaction_id"
            )
            enriched_primary = svc.get_by_id_enriched(str(tx_id))
            response = render(
                request, "transactions/_transaction_row.html", {"tx": enriched_primary}
            )
            response["HX-Retarget"] = f"#tx-{tx_id}"
            response["HX-Reswap"] = "outerHTML"
            response["HX-Trigger"] = "closeEditSheet"
            if linked_id:
                enriched_linked = svc.get_by_id_enriched(str(linked_id))
                oob = render(
                    request,
                    "transactions/_transaction_row.html",
                    {"tx": enriched_linked},
                )
                oob_html = oob.content.decode()
                # Inject OOB swap attribute
                oob_html = oob_html.replace(
                    f'id="tx-{linked_id}"',
                    f'id="tx-{linked_id}" hx-swap-oob="outerHTML:#tx-{linked_id}"',
                    1,
                )
                response.content = response.content + oob_html.encode()
            return response

        elif tx_type == "exchange":
            amount = parse_float_or_none(data_source.get("amount", ""))
            rate = parse_float_or_none(data_source.get("rate", ""))
            counter_amount = parse_float_or_none(data_source.get("counter_amount", ""))
            exchange_source_id = data_source.get("exchange_source_id") or None
            exchange_dest_id = data_source.get("exchange_dest_id") or None
            debit, credit = svc.update_exchange(
                str(tx_id),
                amount=amount,
                rate=rate,
                counter_amount=counter_amount,
                note=note,
                tx_date=tx_date,
                source_id=exchange_source_id,
                dest_id=exchange_dest_id,
            )
            linked_id = debit.get("linked_transaction_id") or credit.get(
                "linked_transaction_id"
            )
            enriched_primary = svc.get_by_id_enriched(str(tx_id))
            response = render(
                request, "transactions/_transaction_row.html", {"tx": enriched_primary}
            )
            response["HX-Retarget"] = f"#tx-{tx_id}"
            response["HX-Reswap"] = "outerHTML"
            response["HX-Trigger"] = "closeEditSheet"
            if linked_id:
                enriched_linked = svc.get_by_id_enriched(str(linked_id))
                oob = render(
                    request,
                    "transactions/_transaction_row.html",
                    {"tx": enriched_linked},
                )
                oob_html = oob.content.decode()
                oob_html = oob_html.replace(
                    f'id="tx-{linked_id}"',
                    f'id="tx-{linked_id}" hx-swap-oob="outerHTML:#tx-{linked_id}"',
                    1,
                )
                response.content = response.content + oob_html.encode()
            return response

        else:
            data = {
                "type": data_source.get("type", ""),
                "amount": data_source.get("amount", "0"),
                "category_id": data_source.get("category_id", ""),
                "note": note,
                "date": tx_date_raw,
                "tags": data_source.get("tags", ""),
                "attachment": attachment,
            }
            tx, _ = svc.update(str(tx_id), data)

            # Handle fee and VA reallocation via service helper
            svc.apply_post_create_logic(
                tx,
                fee_amount=parse_float_or_none(data_source.get("fee_amount", "")),
                va_id=data_source.get("virtual_account_id"),
                tx_date=tx_date_raw,
                fee_preset_id=data_source.get("fee_preset_id", "") or None,
            )

            enriched = svc.get_by_id_enriched(str(tx_id))
            response = render(
                request, "transactions/_transaction_row.html", {"tx": enriched}
            )
            response["HX-Retarget"] = f"#tx-{tx_id}"
            response["HX-Reswap"] = "outerHTML"
            response["HX-Trigger"] = "closeEditSheet"
            return response

    except ValueError as e:
        return error_response(str(e))


@inject_service(TransactionService)
@require_http_methods(["POST"])
def transaction_delete_attachment(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """POST /transactions/<id>/delete-attachment — remove attachment."""
    svc.delete_attachment(str(tx_id))
    enriched = svc.get_by_id_enriched(str(tx_id))
    return render(
        request, "transactions/_transaction_detail_sheet.html", {"tx": enriched}
    )


@inject_service(TransactionService)
def transaction_delete(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """DELETE /transactions/<id> — delete transaction (HTMX removes row)."""
    try:
        svc.deallocate_from_virtual_accounts(str(tx_id))
        related_ids = svc.delete(str(tx_id))

        # Build OOB delete elements
        oob_html = "".join(
            f'<div id="tx-{rid}" hx-swap-oob="delete"></div>' for rid in related_ids
        )
        response = HttpResponse(oob_html)
        if related_ids:
            response["X-Related-Deleted"] = ",".join(related_ids)
        return response
    except ValueError as e:
        return error_response(str(e))


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def transaction_row(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """GET /transactions/row/<id> — single row partial (cancel edit)."""
    enriched = svc.get_by_id_enriched(str(tx_id))
    if not enriched:
        return HttpResponse("Not found", status=404)
    return render(request, "transactions/_transaction_row.html", {"tx": enriched})


# ---------------------------------------------------------------------------
# Transfer Unified Views (unified transfer/exchange)
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def transfer_new_unified(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transfer/new — unified transfer form page. Supports ?dup=<id>."""
    prefill = None
    dup_id = request.GET.get("dup")
    if dup_id:
        prefill = svc.get_by_id(dup_id)
    logger.info("page viewed: transfer-unified, user=%s", request.user_email)
    return render(
        request,
        "transactions/transfer_unified.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
            "prefill": prefill,
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def quick_transfer_unified(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transactions/quick-transfer-unified — quick transfer unified partial."""
    logger.info("partial loaded: quick-transfer-unified, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_transfer_unified.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


# ---------------------------------------------------------------------------
# Transfer Views (legacy — redirects to unified transfer)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def transfer_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transfers/new — redirect to unified transfer page."""
    return HttpResponseRedirect("/transfer/new")


@inject_service(TransactionService)
@general_rate
@require_http_methods(["POST"])
def transfer_create(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /transactions/transfer — create transfer with optional fee (HTMX)."""
    try:
        amount = parse_float_or_none(request.POST.get("amount", ""))
        if not amount:
            return error_response("Amount is required", field="amount")
        fee = parse_float_or_none(request.POST.get("fee_amount", ""))
        source_id = request.POST.get("source_account_id", "")
        dest_id = request.POST.get("dest_account_id", "")
        svc.create_transfer(
            source_id=source_id,
            dest_id=dest_id,
            amount=amount,
            currency=request.POST.get("currency"),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
            fee_amount=fee,
        )
        accs = {
            str(a["id"]): a
            for a in Account.objects.for_user(request.user_id)
            .filter(id__in=[source_id, dest_id])
            .values("id", "name", "current_balance", "currency")
        }
        src = accs.get(source_id, {})
        dst = accs.get(dest_id, {})
        return render(
            request,
            "transactions/_transfer_success.html",
            {
                "src_name": src.get("name", ""),
                "src_balance": str(src.get("current_balance", "")),
                "src_currency": src.get("currency", ""),
                "src_amount": str(amount),
                "dest_name": dst.get("name", ""),
                "dest_balance": str(dst.get("current_balance", "")),
                "dest_currency": dst.get("currency", ""),
                "dest_amount": str(amount),
            },
        )
    except ValueError as e:
        return error_response(str(e))


# ---------------------------------------------------------------------------
# Exchange Views (legacy — redirects to unified transfer)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def exchange_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /exchange/new — redirect to unified transfer page."""
    return HttpResponseRedirect("/transfer/new")


@inject_service(TransactionService)
@general_rate
@require_http_methods(["POST"])
def exchange_create(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /transactions/exchange-submit — currency exchange (HTMX)."""
    try:
        source_id = request.POST.get("source_account_id", "")
        dest_id = request.POST.get("dest_account_id", "")
        src_amount = parse_float_or_none(request.POST.get("amount", ""))
        dest_amount = parse_float_or_none(request.POST.get("counter_amount", ""))
        debit, credit = svc.create_exchange(
            source_id=source_id,
            dest_id=dest_id,
            amount=src_amount,
            rate=parse_float_or_none(request.POST.get("rate", "")),
            counter_amount=dest_amount,
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
        )
        resolved_src = debit.get("amount", str(src_amount or ""))
        resolved_dest = credit.get("amount", str(dest_amount or ""))
        accs = {
            str(a["id"]): a
            for a in Account.objects.for_user(request.user_id)
            .filter(id__in=[source_id, dest_id])
            .values("id", "name", "current_balance", "currency")
        }
        src = accs.get(source_id, {})
        dst = accs.get(dest_id, {})
        return render(
            request,
            "transactions/_transfer_success.html",
            {
                "src_name": src.get("name", ""),
                "src_balance": str(src.get("current_balance", "")),
                "src_currency": src.get("currency", ""),
                "src_amount": resolved_src,
                "dest_name": dst.get("name", ""),
                "dest_balance": str(dst.get("current_balance", "")),
                "dest_currency": dst.get("currency", ""),
                "dest_amount": resolved_dest,
            },
        )
    except ValueError as e:
        return error_response(str(e))


# ---------------------------------------------------------------------------
# Batch Entry Views
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def batch_entry(request: AuthenticatedRequest, svc: TransactionService) -> HttpResponse:
    """GET /batch-entry — batch entry form page."""
    logger.info("page viewed: batch-entry, user=%s", request.user_email)
    return render(
        request,
        "transactions/batch_entry.html",
        {
            "accounts": svc.get_accounts(),
            "categories": svc.get_categories(),
            "today": date.today(),
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["POST"])
def batch_create(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /transactions/batch — create multiple transactions (HTMX)."""
    types = request.POST.getlist("type[]")
    amounts = request.POST.getlist("amount[]")
    account_ids = request.POST.getlist("account_id[]")
    category_ids = request.POST.getlist("category_id[]")
    dates = request.POST.getlist("date[]")
    notes = request.POST.getlist("note[]")

    items = []
    for i in range(len(types)):
        items.append(
            {
                "type": types[i] if i < len(types) else "expense",
                "amount": amounts[i] if i < len(amounts) else "0",
                "account_id": account_ids[i] if i < len(account_ids) else "",
                "category_id": category_ids[i] if i < len(category_ids) else "",
                "date": dates[i] if i < len(dates) else "",
                "note": notes[i] if i < len(notes) else "",
            }
        )

    created, failed = svc.batch_create(items)
    return render_htmx_result(
        "info",
        f"Created {created} transaction{'s' if created != 1 else ''}"
        + (f", {failed} failed" if failed else ""),
    )


# ---------------------------------------------------------------------------
# Sync API (JSON)
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@csrf_exempt  # JS fetch() API (offline sync) — authenticated via session, rate-limited
@general_rate
@require_http_methods(["POST"])
def sync_transactions(
    request: AuthenticatedRequest, svc: TransactionService
) -> JsonResponse:
    """POST /sync/transactions — JSON API for bulk transaction import."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(body, list):
        return JsonResponse({"error": "Expected JSON array"}, status=400)

    created, failed = svc.batch_create(body)
    return JsonResponse({"created": created, "failed": failed})


# ---------------------------------------------------------------------------
# Category Suggestion API
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def suggest_category(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /api/transactions/suggest-category?note=TEXT — suggest category."""
    note = request.GET.get("note", "")
    category_id = svc.suggest_category(note)
    if category_id:
        return HttpResponse(category_id, content_type="text/plain")
    return HttpResponse("", content_type="text/plain")


# ---------------------------------------------------------------------------
# Global Search (Header)
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def global_search(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /search?q=TEXT — HTMX partial for the global header search bar.

    Searches transactions by note, amount, and category name (up to 20 results).
    Returns an empty partial when ``q`` is blank so the search overlay clears.
    """
    q = (request.GET.get("q", "") or "").strip()
    transactions = svc.search(q) if q else []
    logger.info(
        "global search: q=%r hits=%d user=%s", q, len(transactions), request.user_email
    )
    return render(
        request,
        "transactions/_search_results.html",
        {"transactions": transactions, "query": q},
    )


# ---------------------------------------------------------------------------
# Quick Entry Partials (Dashboard Bottom Sheet)
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def quick_entry_form(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transactions/quick-form — quick entry partial for bottom sheet."""
    defaults = svc.get_smart_defaults("expense")
    expense_accounts = svc.get_accounts("expense")
    income_accounts = svc.get_accounts("income")
    transfer_accounts = svc.get_accounts()
    categories = svc.get_categories()
    virtual_accounts = svc.get_virtual_accounts()

    logger.info("partial loaded: quick-entry, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_entry.html",
        {
            "accounts": expense_accounts,
            "expense_accounts": expense_accounts,
            "income_accounts": income_accounts,
            "transfer_accounts": transfer_accounts,
            "categories": categories,
            "virtual_accounts": virtual_accounts,
            "last_account_id": defaults["last_account_id"],
            "auto_category_id": defaults["auto_category_id"],
            "today": date.today(),
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["POST"])
def quick_entry_create(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /transactions/quick — create quick entry (HTMX toast response)."""
    try:
        attachment = request.FILES.get("attachment")
        att_err = _validate_attachment(attachment)
        if att_err:
            return error_response(att_err)

        tx_type = request.POST.get("type", "")
        amount_str = request.POST.get("amount", "0")
        amount = parse_float_or_none(amount_str)

        success_ctx: dict[str, object] = {}
        if tx_type == "transfer":
            if not amount:
                return error_response("Amount is required", field="amount")
            source_id = request.POST.get("account_id", "")
            dest_id = request.POST.get("dest_account_id", "")
            svc.create_transfer(
                source_id=source_id,
                dest_id=dest_id,
                amount=amount,
                currency=request.POST.get("currency"),
                note=request.POST.get("note") or None,
                tx_date=request.POST.get("date") or None,
                fee_amount=parse_float_or_none(request.POST.get("fee_amount", "")),
            )
            accs = {
                str(a["id"]): a
                for a in Account.objects.for_user(request.user_id)
                .filter(id__in=[source_id, dest_id])
                .values("id", "name", "current_balance", "currency")
            }
            src = accs.get(source_id, {})
            dst = accs.get(dest_id, {})
            success_ctx = {
                "is_transfer": True,
                "src_name": src.get("name", ""),
                "src_balance": str(src.get("current_balance", "")),
                "src_currency": src.get("currency", ""),
                "src_amount": str(amount),
                "dest_name": dst.get("name", ""),
                "dest_balance": str(dst.get("current_balance", "")),
                "dest_currency": dst.get("currency", ""),
                "dest_amount": str(amount),
            }
        else:
            data = {
                "type": tx_type,
                "amount": amount_str,
                "account_id": request.POST.get("account_id", ""),
                "category_id": request.POST.get("category_id", ""),
                "note": request.POST.get("note", ""),
                "date": request.POST.get("date", ""),
                "tags": request.POST.get("tags", ""),
                "attachment": attachment,
            }
            tx, new_balance = svc.create(data)

            # Handle fee and VA allocation via service helper
            svc.apply_post_create_logic(
                tx,
                fee_amount=parse_float_or_none(request.POST.get("fee_amount", "")),
                va_id=request.POST.get("virtual_account_id"),
                tx_date=data.get("date"),
                fee_preset_id=request.POST.get("fee_preset_id", "") or None,
            )
            success_ctx = {
                "is_transfer": False,
                "tx": tx,
                "new_balance": new_balance,
                "currency": tx["currency"],
            }

        # Render success screen with Done/Add Another buttons
        response = render(
            request, "transactions/_quick_entry_success.html", success_ctx
        )

        # OOB swaps: refresh dashboard balances with skeleton placeholders
        nw_skeleton = (
            '<section class="bg-white dark:bg-slate-900 rounded-2xl shadow-sm p-5 animate-pulse">'
            '<div class="h-4 w-24 skeleton mb-4"></div>'
            '<div class="flex gap-4 mb-4"><div class="h-8 w-28 skeleton"></div><div class="h-8 w-28 skeleton"></div></div>'
            '<div class="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-gray-100 dark:border-slate-800">'
            '<div class="h-10 skeleton"></div><div class="h-10 skeleton"></div>'
            "</div></section>"
        )
        acc_skeleton = (
            '<section class="bg-white dark:bg-slate-900 rounded-2xl shadow-sm p-5 animate-pulse">'
            '<div class="flex items-center justify-between mb-4"><div class="h-4 w-20 skeleton"></div><div class="h-4 w-12 skeleton"></div></div>'
            '<div class="space-y-4">'
            '<div class="h-12 skeleton"></div><div class="h-12 skeleton"></div><div class="h-12 skeleton"></div>'
            "</div></section>"
        )

        response.write(
            f'<div id="dashboard-net-worth" hx-swap-oob="true"'
            ' hx-get="/partials/net-worth"'
            f' hx-trigger="load" hx-swap="innerHTML" aria-busy="true">{nw_skeleton}</div>'
        )
        response.write(
            f'<div id="dashboard-accounts" hx-swap-oob="true"'
            ' hx-get="/partials/accounts"'
            f' hx-trigger="load" hx-swap="innerHTML" aria-busy="true">{acc_skeleton}</div>'
        )
        return response
    except ValueError as e:
        return error_response(str(e))


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def quick_transfer_form(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /transactions/quick-transfer — quick transfer partial."""
    logger.info("partial loaded: quick-transfer, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_transfer.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


@inject_service(TransactionService)
@general_rate
@require_http_methods(["GET"])
def quick_exchange_form(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET /exchange/quick-form — quick exchange partial."""
    logger.info("partial loaded: quick-exchange, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_exchange.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


# ---------------------------------------------------------------------------
# JSON API Views
# ---------------------------------------------------------------------------


@inject_service(TransactionService)
@csrf_exempt  # JSON API — authenticated via session, called by e2e helpers and JS fetch()
@api_rate
@require_http_methods(["GET", "POST"])
def api_transaction_list_create(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """GET/POST /api/transactions — list or create transactions (JSON).

    GET supports ?account_id=, ?limit= (default 15), ?offset= (default 0).
    Returns paginated response with metadata.
    POST returns {"transaction": {...}, "new_balance": X}.
    """

    if request.method == "GET":
        account_id = request.GET.get("account_id", "")
        limit = int(request.GET.get("limit", "15") or "15")
        offset = int(request.GET.get("offset", "0") or "0")
        paginated = svc.get_paginated(limit=limit, offset=offset, account_id=account_id)
        return JsonResponse(paginated)

    # POST — create
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    # Idempotency: check for Idempotency-Key header
    idempotency_key = request.headers.get("Idempotency-Key", "")
    if idempotency_key:
        # User ID prefix to avoid key collisions across users
        cache_key = f"idempotency:{request.user_id}:{idempotency_key}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return JsonResponse(cached_result, status=201)

    try:
        tx, new_balance = svc.create(body)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    result = {"transaction": tx, "new_balance": new_balance}

    # Cache the result for idempotency (5 minute TTL)
    if idempotency_key:
        cache.set(cache_key, result, timeout=300)

    return JsonResponse(result, status=201)


@inject_service(TransactionService)
@api_rate
@require_http_methods(["POST"])
def api_transaction_transfer(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /api/transactions/transfer — create transfer (JSON).

    Returns {"debit": {...}, "credit": {...}}.
    """
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    try:
        debit, credit = svc.create_transfer(
            source_id=body.get("source_account_id", ""),
            dest_id=body.get("dest_account_id", ""),
            amount=float(body.get("amount", 0)),
            currency=body.get("currency"),
            note=body.get("note"),
            tx_date=body.get("date"),
        )
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"debit": debit, "credit": credit}, status=201)


@inject_service(TransactionService)
@api_rate
@require_http_methods(["POST"])
def api_transaction_exchange(
    request: AuthenticatedRequest, svc: TransactionService
) -> HttpResponse:
    """POST /api/transactions/exchange — create currency exchange (JSON).

    Returns {"debit": {...}, "credit": {...}}.
    """
    body = parse_json_body(request)
    if body is None:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    try:
        debit, credit = svc.create_exchange(
            source_id=body.get("source_account_id", ""),
            dest_id=body.get("dest_account_id", ""),
            amount=body.get("amount"),
            rate=body.get("rate"),
            counter_amount=body.get("counter_amount"),
            note=body.get("note"),
            tx_date=body.get("date"),
        )
    except (ValueError, TypeError) as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"debit": debit, "credit": credit}, status=201)


@inject_service(TransactionService)
@csrf_exempt  # JSON API — authenticated via session, called by e2e helpers and JS fetch()
@api_rate
@require_http_methods(["GET", "DELETE"])
def api_transaction_detail(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """GET/DELETE /api/transactions/{id} — single transaction operations (JSON)."""
    tid = str(tx_id)

    if request.method == "GET":
        tx = svc.get_by_id(tid)
        if not tx:
            return JsonResponse({"error": "transaction not found"}, status=404)
        return JsonResponse(tx)

    # DELETE
    try:
        svc.delete(tid)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=404)
    return HttpResponse(status=204)


@require_http_methods(["GET"])
@inject_service(TransactionService)
def transaction_settle_form(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """GET /transactions/settle/<id> — settle form partial (loaded into bottom sheet)."""
    tx = svc.get_by_id(str(tx_id))
    if not tx:
        return HttpResponse("Not found", status=404)
    if not tx.get("is_pending"):
        return HttpResponse("Transaction is not pending", status=400)
    return render(request, "transactions/_settle_form.html", {"tx": tx})


@require_http_methods(["POST"])
@inject_service(TransactionService)
def transaction_settle(
    request: AuthenticatedRequest, svc: TransactionService, tx_id: str
) -> HttpResponse:
    """POST /transactions/<id>/settle — settle a pending transaction."""
    from decimal import Decimal, InvalidOperation

    raw = request.POST.get("settled_amount", "")
    try:
        final_amount = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return error_response("Enter a valid amount")

    try:
        settled, new_balance = svc.settle(str(tx_id), final_amount)
    except ValueError as e:
        return error_response(str(e))

    return render(
        request,
        "transactions/_settle_success.html",
        {"tx": settled, "new_balance": new_balance},
    )
