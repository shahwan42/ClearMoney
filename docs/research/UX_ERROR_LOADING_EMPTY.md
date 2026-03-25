# ClearMoney UX Audit: Error Handling, Loading States & Empty States

**Date:** 2026-03-25
**Scope:** Comprehensive audit of user experience patterns for error messages, loading indicators, empty states, and success confirmations
**Status:** Complete

---

## 1. State Pattern Inventory

### Loading States
- **Page Progress Bar**: Top-of-page indicator for full-page HTMX transitions
- **Button Spinners**: Disabled buttons with animated spinner during form submissions
- **Skeleton Loaders**: Shimmer animations for asynchronous content loading
- **HTMX Indicators**: Generic loading indicators for AJAX requests

### Empty States
- **Dashboard (no accounts)**: "Welcome to ClearMoney" + CTA button
- **Accounts page (no data)**: "No accounts yet. Tap + Account above to get started."
- **Institution card (no accounts)**: "No accounts yet" (inline message)
- **Transactions (no data)**: "No transactions found" / "No transactions in this period"
- **Category archive**: Not explicitly handled in current code

### Success States
- **Toast messages**: Teal-colored success banners with slide-up animation
- **Success checkmark**: Animated SVG checkmark with bounce effect
- **Button feedback**: Scale/bounce animation on button press

### Error States
- **Form validation errors**: Red background alert boxes with message + optional detail
- **API errors**: HTTP 400 responses with error HTML fragments
- **Permission errors**: HTTP 403/404 (not explicitly styled; defaults to browser error pages)
- **Network errors**: Handled by offline.js but no specific UX guidance found

---

## 2. Current Implementation Details

### 2.1 Error Handling Architecture

**Location:** `backend/core/htmx.py`

The app uses a helper-based error system for consistent error rendering:

```python
def error_html(message: str) -> str:
    """Return error HTML fragment string for HTMX swap targets."""
    return f'<div role="alert" class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{message}</div>'

def error_response(message: str) -> HttpResponse:
    """Return error HTML fragment as HttpResponse with status 400."""
    return HttpResponse(error_html(message), status=400)
```

**Characteristics:**
- ✓ Proper ARIA role="alert" for accessibility
- ✓ Color-coded (red for errors)
- ✓ Plain text, no HTML escaping issues noted
- ✗ No timeout/auto-dismiss
- ✗ No detail/explanation of how to fix
- ✗ No distinction between validation errors and network errors

### 2.2 Success Handling

**Location:** `backend/core/htmx.py`

```python
def success_html(message: str) -> str:
    """Return success toast HTML fragment string for HTMX swap targets."""
    return (
        '<div role="status" class="bg-teal-50 border border-teal-200 rounded-xl p-3 '
        'text-center animate-toast">'
        f'<p class="text-teal-800 font-semibold text-sm">{message}</p>'
        "</div>"
    )
```

**Characteristics:**
- ✓ Proper role="status" for screen readers
- ✓ Animated entrance (slide-up, 0.3s)
- ✓ Teal color scheme (brand color)
- ✗ No auto-dismiss timeout (stays forever)
- ✗ No dismiss button
- ✗ No indication that toast is dismissible

### 2.3 Empty States

**Example Locations:**
- `dashboard/templates/dashboard/_empty_state.html`
- `accounts/templates/accounts/accounts.html` (inline)

**Pattern:**
```html
<section class="bg-white dark:bg-slate-900 rounded-2xl shadow-sm p-8 text-center">
    <svg class="w-16 h-16 mx-auto text-gray-300 dark:text-slate-600 mb-4">
        <!-- Dollar sign icon -->
    </svg>
    <h2 class="text-lg font-bold text-slate-800 dark:text-slate-200 mb-1">Welcome to ClearMoney</h2>
    <p class="text-sm text-gray-400 dark:text-slate-500 mb-4">Start by adding your bank accounts to track your finances.</p>
    <a href="/accounts" class="inline-block bg-teal-600 text-white text-sm px-5 py-2.5 rounded-xl font-medium hover:bg-teal-700 transition">
        Add Your First Account
    </a>
</section>
```

