---
id: "119"
title: "Bug: PDF export returns HTTP 500 with no user-facing error message"
type: bug
priority: medium
status: done
created: 2026-04-17
updated: 2026-04-18
---

## Description

The **Download PDF** button on `/reports` triggers `GET /reports/export-pdf` which returns a raw HTTP 500 response when WeasyPrint's native system libraries (Pango, Cairo, etc.) are not installed. The user sees a browser error with no explanation.

**Observed:** HTTP 500, body: `"PDF generation dependency (weasyprint) not installed."`  
**Expected:** User-friendly in-page error message or disabled button with tooltip when PDF is unavailable.

## Root Cause

In `backend/reports/views.py`:

```python
if HTML is None:
    return HttpResponse(
        "PDF generation dependency (weasyprint) not installed.", status=500
    )
```

This returns a raw 500 with plain text. WeasyPrint imports successfully but native libs (libpango, libcairo) are missing at runtime, causing `HTML = None`.

The issue is:
1. HTTP 500 is semantically wrong (server not misconfigured — dependency is a deployment choice)
2. Plain text response is not user-friendly
3. No graceful UI degradation (e.g. hide the button if PDF is unavailable)

## Steps to Reproduce

1. Ensure WeasyPrint native libs are not fully installed (common on macOS dev)
2. Navigate to `/reports`
3. Click **Download PDF**
4. Observe HTTP 500

## Acceptance Criteria

- [x] If WeasyPrint unavailable: return HTTP 503 (Service Unavailable) with proper JSON/HTML error
- [x] OR: add a server-side check at startup that sets a `PDF_AVAILABLE` flag, and hide/disable the Download PDF button with a tooltip: "PDF export requires additional server setup"
- [x] The user should never see a raw HTTP 500 from this endpoint

## Progress Notes

- 2026-04-17: Filed during manual QA session (ticket #117). Confirmed via `curl` returning 500. WeasyPrint import succeeds but native libs missing.
- 2026-04-18: Completed — Added `PDF_AVAILABLE` module-level flag in `reports/views.py`; changed 500→503 in fallback guard; passed `pdf_available` into `reports_page` context; template conditionally renders active teal button or grayed disabled `<span>` with tooltip; 2 new tests added (503 guard + context flag). 17 tests pass, zero lint errors.
