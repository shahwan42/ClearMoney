"""
Transaction views — all /transactions/*, /transfers/*, /exchange/*, /move-money/*,
/batch-entry, /fawry-cashout, and /sync/transactions routes.

Like Laravel's TransactionController — thin views that delegate to services.
"""

import json
import logging
from datetime import date

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import Account
from core.htmx import error_response, render_htmx_result
from core.ratelimit import api_rate, general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none, parse_json_body
from people.models import Person
from transactions.models import Transaction, VirtualAccountAllocation

from .services import TransactionService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svc(request: AuthenticatedRequest) -> TransactionService:
    """Create a TransactionService for the authenticated user."""
    return TransactionService(request.user_id, request.tz)


# ---------------------------------------------------------------------------
# Page Views
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET", "POST"])
def transactions_list(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions — full page. POST /transactions — create (HTMX)."""
    if request.method == "POST":
        return transaction_create(request)

    svc = _svc(request)
    offset = int(request.GET.get("offset", 0))
    filters = {
        "account_id": request.GET.get("account_id", ""),
        "category_id": request.GET.get("category_id", ""),
        "type": request.GET.get("type", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "search": request.GET.get("search", ""),
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
            },
        },
    )


@general_rate
@require_http_methods(["GET"])
def transactions_list_partial(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/list — HTMX partial for filter updates."""
    svc = _svc(request)
    offset = int(request.GET.get("offset", 0))
    filters = {
        "account_id": request.GET.get("account_id", ""),
        "category_id": request.GET.get("category_id", ""),
        "type": request.GET.get("type", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "search": request.GET.get("search", ""),
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
            },
        },
    )


@general_rate
@require_http_methods(["GET"])
def transaction_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/new — full transaction form page. Supports ?dup=<id>."""
    svc = _svc(request)
    accounts = svc.get_accounts()
    categories = svc.get_categories()
    virtual_accounts = svc.get_virtual_accounts()

    prefill = None
    dup_id = request.GET.get("dup")
    if dup_id:
        prefill = svc.get_by_id(dup_id)

    logger.info("page viewed: transaction-new, user=%s", request.user_email)
    return render(
        request,
        "transactions/transaction_new.html",
        {
            "accounts": accounts,
            "categories": categories,
            "virtual_accounts": virtual_accounts,
            "today": date.today(),
            "prefill": prefill,
        },
    )


# ---------------------------------------------------------------------------
# CRUD Mutations
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def transaction_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions — create expense/income transaction (HTMX)."""
    svc = _svc(request)
    try:
        data = {
            "type": request.POST.get("type", ""),
            "amount": request.POST.get("amount", "0"),
            "account_id": request.POST.get("account_id", ""),
            "category_id": request.POST.get("category_id", ""),
            "note": request.POST.get("note", ""),
            "date": request.POST.get("date", ""),
        }
        tx, new_balance = svc.create(data)

        # Optional fee → separate linked expense transaction
        fee_raw = request.POST.get("fee_amount", "")
        if fee_raw:
            fee = parse_float_or_none(fee_raw)
            if fee and fee > 0:
                svc.create_fee_for_transaction(
                    parent_tx=tx,
                    fee_amount=fee,
                    tx_date=data.get("date") or None,
                )

        # Virtual account allocation
        va_id = request.POST.get("virtual_account_id", "")
        if va_id:
            alloc_amount = float(data["amount"])
            if tx["type"] == "expense":
                alloc_amount = -alloc_amount
            try:
                svc.allocate_to_virtual_account(tx["id"], va_id, alloc_amount)
            except ValueError as e:
                logger.warning("VA allocation failed: %s", e)

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


@general_rate
@require_http_methods(["GET"])
def transaction_edit_form(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """GET /transactions/edit/<id> — inline edit form partial (HTMX)."""
    svc = _svc(request)
    tx = svc.get_by_id(str(tx_id))
    if not tx:
        return HttpResponse("Not found", status=404)

    categories = svc.get_categories()
    virtual_accounts = svc.get_virtual_accounts()
    selected_va_id = svc.get_allocation_for_tx(str(tx_id))

    # Look up existing linked fee transaction
    fee_tx = (
        Transaction.objects.for_user(request.user_id)
        .filter(linked_transaction_id=str(tx_id), note="Transaction fee")
        .first()
    )

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
        },
    )


