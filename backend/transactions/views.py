"""
Transaction views — all /transactions/*, /transfers/*, /exchange/*, /batch-entry,
/fawry-cashout, and /sync/transactions routes.

Port of Go's PageHandler methods for transactions (pages.go lines 591-1210,
1606-1725, 1907-1961, 2230-2525). Handles pages, HTMX partials, and mutations.

Like Laravel's TransactionController — thin views that delegate to services.
"""

import json
import logging
from datetime import date

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.htmx import render_htmx_result
from core.types import AuthenticatedRequest

from .services import TransactionService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svc(request: AuthenticatedRequest) -> TransactionService:
    """Create a TransactionService for the authenticated user."""
    return TransactionService(request.user_id, request.tz)


def _parse_float(value: str) -> float | None:
    """Parse form value to float, None if empty."""
    if not value or not value.strip():
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _error_html(message: str) -> HttpResponse:
    """Return an error HTML fragment for HTMX targets."""
    html = (
        f'<div class="bg-red-50 border border-red-200 rounded-xl p-3 text-center">'
        f'<p class="text-red-800 text-sm font-medium">{message}</p></div>'
    )
    return HttpResponse(html, status=400)


def _success_html(message: str) -> HttpResponse:
    """Return a success HTML fragment for HTMX targets."""
    html = (
        f'<div class="bg-teal-50 border border-teal-200 rounded-xl p-3 text-center animate-toast">'
        f'<p class="text-teal-800 font-semibold text-sm">{message}</p></div>'
    )
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# Page Views
# ---------------------------------------------------------------------------


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


