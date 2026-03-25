# UX Audit Summary: Error Handling, Loading States & Empty States

**Report:** `UX_ERROR_LOADING_EMPTY.md`
**Date:** March 25, 2026
**Status:** ✅ Complete

---

## Key Findings at a Glance

| Category | Finding | Severity | Impact |
|----------|---------|----------|--------|
| **Success Toasts** | Never auto-dismiss, accumulate on screen | 🔴 High | Users can't track what actions completed |
| **Error Messages** | Vague, don't explain how to fix | 🔴 High | Users repeat failed attempts blindly |
| **Empty States** | Inconsistent wording, styling, CTAs | 🟡 Medium | Poor UX consistency, unclear next steps |
| **Form Errors** | Not field-specific, buried in alerts | 🟡 Medium | Confusing on mobile, accessibility gap |
| **Permission/404 Errors** | Use Django default pages | 🟡 Medium | Breaks PWA immersion, confusing users |
| **Loading Feedback** | Minimal visibility of page progress | 🟡 Medium | Users think app froze |
| **Button Spinners** | Abrupt label swap, no transition | 🟡 Medium | Jarring UX, button size might shift |
| **Empty State Icons** | No alt text or ARIA labels | 🟡 Medium | Screen readers don't explain icon |
| **Toast Position** | May overlap bottom nav on mobile | 🟢 Low | Success message hidden behind navbar |
| **Request Timeouts** | No timeout handling | 🟢 Low | Button stuck indefinitely on slow network |
| **Skeleton Loaders** | Generic, may not match content | 🟢 Low | Layout shift when content loads |
| **Progress Bar** | Very thin (2px), not obvious | 🟢 Low | Users miss loading indication |
| **Error Type Distinction** | All errors look the same | 🟢 Low | Can't tell user's fault from system fault |

---

## Top 3 Issues to Fix First

### 1. Success Toasts Never Dismiss ⏰
**Problem:** Success messages stay forever. Multiple toasts accumulate after several actions.

**Current Code:**
```python
def success_html(message: str) -> str:
    return (
        '<div role="status" class="bg-teal-50 border border-teal-200 rounded-xl p-3 '
        'text-center animate-toast">'
        f'<p class="text-teal-800 font-semibold text-sm">{message}</p>'
        "</div>"
    )
```

**Fix:** Add JavaScript auto-dismiss after 3 seconds.

```javascript
// Auto-dismiss after 3 seconds
const toast = document.querySelector('[role="status"]');
if (toast) {
    setTimeout(() => toast.remove(), 3000);
}
```

**Effort:** 30 minutes | **Impact:** High

---

### 2. Error Messages Don't Explain How to Fix ❓
**Problem:** "Amount is required" tells what's wrong but not what to do.

**Current Pattern:**
```
❌ "Invalid amount"
❌ "Amount is required"
❌ "Validation failed"
```

**Recommended Pattern:**
```
✅ "Amount must be greater than 0 — Enter a positive number"
✅ "Email already registered — Log in or use a different email"
✅ "Credit limit exceeded — Your available balance is $500"
```

**Fix:** Update all error messages to follow `[Problem] — [Action]` format.

**Example from code:**
```python
# BEFORE
return error_response("Amount is required")

# AFTER
return error_response("Amount is required — Please enter an amount greater than 0")
```

**Effort:** 2-4 hours | **Impact:** High

---

### 3. Empty States Are Inconsistent 🎨
**Problem:** Different messaging, styling, and CTAs across app.

**Current Examples:**
- `"Welcome to ClearMoney"` (dashboard, with icon + link)
- `"No accounts yet. Tap + Account above to get started."` (accounts page, plain text)
- `"No transactions found"` (transaction list)

**Fix:** Create standardized empty state component.

```html
<div class="empty-state">
    <svg role="img" class="w-16 h-16 mx-auto text-gray-300">
        <title>No accounts</title>
        <!-- icon -->
    </svg>

    <h2 class="text-lg font-bold">Time to add your first account</h2>
    <p class="text-sm text-gray-500">
        Connect your bank, credit card, or digital wallet to get started.
    </p>
    <a href="/accounts/new" class="btn btn-primary">Create Account</a>
    <p class="text-xs text-gray-400">💡 Takes less than 2 minutes</p>
</div>
```

**Effort:** 4-6 hours | **Impact:** Medium-High

---

## Implementation Priorities

### 🏃 Week 1: Quick Wins (High ROI)
1. Fix success toast auto-dismiss (30 min)
2. Update error messages with guidance (2-4 hrs)
3. Add inline field-specific errors (3-4 hrs)

### 📋 Week 2: Pattern Library
4. Create reusable toast component (2 hrs)
5. Create standardized empty state (2-3 hrs)
6. Create form error component (1-2 hrs)

