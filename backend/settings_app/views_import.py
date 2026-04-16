import json
import logging
import uuid

from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from transactions.services import CsvImportService, TransactionService

logger = logging.getLogger(__name__)


@general_rate
@require_http_methods(["GET", "POST"])
def import_upload(request: AuthenticatedRequest) -> HttpResponse:
    """Step 1: Upload CSV file."""
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file:
            return HttpResponse("No file uploaded", status=400)

        if not file.name.endswith(".csv"):
            return HttpResponse("Only .csv files are supported", status=400)

        # Max 5MB
        if file.size > 5 * 1024 * 1024:
            return HttpResponse("File too large (max 5MB)", status=400)

        content = file.read().decode("utf-8")
        import_id = str(uuid.uuid4())

        # Store in cache for 1 hour
        cache.set(f"import_csv_{import_id}", content, timeout=3600)

        return redirect("import-mapping", import_id=import_id)

    return render(request, "settings_app/import/upload.html")


@general_rate
@require_http_methods(["GET", "POST"])
def import_mapping(request: AuthenticatedRequest, import_id: str) -> HttpResponse:
    """Step 2: Map CSV columns."""
    content = cache.get(f"import_csv_{import_id}")
    if not content:
        return redirect("import-upload")

    svc = CsvImportService(request.user_id, request.tz.key)

    try:
        headers = svc.parse_headers(content)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    if request.method == "POST":
        mapping = {
            "date": request.POST.get("col_date"),
            "amount": request.POST.get("col_amount"),
            "type": request.POST.get("col_type"),
            "note": request.POST.get("col_note"),
        }
        account_id = request.POST.get("account_id")

        if not mapping["date"] or not mapping["amount"] or not account_id:
            return HttpResponse("Date, Amount and Account are required", status=400)

        cache.set(f"import_mapping_{import_id}", json.dumps({
            "mapping": mapping,
            "account_id": account_id
        }), timeout=3600)

        return redirect("import-preview", import_id=import_id)

    # Need accounts for the dropdown
    tx_svc = TransactionService(request.user_id, request.tz)
    accounts = tx_svc.get_accounts()

    return render(request, "settings_app/import/mapping.html", {
        "headers": headers,
        "import_id": import_id,
        "accounts": accounts,
    })


@general_rate
@require_http_methods(["GET", "POST"])
def import_preview(request: AuthenticatedRequest, import_id: str) -> HttpResponse:
    """Step 3: Preview parsed rows and validate."""
    content = cache.get(f"import_csv_{import_id}")
    mapping_data_str = cache.get(f"import_mapping_{import_id}")

    if not content or not mapping_data_str:
        return redirect("import-upload")

    mapping_data = json.loads(mapping_data_str)
    mapping = mapping_data["mapping"]
    account_id = mapping_data["account_id"]

    svc = CsvImportService(request.user_id, request.tz.key)

    try:
        parsed, duplicates, errors = svc.parse_rows(content, mapping, account_id)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    # 10,000 rows limit
    if len(parsed) > 10000:
         return HttpResponse("Too many rows (max 10,000)", status=400)

    if request.method == "POST":
        # Process import
        tx_svc = TransactionService(request.user_id, request.tz)

        # We don't block duplicates, just create them all (except any the user chose to skip if we built that, but requirements say "warn, don't block")
        # For simplicity, we just batch create everything that parsed successfully.

        created, failed = tx_svc.batch_create(parsed)

        # Clean up cache
        cache.delete(f"import_csv_{import_id}")
        cache.delete(f"import_mapping_{import_id}")

        cache.set(f"import_summary_{import_id}", {
            "created": created,
            "failed": failed,
            "errors": errors,
            "duplicates": len(duplicates),
        }, timeout=3600)

        return redirect("import-summary", import_id=import_id)

    return render(request, "settings_app/import/preview.html", {
        "parsed": parsed[:50], # show top 50
        "total_rows": len(parsed),
        "duplicates": duplicates[:50],
        "total_duplicates": len(duplicates),
        "errors": errors,
        "import_id": import_id,
    })


@general_rate
def import_summary(request: AuthenticatedRequest, import_id: str) -> HttpResponse:
    """Step 4: Show summary of import."""
    summary = cache.get(f"import_summary_{import_id}")
    if not summary:
        return redirect("import-upload")

    return render(request, "settings_app/import/summary.html", {
        "summary": summary
    })