@require_http_methods(["GET"])
def transaction_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/new — full transaction form page. Supports ?dup=<id>."""
    svc = _svc(request)
    accounts = svc.get_accounts()
    expense_cats = svc.get_categories("expense")
    income_cats = svc.get_categories("income")
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
            "expense_categories": expense_cats,
            "income_categories": income_cats,
            "virtual_accounts": virtual_accounts,
            "today": date.today(),
            "prefill": prefill,
        },
    )


# ---------------------------------------------------------------------------
# CRUD Mutations
# ---------------------------------------------------------------------------


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
        return _error_html(str(e))


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
        },
    )


@require_http_methods(["PUT", "DELETE"])
def transaction_detail(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """PUT/DELETE /transactions/<id> — dispatches to update or delete."""
    if request.method == "DELETE":
        return transaction_delete(request, tx_id)
    return transaction_update(request, tx_id)


def transaction_update(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """PUT /transactions/<id> — update transaction (HTMX inline edit)."""
    svc = _svc(request)
    try:
        data = {
            "type": request.POST.get("type", ""),
            "amount": request.POST.get("amount", "0"),
            "category_id": request.POST.get("category_id", ""),
            "note": request.POST.get("note", ""),
            "date": request.POST.get("date", ""),
        }
        svc.update(str(tx_id), data)

        # Handle VA reallocation
        old_va_id = svc.get_allocation_for_tx(str(tx_id))
        new_va_id = request.POST.get("virtual_account_id", "")
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

        # Return updated row
        enriched = svc.get_by_id_enriched(str(tx_id))
        return render(request, "transactions/_transaction_row.html", {"tx": enriched})
    except ValueError as e:
        return _error_html(str(e))


def transaction_delete(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """DELETE /transactions/<id> — delete transaction (HTMX removes row)."""
    svc = _svc(request)
    try:
        svc.deallocate_from_virtual_accounts(str(tx_id))
        svc.delete(str(tx_id))
        return HttpResponse("")
    except ValueError as e:
        return _error_html(str(e))


@require_http_methods(["GET"])
def transaction_row(request: AuthenticatedRequest, tx_id: str) -> HttpResponse:
    """GET /transactions/row/<id> — single row partial (cancel edit)."""
    svc = _svc(request)
    enriched = svc.get_by_id_enriched(str(tx_id))
    if not enriched:
        return HttpResponse("Not found", status=404)
    return render(request, "transactions/_transaction_row.html", {"tx": enriched})


# ---------------------------------------------------------------------------
# Transfer Views
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def transfer_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transfers/new — transfer form page."""
    svc = _svc(request)
    logger.info("page viewed: transfer, user=%s", request.user_email)
    return render(
        request,
        "transactions/transfer.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


@require_http_methods(["POST"])
def transfer_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/transfer — create transfer (HTMX)."""
    svc = _svc(request)
    try:
        amount = _parse_float(request.POST.get("amount", ""))
        if not amount:
            return _error_html("Amount is required")
        svc.create_transfer(
            source_id=request.POST.get("source_account_id", ""),
            dest_id=request.POST.get("dest_account_id", ""),
            amount=amount,
            currency=request.POST.get("currency"),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
        )
        return _success_html("Transfer completed!")
    except ValueError as e:
        return _error_html(str(e))


@require_http_methods(["POST"])
def instapay_transfer_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/instapay-transfer — InstaPay with fee (HTMX)."""
    svc = _svc(request)
    try:
        amount = _parse_float(request.POST.get("amount", ""))
        if not amount:
            return _error_html("Amount is required")
        fees_cat_id = svc.get_fees_category_id()
        _, _, fee = svc.create_instapay_transfer(
            source_id=request.POST.get("source_account_id", ""),
            dest_id=request.POST.get("dest_account_id", ""),
            amount=amount,
            currency=request.POST.get("currency"),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
            fees_category_id=fees_cat_id,
        )
        return render_htmx_result(
            "success",
            f"InstaPay transfer completed! Fee: EGP {fee:.2f}",
        )
    except ValueError as e:
        return render_htmx_result("error", str(e))


# ---------------------------------------------------------------------------
# Exchange Views
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def exchange_new(request: AuthenticatedRequest) -> HttpResponse:
    """GET /exchange/new — exchange form page."""
    svc = _svc(request)
    logger.info("page viewed: exchange, user=%s", request.user_email)
    return render(
        request,
        "transactions/exchange.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


@require_http_methods(["POST"])
def exchange_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/exchange-submit — currency exchange (HTMX)."""
    svc = _svc(request)
    try:
        svc.create_exchange(
            source_id=request.POST.get("source_account_id", ""),
            dest_id=request.POST.get("dest_account_id", ""),
            amount=_parse_float(request.POST.get("amount", "")),
            rate=_parse_float(request.POST.get("rate", "")),
            counter_amount=_parse_float(request.POST.get("counter_amount", "")),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
        )
        from_sheet = request.POST.get("from_sheet") == "1"
        if from_sheet:
            return _success_html("Exchange completed!")
        return _success_html("Exchange completed!")
    except ValueError as e:
        return _error_html(str(e))


# ---------------------------------------------------------------------------
# Fawry Cashout Views
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def fawry_cashout(request: AuthenticatedRequest) -> HttpResponse:
    """GET /fawry-cashout — Fawry cash-out form page."""
    svc = _svc(request)
    logger.info("page viewed: fawry-cashout, user=%s", request.user_email)
    return render(
        request,
        "transactions/fawry_cashout.html",
        {
            "accounts": svc.get_accounts(),
            "today": date.today(),
        },
    )


@require_http_methods(["POST"])
def fawry_cashout_create(request: AuthenticatedRequest) -> HttpResponse:
    """POST /transactions/fawry-cashout — process Fawry cash-out (HTMX)."""
    svc = _svc(request)
    try:
        amount = _parse_float(request.POST.get("amount", ""))
        fee = _parse_float(request.POST.get("fee", "")) or 0.0
        if not amount:
            return render_htmx_result("error", "Amount is required")
        fees_cat_id = svc.get_fees_category_id()
        svc.create_fawry_cashout(
            credit_card_id=request.POST.get("credit_card_id", ""),
            prepaid_id=request.POST.get("prepaid_account_id", ""),
            amount=amount,
            fee=fee,
            currency=request.POST.get("currency"),
            note=request.POST.get("note") or None,
            tx_date=request.POST.get("date") or None,
            fees_category_id=fees_cat_id,
        )
        return render_htmx_result(
            "success",
            f"Cash-out complete! Amount: EGP {amount:.2f}, Fee: EGP {fee:.2f}",
        )
    except ValueError as e:
        return render_htmx_result("error", str(e))


# ---------------------------------------------------------------------------
# Batch Entry Views
# ---------------------------------------------------------------------------


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
            "expense_categories": svc.get_categories("expense"),
            "today": date.today(),
        },
    )


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


@require_http_methods(["GET"])
def quick_entry_form(request: AuthenticatedRequest) -> HttpResponse:
    """GET /transactions/quick-form — quick entry partial for bottom sheet."""
    svc = _svc(request)
    defaults = svc.get_smart_defaults("expense")
    accounts = svc.get_accounts()
    expense_cats = svc.get_categories("expense")
    income_cats = svc.get_categories("income")
    virtual_accounts = svc.get_virtual_accounts()

    logger.info("partial loaded: quick-entry, user=%s", request.user_email)
    return render(
        request,
        "transactions/_quick_entry.html",
        {
            "accounts": accounts,
            "expense_categories": expense_cats,
            "income_categories": income_cats,
            "virtual_accounts": virtual_accounts,
            "last_account_id": defaults["last_account_id"],
            "auto_category_id": defaults["auto_category_id"],
        },
    )


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

        va_id = request.POST.get("virtual_account_id", "")
        if va_id:
            alloc_amount = float(data["amount"])
            if tx["type"] == "expense":
                alloc_amount = -alloc_amount
            try:
                svc.allocate_to_virtual_account(tx["id"], va_id, alloc_amount)
            except ValueError:
                pass

        return _success_html("Saved!")
    except ValueError as e:
        return _error_html(str(e))


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
# JSON API Views (port of Go's TransactionHandler)
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def api_transaction_list_create(request: AuthenticatedRequest) -> HttpResponse:
    """GET/POST /api/transactions — list or create transactions (JSON).

    GET supports ?account_id= and ?limit= (default 15).
    POST returns {"transaction": {...}, "new_balance": X}.
    """
    svc = _svc(request)

    if request.method == "GET":
        account_id = request.GET.get("account_id", "")
        limit = int(request.GET.get("limit", "15") or "15")
        if account_id:
            transactions = svc.get_by_account(account_id, limit)
        else:
            transactions = svc.get_recent(limit)
        return JsonResponse(transactions, safe=False)

    # POST — create
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    try:
        tx, new_balance = svc.create(body)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"transaction": tx, "new_balance": new_balance}, status=201)


@require_http_methods(["POST"])
def api_transaction_transfer(request: AuthenticatedRequest) -> HttpResponse:
    """POST /api/transactions/transfer — create transfer (JSON).

    Returns {"debit": {...}, "credit": {...}}.
    """
    svc = _svc(request)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
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


@require_http_methods(["POST"])
def api_transaction_exchange(request: AuthenticatedRequest) -> HttpResponse:
    """POST /api/transactions/exchange — create currency exchange (JSON).

    Returns {"debit": {...}, "credit": {...}}.
    """
    svc = _svc(request)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
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