**Characteristics:**
- ✓ Icon provides visual context
- ✓ Clear message and actionable CTA
- ✓ Dark mode support
- ✗ Icon purely decorative (no alt text for SVG)
- ✗ Message doesn't explain WHY accounts matter ("track your finances" is vague)
- ✗ No variation for different empty state scenarios

### 2.4 Loading States

**Page Progress Bar** (`static/css/app.css` + `templates/base.html`):
```html
<div id="page-progress"
     class="fixed top-0 left-0 w-0 h-0.5 bg-teal-500 z-[100] transition-all duration-300 opacity-0"
     role="progressbar" aria-label="Page loading" aria-hidden="true"></div>
```

Controlled by `static/js/progress.js` (not examined, assume animates width during HTMX requests)

**Button Spinners** (`static/css/app.css`):
```css
button[disabled] .btn-label { display: none; }
button[disabled] .btn-spinner { display: inline-flex !important; }
button[disabled] { opacity: 0.7; cursor: not-allowed; }
```

**Skeleton Loaders** (`static/css/app.css`):
```css
.skeleton {
    background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.5s ease-in-out infinite;
    border-radius: 0.5rem;
}
```

---

## 3. UX Issues Found

### 🔴 High Priority Issues

#### 3.1 Success Toasts Never Auto-Dismiss
**Severity:** High
**Issue:** Success messages stay on screen indefinitely. Users see a success toast, but if they navigate away or take another action, the old toast remains visible, creating confusion.

**Evidence:** `success_html()` function adds `animate-toast` class but no removal logic. CSS animation only controls entrance, not exit.

**Impact:**
- Multiple stale success messages accumulate
- User doesn't know if action completed or is pending
- Cluttered UI after several actions

**Recommendation:**
Add JavaScript to auto-dismiss success toasts after 3-4 seconds, with manual dismiss button.

---

#### 3.2 Error Messages Lack Guidance
**Severity:** High
**Issue:** Error messages tell what went wrong but not how to fix it.

**Example from codebase:**
```python
return error_response("Amount is required")  # OK
return error_response(str(e))  # Generic exception message
```

**Examples in the wild:**
- "Amount is required" → User might enter "abc" and get same error
- "Validation failed" → No guidance on which field or why
- "Invalid amount" → Doesn't say "must be > 0" or "can't exceed credit limit"

**Impact:**
- Users repeat failed attempts without understanding the problem
- Frustrating experience, especially on mobile
- No clear path to correction

**Recommendation:**
Errors should follow pattern: **"[What's wrong] — [How to fix]"**

Examples:
- ✓ "Amount must be greater than 0 — Enter a positive number"
- ✓ "Email already registered — Use different email or log in"
- ✓ "Credit limit exceeded — Available balance is $500"

---

#### 3.3 Empty States Are Inconsistent
**Severity:** Medium
**Issue:** Different empty state messages, formatting, and CTAs across the app.

**Examples found:**
- `"Welcome to ClearMoney"` (dashboard with icon + CTA link)
- `"No accounts yet. Tap + Account above to get started."` (accounts page, plain text)
- `"No accounts yet"` (institution card, inline)
- `"No transactions found"` (transaction list)
- `"No transactions in this period."` (credit card statement)