### 🎯 Week 3-4: Polish
7. Add skeleton loaders to async content (4-6 hrs)
8. Improve loading state visibility (2-3 hrs)
9. Add request timeouts (1-2 hrs)
10. Update documentation (2-3 hrs)

---

## Quick Reference: Error Message Templates

| Scenario | Template |
|----------|----------|
| **Empty field** | "[Field] is required — Please enter [field]" |
| **Invalid format** | "[Field] format is invalid — Use format [example]" |
| **Value too small** | "[Field] must be at least [limit] — You entered [value]" |
| **Value too large** | "[Field] exceeds limit — Maximum allowed is [limit]" |
| **Already exists** | "[Item] already exists — [Suggestion]" |
| **Network error** | "Connection lost — Check your internet and try again" |
| **Server error** | "Something went wrong — We're working on it. Try again later" |
| **Not found** | "[Item] was deleted — [Recovery option]" |
| **Not authorized** | "You don't have permission — [Contact support / Learn more]" |

---

## Code Examples

### ✅ Improved Error Response Pattern

**File:** `backend/core/htmx.py`

```python
def error_response(message: str, detail: str = "") -> HttpResponse:
    """Return error HTML fragment as HttpResponse with status 400.

    Args:
        message: Main error message (problem statement)
        detail: Optional detail text (how to fix / try alternative)
    """
    detail_html = f'<p class="text-xs text-red-600 mt-1">{detail}</p>' if detail else ""
    html = (
        f'<div role="alert" class="bg-red-50 border border-red-200 rounded-lg p-3">'
        f'<p class="text-sm font-medium text-red-800">{message}</p>'
        f'{detail_html}'
        f'</div>'
    )
    return HttpResponse(html, status=400)
```

**Usage:**
```python
# BEFORE
return error_response("Amount is required")

# AFTER
return error_response(
    "Amount is required",
    detail="Enter a positive amount, like 25.50"
)
```

---

### ✅ Auto-Dismissing Toast Component

**File:** `backend/templates/components/toast.html`

```html
<div id="toast-container"
     class="fixed bottom-24 left-4 right-4 z-50 space-y-2"
     role="region"
     aria-live="polite"
     aria-atomic="true"></div>

<script>
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');

    const colors = {
        success: 'bg-green-50 border-green-200 text-green-800',
        error: 'bg-red-50 border-red-200 text-red-800',
        info: 'bg-blue-50 border-blue-200 text-blue-800'
    };

    const toast = document.createElement('div');
    toast.className = `border rounded-xl p-4 animate-toast ${colors[type]}`;
    toast.innerHTML = `
        <div class="flex items-center justify-between">
            <span class="text-sm font-medium">${message}</span>
            <button class="text-xs opacity-50 hover:opacity-100" onclick="this.closest('[role=region]').removeChild(this.closest('div'))">
                ✕
            </button>
        </div>
    `;

    container.appendChild(toast);

    // Auto-dismiss after duration
    if (duration > 0) {
        setTimeout(() => toast.remove(), duration);
    }
}

// Example usage:
// showToast('Transaction created ✓', 'success', 3000);
</script>
```

---

## File References

**Complete audit:** `/docs/research/UX_ERROR_LOADING_EMPTY.md` (993 lines)

**Sections:**
1. State Pattern Inventory
2. Current Implementation Details
3. 13 UX Issues (2 high, 5 medium, 6 low)
4. Improvement Proposals with code examples
5. Pattern Library Recommendations
6. Specific Wording for Errors & Success
7. Implementation Roadmap
8. Accessibility Checklist
9. Testing Recommendations
10. Summary & Next Steps

---

## Quick Access: Issue Severity

### 🔴 HIGH (Fix ASAP)
- Success toasts never dismiss
- Error messages lack guidance
- Form errors not field-specific

### 🟡 MEDIUM (Fix in next sprint)
- Empty states inconsistent
- Permission/404 errors use browser defaults
- Loading states not obvious
- Button spinners abrupt
- Error types not distinguished

### 🟢 LOW (Nice to have)
- Toast position overlaps nav
- Progress bar too thin
- Skeleton loaders generic
- Empty state icons not accessible
- No request timeouts

---

## Next Steps

1. **Review** with product team (30 min)
2. **Prioritize** top 3 fixes (30 min)
3. **Implement** week 1 improvements (8 hrs)
4. **Test** across mobile + assistive tech (4 hrs)
5. **Document** in pattern library (3 hrs)

**Estimated total:** 2-3 sprints (60-90 hours)

---

**Generated by:** UX Audit Agent
**Last updated:** 2026-03-25
**Questions?** See full report: `UX_ERROR_LOADING_EMPTY.md`