@general_rate
@require_http_methods(["GET"])
def transaction_detail_sheet(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """GET /transactions/detail/<id> — bottom sheet detail partial."""
    svc = _svc(request)
    tx = svc.get_by_id_enriched(str(tx_id))
    if not tx:
        return HttpResponse("Not found", status=404)

    context: dict[str, object] = {"tx": tx}

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

    logger.info("partial loaded: transaction-detail-sheet, user=%s", request.user_email)
    return render(request, "transactions/_transaction_detail_sheet.html", context)


@csrf_exempt  # JSON API — authenticated via session, called by e2e helpers and HTMX (which sends X-CSRFToken anyway)
@general_rate
@require_http_methods(["PUT", "DELETE"])
def transaction_detail(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """PUT/DELETE /transactions/<id> — dispatches to update or delete."""
    if request.method == "DELETE":
        return transaction_delete(request, tx_id)
    return transaction_update(request, tx_id)


def transaction_update(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """PUT /transactions/<id> — update transaction (HTMX inline edit)."""
    svc = _svc(request)
    # Django only populates request.POST for POST method — parse PUT body manually
    put_data = QueryDict(request.body)
    try:
        data = {
            "type": put_data.get("type", ""),
            "amount": put_data.get("amount", "0"),
            "category_id": put_data.get("category_id", ""),
            "note": put_data.get("note", ""),
            "date": put_data.get("date", ""),
        }
        svc.update(str(tx_id), data)

        # Handle fee changes
        fee_raw = put_data.get("fee_amount", "")
        fee = parse_float_or_none(fee_raw) if fee_raw else None
        svc.update_fee_for_transaction(
            str(tx_id), fee, tx_date=data.get("date") or None
        )

        # Handle VA reallocation
        old_va_id = svc.get_allocation_for_tx(str(tx_id))
        new_va_id = put_data.get("virtual_account_id", "")
        if old_va_id != new_va_id:
            if old_va_id:
                svc.deallocate_from_virtual_accounts(str(tx_id))
            if new_va_id:
                alloc_amount = float(data["amount"])
                if data["type"] == "expense":
                    alloc_amount = -alloc_amount
                try:
                    svc.allocate_to_virtual_account(str(tx_id), new_va_id, alloc_amount)
                except ValueError:
                    pass

        # Return updated row with retarget headers so HTMX updates the row
        # in-place, regardless of the form's hx-target (which points at the
        # error div inside the sheet).
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


def transaction_delete(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """DELETE /transactions/<id> — delete transaction (HTMX removes row)."""
    svc = _svc(request)
    try:
        svc.deallocate_from_virtual_accounts(str(tx_id))
        related_ids = svc.delete(str(tx_id))

        # Build OOB delete elements so HTMX removes related rows (linked + fees)
        oob_html = "".join(
            f'<div id="tx-{rid}" hx-swap-oob="delete"></div>' for rid in related_ids
        )
        response = HttpResponse(oob_html)
        # Header for swipe-to-delete path (raw fetch, not HTMX)
        if related_ids:
            response["X-Related-Deleted"] = ",".join(related_ids)
        return response
    except ValueError as e:
        return error_response(str(e))


@general_rate
@require_http_methods(["GET"])
def transaction_row(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """GET /transactions/row/<id> — single row partial (cancel edit)."""
    svc = _svc(request)
    enriched = svc.get_by_id_enriched(str(tx_id))
    if not enriched:
        return HttpResponse("Not found", status=404)
    return render(request, "transactions/_transaction_row.html", {"tx": enriched})


# ---------------------------------------------------------------------------
# Move Money Views (unified transfer/exchange)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def move_money_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /move-money/new — unified move money form page."""
    svc = _svc(request)
    logger.info("page viewed: move-money, user=%s", request.user_email)
    return render(
        request,
        "transactions/move_money.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


@general_rate
@require_http_methods(["GET"])
def quick_move_money_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/quick-move — quick move money partial for bottom sheet."""
    svc = _svc(request)
    logger.info("partial loaded: quick-move-money, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_move_money.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


# ---------------------------------------------------------------------------
# Transfer Views (legacy — redirects to move money)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def transfer_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transfers/new — redirect to unified move money page."""
    return HttpResponseRedirect("/move-money/new")


@general_rate
@require_http_methods(["POST"])
def transfer_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/transfer — create transfer with optional fee (HTMX)."""
    svc = _svc(request)
    try:
        amount = parse_float_or_none(request.POST.get("amount", ""))
        if not amount:
            return error_response("Amount is required", field="amount")
        fee = parse_float_or_none(request.POST.get("fee_amount", ""))
        svc.create_transfer(
            source_id=request.POST.get("source_account_id", ""),
            dest_id=request.POST.get("dest_account_id", ""),
            amount=amount,
            currency=request.POST.get("currency"),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
            fee_amount=fee,
        )
        return render(
            request,
            "transactions/_transfer_success.html",
            {"message": "Transfer completed!"},
        )
    except ValueError as e:
        return error_response(str(e))


@require_http_methods(["POST"])
def instapay_transfer_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/instapay-transfer — deprecated, redirect to move money."""
    return HttpResponseRedirect("/move-money/new")


# ---------------------------------------------------------------------------
# Exchange Views (legacy — redirects to move money)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def exchange_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /exchange/new — redirect to unified move money page."""
    return HttpResponseRedirect("/move-money/new")


@general_rate
@require_http_methods(["POST"])
def exchange_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/exchange-submit — currency exchange (HTMX)."""
    svc = _svc(request)
    try:
        svc.create_exchange(
            source_id=request.POST.get("source_account_id", ""),
            dest_id=request.POST.get("dest_account_id", ""),
            amount=parse_float_or_none(request.POST.get("amount", "")),
            rate=parse_float_or_none(request.POST.get("rate", "")),
            counter_amount=parse_float_or_none(request.POST.get("counter_amount", "")),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
        )
        return render(
            request,
            "transactions/_transfer_success.html",
            {"message": "Exchange completed!"},
        )
    except ValueError as e:
        return error_response(str(e))


# ---------------------------------------------------------------------------
# Fawry Cashout Views
# ---------------------------------------------------------------------------


def fawry_cashout(request: AuthenticatedRequest) -> HttpResponse:
    """GET /fawry-cashout — deprecated, redirect to move money."""
    return HttpResponseRedirect("/move-money/new")


def fawry_cashout_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/fawry-cashout — deprecated, redirect to unified transfer."""
    return HttpResponseRedirect("/transfers/new")


# ---------------------------------------------------------------------------
# Batch Entry Views
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def batch_entry(request: AuthenticatedRequest) -> HttpResponse:
    """GET /batch-entry — batch entry form page."""
    svc = _svc(request)
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


@general_rate
@require_http_methods(["POST"])
def batch_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/batch — create multiple transactions (HTMX)."""
    svc = _svc(request)
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


@csrf_exempt  # JS fetch() API (offline sync) — authenticated via session, rate-limited
@general_rate
@require_http_methods(["POST"])
def sync_transactions(request: AuthenticatedRequest) -> JsonResponse:
    """POST /sync/transactions — JSON API for bulk transaction import."""
    svc = _svc(request)
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


@general_rate
@require_http_methods(["GET"])
def suggest_category(request: AuthenticatedRequest) -> HttpResponse:
    """GET /api/transactions/suggest-category?note=TEXT — suggest category."""
    svc = _svc(request)
    note = request.GET.get("note", "")
    category_id = svc.suggest_category(note)
    if category_id:
        return HttpResponse(category_id, content_type="text/plain")
    return HttpResponse("", content_type="text/plain")


# ---------------------------------------------------------------------------
# Quick Entry Partials (Dashboard Bottom Sheet)
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def quick_entry_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/quick-form — quick entry partial for bottom sheet."""
    svc = _svc(request)
    defaults = svc.get_smart_defaults("expense")
    accounts = svc.get_accounts()
    categories = svc.get_categories()
    virtual_accounts = svc.get_virtual_accounts()

    logger.info("partial loaded: quick-entry, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_entry.html",
        {
            "accounts": accounts,
            "categories": categories,
            "virtual_accounts": virtual_accounts,
            "last_account_id": defaults["last_account_id"],
            "auto_category_id": defaults["auto_category_id"],
            "today": date.today(),
        },
    )


@general_rate
@require_http_methods(["POST"])
def quick_entry_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/quick — create quick entry (HTMX toast response)."""
    svc = _svc(request)
    try:
        data = {
            "type": request.POST.get("type", ""),
            "amount": request.POST.get("amount", "0"),
            "account_id": request.POST.get("account_id", ""),
            "category_id": request.POST.get("category_id", ""),
            "note": request.POST.get("note", ""),
            "date": request.POST.get("date", ""),
        }
        tx, new_balance = svc.create(data)

        # Optional fee → separate linked expense transaction
        fee_raw = request.POST.get("fee_amount", "")
        if fee_raw:
            fee = parse_float_or_none(fee_raw)
            if fee and fee > 0:
                svc.create_fee_for_transaction(
                    parent_tx=tx,
                    fee_amount=fee,
                    tx_date=data.get("date") or None,
                )

        va_id = request.POST.get("virtual_account_id", "")
        if va_id:
            alloc_amount = float(data["amount"])
            if tx["type"] == "expense":
                alloc_amount = -alloc_amount
            try:
                svc.allocate_to_virtual_account(tx["id"], va_id, alloc_amount)
            except ValueError:
                pass

        # Render success screen with Done/Add Another buttons
        response = render(request, "transactions/_quick_entry_success.html")

        # OOB swaps: refresh dashboard balances without rendering inline
        response.write(
            '<div id="dashboard-net-worth" hx-swap-oob="true"'
            ' hx-get="/partials/net-worth"'
            ' hx-trigger="load" hx-swap="innerHTML"></div>'
        )
        response.write(
            '<div id="dashboard-accounts" hx-swap-oob="true"'
            ' hx-get="/partials/accounts"'
            ' hx-trigger="load" hx-swap="innerHTML"></div>'
        )
        return response
    except ValueError as e:
        return error_response(str(e))


@general_rate
@require_http_methods(["GET"])
def quick_transfer_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/quick-transfer — quick transfer partial."""
    svc = _svc(request)
    logger.info("partial loaded: quick-transfer, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_transfer.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


@general_rate
@require_http_methods(["GET"])
def quick_exchange_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /exchange/quick-form — quick exchange partial."""
    svc = _svc(request)
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


@csrf_exempt  # JSON API — authenticated via session, called by e2e helpers and JS fetch()
@api_rate
@require_http_methods(["GET", "POST"])
def api_transaction_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/transactions — list or create transactions (JSON).

    GET supports ?account_id=, ?limit= (default 15), ?offset= (default 0).
    Returns paginated response with metadata.
    POST returns {"transaction": {...}, "new_balance": X}.
    """
    svc = _svc(request)

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


@api_rate
@require_http_methods(["POST"])
def api_transaction_transfer(request: AuthenticatedRequest) -> HttpResponse:
    """POST /api/transactions/transfer — create transfer (JSON).

    Returns {"debit": {...}, "credit": {...}}.
    """
    svc = _svc(request)
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


@api_rate
@require_http_methods(["POST"])
def api_transaction_exchange(request: AuthenticatedRequest) -> HttpResponse:
    """POST /api/transactions/exchange — create currency exchange (JSON).

    Returns {"debit": {...}, "credit": {...}}.
    """
    svc = _svc(request)
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


@csrf_exempt  # JSON API — authenticated via session, called by e2e helpers and JS fetch()
@api_rate
@require_http_methods(["GET", "DELETE"])
def api_transaction_detail(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """GET/DELETE /api/transactions/{id} — single transaction operations (JSON)."""
    svc = _svc(request)
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