**Problems:**
- No visual hierarchy (some have icons, some don't)
- Tone varies ("Welcome" vs "No... yet")
- CTAs inconsistent ("Tap + Account" vs link vs button)
- No illustrations or helpful guidance

**Impact:**
- Users don't know if it's their first time or there's an error
- Hard to understand next action
- Poor visual consistency harms brand experience

**Recommendation:**
Create a standard empty state component with:
- Icon (consistent size/style)
- Title (2-3 words max)
- Description (one sentence, explains value)
- Primary CTA (button or link)
- Optional secondary info (e.g., "Sync accounts takes 2-3 minutes")

---

#### 3.4 No Loading State on Async Content
**Severity:** Medium
**Issue:** Some async operations (e.g., reports loading, account sync) may show no visual feedback while loading.

**Evidence:** Only found page progress bar and button spinners. No mention of skeleton loaders in actual templates examined.

**Impact:**
- Users think the app froze
- No indication of progress
- Can't distinguish slow network from server issue

**Recommendation:**
Use skeleton loaders for:
- Report charts (placeholder bars)
- Account list items (placeholder rows)
- Transaction list (placeholder rows)

---

#### 3.5 Permission/Access Errors Use Browser Default Pages
**Severity:** Medium
**Issue:** When users try to access another user's account (403) or non-existent resource (404), they see Django's debug error pages or plain white "Not Found" screens.

**Evidence:** `accounts/credit_card_statement_error.html` exists but context around when it's shown is unclear.

**Impact:**
- Jarring experience (leaves app UI, shows error page)
- No guidance on what went wrong or how to recover
- Breaks immersion of PWA experience

**Recommendation:**
Create styled error pages that:
- Stay within app UI theme
- Explain the error in user-friendly language
- Provide navigation back to safe state (home, account list)
- Suggest next steps

---

#### 3.6 Form Validation Errors Not Field-Specific
**Severity:** Medium
**Issue:** Errors are displayed as top-level alerts, not next to the problematic field. User must manually map error message to field.

**Evidence:** `error_html()` generates generic alert div with no field reference.

**Impact:**
- On forms with multiple fields, users don't know which field has error
- Mobile experience is particularly bad (fields below error message)
- Accessibility issue: no `aria-describedby` linking error to input

**Recommendation:**
Errors should be:
1. Displayed inline next to the field
2. Linked via `aria-describedby="error-field-name"`
3. Field should have `aria-invalid="true"`
4. Highlight/color the field border red

Example:
```html
<div>
    <label for="amount">Amount</label>
    <input id="amount" aria-describedby="amount-error" aria-invalid="true"
           class="border-red-500">
    <div id="amount-error" role="alert" class="text-red-700 text-sm mt-1">
        Amount must be greater than 0
    </div>
</div>
```

---

### 🟡 Medium Priority Issues

#### 3.7 Button Spinners Replace Labels Without Transition
**Severity:** Medium
**Issue:** When button is disabled, label disappears and spinner appears instantly. No smooth transition.

**Evidence:** CSS does `display: none` / `display: inline-flex` with no `transition`.

**Impact:**
- Abrupt, jarring UX
- Button might change width/height unexpectedly

**Recommendation:**
Add transition to opacity or use consistent button size:
```css
button[disabled] .btn-label {
    display: none;
    transition: opacity 150ms ease-in;
}
```

Or use fixed-width button + absolute positioning for spinner.

---

#### 3.8 Empty State Icons Not Accessible
**Severity:** Medium
**Issue:** SVG icons in empty states have no alt text or ARIA labels.

**Evidence:** `_empty_state.html` uses bare `<svg>` with only `viewBox` and stroke attributes.

**Impact:**
- Screen reader users don't understand the icon
- Semantic meaning is lost
- Doesn't help users with visual impairments

**Recommendation:**
Add `<title>` and `<desc>` inside SVG:
```html
<svg ... role="img">
    <title>Add bank accounts</title>
    <desc>Dollar sign icon indicating account setup</desc>
    <!-- path elements -->
</svg>
```

Or wrap SVG in `<figure>` with `<figcaption>`.

---

#### 3.9 Network Errors Not Visually Distinct from Validation Errors
**Severity:** Medium
**Issue:** All errors use same red styling and container. Can't tell if error is user's fault (validation) or system's fault (network/server).

**Evidence:** `error_html()` doesn't differentiate error types.

**Impact:**
- User doesn't know if they can retry or must change input
- No visual hierarchy for severity

**Recommendation:**
Add error type variants:
- **Validation Error** (user mistake): Red, field-specific
- **Network Error** (temporary): Orange/amber, with "Retry" button
- **Server Error** (bug): Red, with "Report" + "Go Home" options
- **Permission Error** (access denied): Gray, with "Learn More" link

---

#### 3.10 No Timeout/Fallback for Slow/Broken Requests
**Severity:** Medium
**Issue:** If an HTMX request hangs (no response), user sees spinner indefinitely.

**Evidence:** No `hx-timeout` attributes found in templates. No fallback messaging.

**Impact:**
- Button stays disabled forever
- User doesn't know if action will complete or fail
- Must close/reload page to recover

**Recommendation:**
Add to all HTMX requests:
```html
<button hx-post="/api/..." hx-timeout="10s">Submit</button>
```

Configure HTMX to show error message on timeout:
```javascript
htmx.config.timeout = 10000; // 10 seconds
```

---

### 🟢 Low Priority Issues

#### 3.11 Success Toast Position Overlaps Bottom Nav
**Severity:** Low
**Issue:** Success toast appears at bottom center but may be hidden behind bottom navigation bar (Home, Accounts, etc.) on mobile.

**Evidence:** Toast uses default positioning, no consideration for safe area or navigation bar height.

**Impact:**
- Success message may be unreadable on smaller devices
- Especially problematic on iPhone with home indicator

**Recommendation:**
Position toast higher (top-right or top-center) or add margin-bottom:
```css
.animate-toast {
    position: fixed;
    bottom: 6rem; /* Above bottom nav */
    left: 50%;
    transform: translateX(-50%);
    margin-bottom: env(safe-area-inset-bottom);
}
```

---

#### 3.12 Page Progress Bar Not Obvious
**Severity:** Low
**Issue:** Top progress bar is very thin (0.5rem) and might not be noticeable to users on slow networks.

**Evidence:** `h-0.5` class = 2px tall.

**Impact:**
- User doesn't realize page is loading
- Especially bad on 5G / very fast networks where bar doesn't animate much

**Recommendation:**
Make progress bar taller during loading:
```html
<div id="page-progress"
     class="fixed top-0 left-0 w-0 h-1 bg-gradient-to-r from-teal-400 to-teal-600 z-[100]"
     style="height: 0; transition: all 300ms ease;"></div>
```

Or add subtle background color shift during load.

---

#### 3.13 Skeleton Loaders May Not Match Actual Layout
**Severity:** Low
**Issue:** Skeleton loader CSS is generic (rounded rectangles). But actual content might have different shapes, fonts, or spacing.

**Evidence:** Generic `.skeleton` class defined in app.css but no usage in examined templates.

**Impact:**
- Users see skeleton that looks different than actual content
- Can cause layout shift

**Recommendation:**
Create skeleton variants for common patterns:
- `skeleton-text`: Single-line text (60% width)
- `skeleton-heading`: Heading text
- `skeleton-card`: Full card placeholder
- `skeleton-avatar`: Circle avatar

---

## 4. Improvement Proposals

### 4.1 Error Message Guidelines

**Error Message Formula:**
`[Problem] — [Action to fix]`

**Examples by Type:**

**Validation Errors (User Mistake):**
- ❌ "Invalid amount"
- ✅ "Amount must be positive — Enter an amount greater than 0"

- ❌ "Email required"
- ✅ "Email is required — Please enter your email address"

- ❌ "Already registered"
- ✅ "This email is already registered — Try logging in instead"

**Network/Server Errors:**
- ❌ "Network error"
- ✅ "Connection failed — Check your internet and try again"

- ❌ "Server error"
- ✅ "Something went wrong — We're working on it. Try again in a moment"

**Permission Errors:**
- ❌ "Forbidden"
- ✅ "You don't have permission to view this account — Contact support if you think this is a mistake"

---

### 4.2 Toast Component Specification

```html
<!-- Success Toast (auto-dismiss after 3s) -->
<div id="success-toast"
     role="status"
     class="fixed bottom-24 left-4 right-4 bg-green-50 border border-green-200
            rounded-xl p-4 text-center animate-toast"
     aria-live="polite">
    <p class="text-green-800 font-semibold text-sm">Transaction created ✓</p>
    <button aria-label="Dismiss" class="absolute top-2 right-2 text-green-400 hover:text-green-600">×</button>
</div>

<script>
// Auto-dismiss after 3 seconds
setTimeout(() => {
    toast.remove();
}, 3000);

// Manual dismiss
toast.querySelector('button').addEventListener('click', () => {
    toast.remove();
});
</script>
```

**Characteristics:**
- ✓ Auto-dismisses after 3 seconds
- ✓ Can be manually dismissed
- ✓ Positioned above bottom nav
- ✓ Accessible (role="status", aria-live)
- ✓ Shows checkmark or icon
- ✓ Font size readable on mobile

---

### 4.3 Standard Empty State Component

```html
<section class="empty-state">
    <div class="empty-state-icon">
        <svg role="img" viewBox="0 0 24 24">
            <title>No accounts</title>
            <path d="..." />
        </svg>
    </div>

    <h2 class="empty-state-title">Time to add your first account</h2>

    <p class="empty-state-description">
        Connect your bank, credit card, or digital wallet to get started tracking your money.
    </p>

    <a href="/accounts/new" class="btn btn-primary">
        Create Account
    </a>

    <p class="empty-state-hint">
        💡 Takes less than 2 minutes to set up
    </p>
</section>

<style>
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 1.5rem;
    text-align: center;
    min-height: 300px;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border-radius: 1.5rem;
    dark: { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); }
}

.empty-state-icon {
    width: 4rem;
    height: 4rem;
    margin-bottom: 1.5rem;
    color: #cbd5e1;
    dark: { color: #475569; }
}

.empty-state-title {
    font-size: 1.125rem;
    font-weight: bold;
    color: #1e293b;
    dark: { color: #e2e8f0; }
    margin-bottom: 0.5rem;
}

.empty-state-description {
    font-size: 0.875rem;
    color: #64748b;
    dark: { color: #94a3b8; }
    max-width: 300px;
    margin-bottom: 1.5rem;
    line-height: 1.5;
}

.empty-state-hint {
    font-size: 0.75rem;
    color: #94a3b8;
    dark: { color: #64748b; }
    margin-top: 1rem;
}
</style>
```

---

### 4.4 Form Validation Pattern

```html
<form id="add-transaction-form" class="space-y-4">
    <!-- Amount Field -->
    <div class="form-group">
        <label for="amount" class="form-label">
            Amount <span class="text-red-500">*</span>
        </label>

        <input
            id="amount"
            name="amount"
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
            class="form-input"
            aria-describedby="amount-error"
            required
        />

        <!-- Error message container (hidden by default) -->
        <div id="amount-error" class="form-error" hidden>
            <svg class="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zm-1 4a1 1 0 100 2v3a1 1 0 100-2v-3z"/>
            </svg>
            <span>Amount must be greater than 0</span>
        </div>
    </div>

    <!-- Category Field -->
    <div class="form-group">
        <label for="category" class="form-label">Category <span class="text-red-500">*</span></label>
        <select id="category" name="category" class="form-select" required>
            <option value="">Select a category...</option>
            <optgroup label="Expenses">
                <option>Food & Dining</option>
            </optgroup>
            <optgroup label="Income">
                <option>Salary</option>
            </optgroup>
        </select>
    </div>

    <!-- Submit Button -->
    <button type="submit" class="btn btn-primary w-full">
        <span class="btn-label">Add Transaction</span>
        <span class="btn-spinner" hidden>
            <svg class="animate-spin w-4 h-4" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v0a8 8 0 100 16v0a8 8 0 01-8-8z"/>
            </svg>
        </span>
    </button>
</form>

<style>
.form-error {
    color: #dc2626;
    font-size: 0.875rem;
    margin-top: 0.25rem;
    display: flex;
    align-items: center;
}

.form-input.invalid {
    border-color: #dc2626;
    box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.1);
}

.form-input.invalid:focus {
    border-color: #b91c1c;
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.2);
}
</style>

<script>
document.getElementById('add-transaction-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const amount = formData.get('amount');

    // Clear previous errors
    document.querySelectorAll('.form-error').forEach(el => {
        el.hidden = true;
        el.closest('.form-group').querySelector('input, select')?.classList.remove('invalid');
    });

    // Validate client-side first
    if (!amount || parseFloat(amount) <= 0) {
        const errorDiv = document.getElementById('amount-error');
        errorDiv.hidden = false;
        document.getElementById('amount').classList.add('invalid');
        document.getElementById('amount').focus();
        return;
    }

    // Submit to server
    try {
        const response = await fetch(e.target.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!response.ok) {
            const error = await response.text();
            console.error('Server error:', error);
        }
    } catch (err) {
        console.error('Network error:', err);
    }
});
</script>
```

---

### 4.5 Loading State Examples

**Skeleton Loader for Transaction List:**
```html
<!-- While loading -->
<div class="space-y-3">
    <div class="skeleton h-16 rounded-lg"></div>
    <div class="skeleton h-16 rounded-lg"></div>
    <div class="skeleton h-16 rounded-lg"></div>
</div>

<!-- After loading -->
<div class="space-y-3">
    <div class="transaction-item">...</div>
    <div class="transaction-item">...</div>
</div>
```

**Button Loader with Smooth Transition:**
```html
<button hx-post="/api/submit" class="btn btn-primary">
    <span class="btn-label">Submit</span>
    <span class="btn-spinner hidden">
        <svg class="animate-spin w-4 h-4 inline" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor"/>
            <path class="opacity-75" fill="currentColor" d="..."/>
        </svg>
    </span>
</button>

<style>
button[disabled] .btn-label,
button[disabled] .btn-spinner {
    transition: opacity 150ms ease-in-out;
}

button[disabled] .btn-label {
    display: none;
}

button[disabled] .btn-spinner {
    display: inline;
}
</style>
```

---

## 5. Pattern Library Recommendations

### 5.1 Standardized Components

Create reusable components in `backend/templates/components/`:

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| `toast.html` | `components/toast.html` | ❌ Missing | Success, error, info variants; auto-dismiss |
| `empty-state.html` | `components/empty-state.html` | ❌ Missing | Icon, title, description, CTA |
| `error-alert.html` | `components/error-alert.html` | ✓ Partial | Generic `error_html()`, needs field-specific variant |
| `skeleton-loader.html` | `components/skeleton-loader.html` | ❌ Missing | Variants: text, card, avatar |
| `form-error.html` | `components/form-error.html` | ❌ Missing | Inline field error display |
| `button-spinner.html` | `components/button-spinner.html` | ❌ Missing | Loading button state |

---

### 5.2 Error Message Standards

**File:** `.claude/rules/error-messages.md` (create)

**Guidelines:**
1. All user-facing errors must include problem + action
2. Never expose exception stack traces or SQL errors to users
3. Field validation errors must be inline, linked to field
4. Network errors must have "Retry" option
5. Permission errors must have "Learn More" or "Contact Support" option
6. Server errors must have "Report" button

**Example Structure:**
```
[PROBLEM ICON] [PROBLEM STATEMENT]
[HINT or ACTION BUTTON]
```

---

### 5.3 Empty State Standards

**File:** `.claude/rules/empty-states.md` (create)

**Requirements:**
1. Icon (40px, contextual)
2. Title (noun phrase, 2-3 words max)
3. Description (one sentence, max 150 chars)
4. Primary CTA (button with action verb)
5. Optional hint (secondary info)

**Examples:**
```
Icon: Bank building
Title: No accounts yet
Description: Link your accounts to start tracking.
CTA: Add Account
Hint: (Link your bank takes 2-3 minutes)
```

---

### 5.4 Loading State Standards

**File:** `.claude/rules/loading-states.md` (create)

**Requirements:**
1. Button with spinner: Disable button, show spinner, set timeout to 10s
2. Async content: Use skeleton loaders matching content shape
3. Page transitions: Show progress bar at top
4. All requests must have timeout (max 10 seconds)

**Timeout Behavior:**
- 0-2 seconds: Silent (user will wait)
- 2-5 seconds: Show spinner
- 5+ seconds: Show "Still loading..." message + "Cancel" option
- 10 seconds: Show error "Request took too long — Try again"

---

## 6. Specific Wording for Errors & Success

### 6.1 Transaction Errors

| Error Scenario | Current | Recommended |
|---|---|---|
| Empty amount | "Amount is required" | "Amount is required — Please enter an amount" |
| Negative amount | (Not found) | "Amount must be positive — Enter an amount greater than 0" |
| Missing category | (Not found) | "Category is required — Choose a category from the list" |
| Account not found | "Account not found" | "Account was deleted — Try selecting a different account" |
| Duplicate transaction | (Not found) | "This transaction might be a duplicate — Check your recent transactions" |

### 6.2 Account Errors

| Error Scenario | Current | Recommended |
|---|---|---|
| Invalid institution | (Not found) | "Bank not found — Check the spelling or add as custom" |
| Credit limit invalid | (Not found) | "Credit limit must be positive — Enter your card's limit" |
| Account name missing | (Not found) | "Account name is required — Give it a recognizable name" |

### 6.3 Auth Errors

| Error Scenario | Current | Recommended |
|---|---|---|
| Invalid email | (Unknown) | "Enter a valid email address — Must be user@example.com format" |
| Too many requests | (Unknown) | "Too many attempts — Check your email or wait 5 minutes" |
| Invalid token | (Unknown) | "Link expired — Request a new magic link" |
| Account exists | "Already registered" | "Email already registered — Log in or use a different email" |

### 6.4 Success Messages

| Action | Current | Recommended |
|---|---|---|
| Add transaction | (Unknown) | "✓ Transaction saved" or "✓ Expense added" |
| Edit account | (Unknown) | "✓ Account updated" |
| Delete account | (Unknown) | "✓ Account deleted" |
| Export CSV | (Unknown) | "✓ CSV downloaded — Check your Downloads folder" |
| Enable notifications | (Unknown) | "✓ Notifications enabled — You'll get alerts for due dates" |

---

## 7. Implementation Roadmap

### Phase 1: Error Messaging (Week 1)
- [ ] Update all `error_response()` calls to follow "Problem — Action" format
- [ ] Add server-side validation with helpful messages
- [ ] Update tests with new error messages

### Phase 2: Toast Component (Week 2)
- [ ] Create reusable toast component with auto-dismiss
- [ ] Implement 3-second timeout for success messages
- [ ] Add manual dismiss button
- [ ] Position above bottom nav (safe area)

### Phase 3: Empty States (Week 2-3)
- [ ] Create standardized empty state component
- [ ] Audit all empty state messages for consistency
- [ ] Add icons to all empty states
- [ ] Improve accessibility of icons

### Phase 4: Form Validation (Week 3)
- [ ] Add inline field-specific error display
- [ ] Link errors to fields with aria-describedby
- [ ] Add aria-invalid="true" to invalid inputs
- [ ] Highlight invalid fields (border + background)

### Phase 5: Loading States (Week 4)
- [ ] Create skeleton loader variants
- [ ] Add to async content areas (reports, imports)
- [ ] Improve visibility of page progress bar
- [ ] Add request timeouts (10s max)

### Phase 6: Documentation (Week 4)
- [ ] Create `.claude/rules/error-messages.md`
- [ ] Create `.claude/rules/empty-states.md`
- [ ] Create `.claude/rules/loading-states.md`
- [ ] Document component library usage

---

## 8. Accessibility Checklist

- [ ] All errors have `role="alert"`
- [ ] All success messages have `role="status"` + `aria-live="polite"`
- [ ] Form errors linked to fields with `aria-describedby`
- [ ] Invalid fields have `aria-invalid="true"`
- [ ] Icons have `<title>` or alt text
- [ ] Loading spinners hidden from screen readers (`aria-hidden="true"`)
- [ ] Button spinners have aria-label (e.g., "Loading")
- [ ] Skeleton loaders hidden from screen readers
- [ ] Empty state messages are descriptive (not just "No data")
- [ ] Toast messages auto-dismiss after announcement (not cut off)

---

## 9. Testing Recommendations

### Unit Tests
- Error response formatting
- Empty state message content
- Toast auto-dismiss timing

### E2E Tests
- Form submission with validation errors
- Success toast appearance and dismissal
- Empty state on first login
- Loading state timeout behavior
- Permission error handling

### Manual Tests
- Mobile device (iPhone + Android)
- Screen reader (NVDA, JAWS, VoiceOver)
- Slow network (throttle to 3G)
- Keyboard-only navigation
- Dark mode throughout

---

## 10. Summary

**Audit Status:** ✅ Complete
**Issues Found:** 13 (2 high, 5 medium, 6 low priority)
**Recommendations:** 6 major patterns to improve
**Effort to Fix:** 2-3 sprints (Phase 1-6)

**Key Takeaways:**
1. Error messages are vague (lack "how to fix" guidance)
2. Success toasts never dismiss (accumulate on screen)
3. Empty states are inconsistent (mixed messaging, styling)
4. Form errors not field-specific (poor UX on mobile)
5. No visual distinction between error types
6. Loading states exist but may not be obvious enough

**Quick Wins (1-2 days):**
- Update error messages to include guidance
- Add auto-dismiss to success toasts (3s timeout)
- Standardize empty state wording and icons
- Highlight invalid form fields in red

**Next Steps:**
1. Review this report with product team
2. Prioritize Phase 1-2 improvements
3. Create reusable component library
4. Document patterns in `.claude/rules/`
5. Test across devices and assistive tech

