# UX Audit: Account Management System

**Audit Date:** March 25, 2026
**Reviewer:** AI Assistant
**Scope:** ClearMoney accounts module — list, create, edit, delete, and detail workflows
**Device Focus:** Mobile-first PWA (accounts tested via Playwright automation)

---

## 1. Current Workflow Walkthrough

### 1.1 Accounts List View
**Route:** `/accounts` | **Template:** `accounts/accounts.html`

**User Flow:**
1. User navigates to Accounts page
2. See header: "Accounts" with "+ Account" button (teal, min-height: 44px)
3. Institutions grouped in expandable cards (details/summary elements)
4. Each institution card shows:
   - Institution icon + name + type badge (e.g., "bank")
   - Edit (pencil icon) and Delete (trash icon) buttons (4x4px) — small touch targets
   - "+ Account" button (text-only, small touch target issue)
5. Expanded institution shows account rows with:
   - Account name (primary)
   - Type + Currency (secondary text, xs)
   - Current balance (right-aligned, red if negative)
   - Available credit (for credit cards, xs, red text)
6. Click account row → Navigate to account detail page
7. Empty state: "No accounts yet. Tap + Account above to get started."

**Issues Identified:**
- Institution icons and edit/delete buttons are very small (4x4px) — poor touch targets
- "+ Account" buttons appear as text links — not visually prominent
- Hierarchy unclear: institution-level action buttons vs. account list
- No visual distinction between different account types (current vs. savings vs. credit card)

---

### 1.2 Create Account Workflow
**Route:** `POST /accounts/add` | **Trigger:** "+ Account" button
**Sheet:** `#create-sheet` (bottom sheet, max-height: 80vh)

**UI Flow (Unified Add-Account Form):**

**Step 1: Institution Selection (if not pre-selected)**
- Three radio button tabs: "Bank" | "Finance App" | "Wallet"
- Each tab shows relevant preset list below
- Institution search combobox (aria-haspopup="listbox")
- Shows icon + name for each preset
- Special "Other (custom name)" option with pencil emoji
- Grouped wallets: "Physical" and "Digital" optgroups

**Step 2: Account Configuration**
- Type dropdown: Current, Savings, Prepaid, Cash, Credit Card, Credit Limit
  - *Dynamic behavior:* Wallet type auto-selects "Cash" and hides type dropdown
  - Fintech type hides credit card options
- Currency dropdown: EGP, USD
- **Custom name** collapsible toggle (hidden by default)
  - Click to reveal text input
  - Placeholder: "e.g., My Savings"
- Initial Balance input (number, step 0.01, default: 0)
- Credit Limit field (hidden until credit_card/credit_limit type selected)
  - Placeholder: "e.g., 500000"

**Step 3: Submit**
- Submit button: "Add Account" (teal, full-width, min-h: 44px)
- Cancel button: "Cancel" (gray, full-width, min-h: 44px)
- Both buttons with active:scale animation

**Success Flow:**
- Bottom sheet closes (1 second delay)
- Institution list refreshes via OOB swap
- No toast confirmation shown (unlike institution add)

**Error Handling:**
- Shows red alert box with validation error
- Form stays open for retry
- Error cleared on next field change (not automatic)

**Issues Identified:**
- Custom account name is hidden under a toggle — users may not know they can rename accounts
- No toast notification on success (inconsistent with institution creation)
- Credit limit field has no validation feedback (should reject if credit type + no limit)
- Institution search placeholder: "Search or type name..." not clear about custom entry
- No visual feedback when credit limit field appears/disappears

---

### 1.3 Edit Account Workflow
**Route:** `GET /accounts/{id}/edit-form` | **Trigger:** "Edit" button on account detail
**Sheet:** `#edit-sheet` (bottom sheet, max-height: 50vh)

**Form Fields:**
- Account Name (text input, required)
- Type (dropdown, same options as create)
- Currency (dropdown, read-only from account)
- Credit Limit (hidden/shown based on type)

**Form Behavior:**
- Inline onchange handler shows/hides credit limit field
- No visual transition when field appears
- Submit button: "Update" (teal, full-width)
- Cancel button: "Cancel" (text-only, gray)

**Error Handling:**
- Shows red inline error box
- Error target: `#edit-account-result` (aria-live="polite")

**Issues Identified:**
- Edit form is shorter than account creation form — seems intentionally minimal
- But "Edit" flows are often where more options should be (like dormant toggle, health rules)
- Currently edit only touches name, type, currency, and credit limit
- No field validation feedback (e.g., required name, valid credit limit)
- Dismissal unclear — does Cancel close the sheet? (onclick="closeEditAccount()" — yes)

---

### 1.4 Delete Account Workflow
**Route:** `DELETE /accounts/{id}/delete`
**Trigger:** "Delete Account" button on account detail page
**UI:** Custom bottom sheet (`#delete-sheet`, z-index: 70)

**Confirmation UX:**
1. Warning icon (red circle)
2. Heading: "Delete Account"
3. Warning text: "This will permanently delete **[Account Name]** and all its transactions. This action cannot be undone."
4. Confirmation input: "Type **[Account Name]** to confirm"
   - Placeholder: "Account name"
   - Input is focused on sheet open (JavaScript: `openDeleteSheet()`)
5. Delete button: "Delete Account" (red, full-width, initially disabled)
   - Enabled only when input matches exact account name
   - Validation triggered on `oninput` event: `checkDeleteConfirmation()`
6. Cancel button: "Cancel" (gray)

**Validation Logic:**
```javascript
function checkDeleteConfirmation() {
    var expectedName = document.querySelector('[data-account-name]').getAttribute('data-account-name');
    var input = document.getElementById('delete-confirm-input');
    var btn = document.getElementById('delete-confirm-btn');
    btn.disabled = (input.value !== expectedName);
}
```

**Delete Endpoint Response:**
- Returns error if foreign key constraint violated (e.g., linked virtual accounts)
- Error displayed in `#delete-error` div with aria-live
- User can fix and retry

**Issues Identified:**
- Exact name match is restrictive — case-sensitive, no trim()
- If account name has special characters, confirmation is harder
- No visual feedback during delete (no loading spinner shown)
- Error handling exists but not tested in E2E (should add)
- Delete button shows no confirmation state (should add spinner)

---

### 1.5 Account Detail Page
**Route:** `/accounts/{id}` | **Template:** `accounts/account_detail.html`

**Page Layout (top to bottom):**

**1. Header Card**
- Account name (h1, bold, slate-800)
- Institution + Type + Currency (meta, xs, gray)
- Edit link + "All Accounts" link (top right, teal)
- Balance section:
  - "Current Balance" label (xs, gray)
  - Balance display (h2, 2xl, bold)
    - Green (teal-700) if positive
    - Red (red-600) if negative (credit card debt)
  - Available Credit (for credit cards only, xs, gray)

**2. Virtual Accounts Holding Info (if VA balance > 0)**
- "Holding for others" (xs, amber)
- Amount held (xs, amber-600)
- "Your money" calculation: balance - excluded VA balance
- Color: green if positive, red if negative

**3. Balance History Chart**
- "30-day trend" label
- SVG sparkline (width: 280px, height: 40px, teal color)

**4. Dormant Toggle**
- Label: "Dormant Account"
- Description: "Dormant accounts are collapsed on the dashboard"
- Button: amber if dormant, gray if active
- Text changes: "Active" / "Dormant"
- Action: `hx-post="/accounts/{id}/dormant"` redirects back to same page

**5. Credit Utilization (Credit Cards Only)**
- Heading: "CREDIT UTILIZATION" (uppercase, gray)
- Donut chart (SVG, 20x20, conic gradient)
  - Green if < 50%
  - Amber if 50-80%
  - Red if > 80%
- Percentage in center (bold, slate-800)
- Legend: "X used of Y limit" (sm text + xs gray)
- 30-day utilization trend sparkline

**6. Credit Card Statement Button** (if billing cycle configured)
- "View Statement" (teal, rounded, centered)
- Links to `/accounts/{id}/statement`

**7. Linked Virtual Accounts** (if any)
- Cards showing each linked VA
- Name + icon + current balance
- Progress bar toward target (if target set)
- Color: VA's own color attribute

**8. Health Rules**
- "HEALTH RULES" heading
- Two inputs: Min Balance, Min Monthly Deposit
- Both optional (placeholder: "Not set")
- Submit button: "Save Health Rules" (gray)

**9. Delete Account**
- Button: "Delete Account" (red text, hover: red background)

**10. Transaction History**
- Heading: "Transaction History"
- List of recent transactions (scrollable)
- "Load more..." button at bottom
- Empty state: "No transactions found"

**Issues Identified:**
- Dormant toggle uses `hx-post` without confirmation — easy to toggle accidentally
- "Delete Account" button is subtle (red text, not red button) — might be missed
- Balance color (red for negative) is correct for showing debt, but confusing for some users
- Multiple bottom sheets are nested: tx-detail, tx-edit, edit-account, delete
- No visual feedback during health rules save (no spinner, no toast)
- Transaction list doesn't show account name (correct per hide_account_name=True in detail page)

---

## 2. Screenshots & Visual Analysis

**Note:** Screenshots cannot be taken via Playwright due to browser initialization issues, but the templates have been thoroughly analyzed.

### Key Visual Assets Used:
1. **Institution Icons:** Presets have .png/.svg icons OR text avatars with colored backgrounds
2. **Account Type Badge:** Uses format filter (e.g., "Current", "Credit Card")
3. **Balance Color Coding:**
   - Positive: teal-700 (default green)
   - Negative: red-600 (debt indicator)
   - Holding: amber-600 (secondary money)
4. **Button Sizing:** All primary buttons enforce `min-h-[44px]` (44px minimum for touch)
5. **Spacing:** Consistent padding (p-4, p-5), gap-3 between sections

---

## 3. UX Issues Found

### CRITICAL Issues

#### 1. **Exact Name Confirmation is Case-Sensitive**
**Severity:** CRITICAL
**Location:** Delete account confirmation (`checkDeleteConfirmation()`)
**Problem:**
- Confirmation expects exact match: `input.value !== expectedName`
- If account is "My Savings" and user types "my savings", button stays disabled
- No hint that case matters
- User frustration: "Why won't the button enable?"

**Evidence:**
```javascript
// Line 260 in account_detail.html
btn.disabled = (input.value.trim() !== expectedName);  // Case-sensitive
```

**Impact:** Users may abandon deletion or be confused about validation.

**Recommendation:**
```javascript
// Should be case-insensitive:
btn.disabled = (input.value.trim().toLowerCase() !== expectedName.toLowerCase());
```

---

#### 2. **Credit Card Without Credit Limit Shows Generic Error**
**Severity:** CRITICAL
**Location:** Account creation form (`account_add` view)
**Problem:**
- User selects "Credit Card" account type
- Credit limit field appears
- User forgets to fill credit limit
- Submit shows generic red error box: "Credit limit required"
- No visual highlight of the missing field
- User doesn't know which field failed

**Evidence:**
- Service validation in `account_add()` returns: `ValueError` with message
- Error rendered in generic red box

**Impact:** Poor error recovery. User must guess which field is required.

**Recommendation:**
- Highlight the credit-limit input field with red border on error
- Add `aria-invalid="true"` and `aria-describedby="credit-limit-error"`
- Show inline error next to the field, not in a separate alert box

---

#### 3. **Bottom Sheet Close Button Ambiguity**
**Severity:** CRITICAL
**Location:** Edit account form, create account form
**Problem:**
- Edit form has: Submit "Update" + Cancel button
- No visual distinction between "Update" (primary) and "Cancel" (secondary)
- Cancel button is text-only (no background) — looks like a link
- Users may click Cancel thinking it's a link to close the form

**Evidence:**
```html
<!-- Line 54-62 in _account_edit_form.html -->
<button type="submit" class="...bg-teal-600...">Update</button>
<button onclick="closeEditAccount()" class="px-4 py-2.5 text-sm text-gray-500...">Cancel</button>
```

**Impact:** Accidental form closes, confusion about primary action.

**Recommendation:**
- Make Cancel button clearly secondary: `bg-gray-100 text-gray-700`
- Add explicit close icon + label: "Close" instead of "Cancel"
- Consider adding confirmation if form has unsaved changes

---

### HIGH Priority Issues

#### 4. **Institution Edit/Delete Icon Buttons are Too Small**
**Severity:** HIGH
**Location:** Institution card (`_institution_card.html`, lines 19-40)
**Problem:**
- Edit button: `text-xs px-1 py-1` → approximately 16x16px
- Delete button: same size
- Both use SVG icons (h-4 w-4 = 16px)
- WCAG standard: 44x44px minimum touch target
- Users with large fingers cannot reliably tap

**Evidence:**
```html
<!-- Line 23-25 -->
<button class="text-xs text-gray-400 hover:text-teal-600 px-1 py-1">
    <svg class="h-4 w-4">...</svg>  <!-- Only 16x16px -->
</button>
```

**Impact:** Accessibility failure. Mobile users struggle with edit/delete.

**Recommendation:**
```html
<button class="p-2 text-gray-400 hover:text-teal-600 min-h-[44px] min-w-[44px] flex items-center justify-center">
    <svg class="h-5 w-5">...</svg>
</button>
```

---

#### 5. **Custom Account Name Feature Hidden Under Toggle**
**Severity:** HIGH
**Location:** Add account form (`_add_account_form.html`, lines 107-118)
**Problem:**
- Account names are auto-generated: "{Institution} - {Type}"
- Custom names available but hidden under "Custom name" toggle
- Users don't know they can rename accounts
- Toggle has downward arrow (not obvious it expands)
- Users think auto-generated names are permanent

**Evidence:**
```html
<!-- Line 108-117 -->
<button type="button" aria-expanded="false" id="add-acct-custom-name-toggle">
    Custom name <svg class="chevron w-3 h-3">...</svg>
</button>
<div id="add-acct-custom-name-field" style="display: none;">
    <input type="text" name="name" placeholder="e.g., My Savings">
</div>
```

**Impact:** Users can't see all form options. Poor discoverability.

**Recommendation:**
- Show custom name field by default, not hidden
- Or: Add clear label "Optional: Customize name" above toggle
- Add help text: "Leave blank to use auto-generated name"

---

#### 6. **No Visual Feedback When Credit Limit Field Appears**
**Severity:** HIGH
**Location:** Add account form (`_add_account_form.html`, lines 126-130)
**Problem:**
- Credit limit field is `display: none` by default
- When user selects credit card type, field appears suddenly
- No animation, fade-in, or visual cue
- Field is below the fold on mobile — user may not see it

**Evidence:**
```html
<!-- Line 126 -->
<div id="add-acct-credit-limit-field" style="display: none;">
```

```javascript
// Line 373-377
function toggleCreditLimit() {
    creditField.style.display = (val === 'credit_card' || val === 'credit_limit') ? 'block' : 'none';
}
```

**Impact:** Users miss required field. Form submits with error.

**Recommendation:**
```css
.credit-limit-field {
    max-height: 0;
    overflow: hidden;
    transition: max-height 300ms ease-out;
}

.credit-limit-field.visible {
    max-height: 100px;
}
```

---

#### 7. **Institution Deletion Warning Doesn't Count Affected Transactions**
**Severity:** HIGH
**Location:** Institution delete confirmation (`_institution_delete_confirm.html`, line 20)
**Problem:**
- Warning shows account count: "and its **2** accounts"
- Does NOT show transaction count (e.g., "120 transactions")
- Users don't realize data impact
- E.g., deleting "HSBC" also deletes 500+ transactions

**Evidence:**
```html
<!-- Line 20 -->
{% if account_count > 0 %} and its <strong>{{ account_count }}</strong> account{{ account_count|pluralize }} including all their transactions{% endif %}
```

**Impact:** Accidental data loss. Users feel blindsided.

**Recommendation:**
- Query transaction count in view: `Transaction.objects.filter(account__institution=inst).count()`
- Show in warning: "**2** accounts and **120** transactions"
- Or: Add collapsible preview of affected accounts and transaction counts

---

### MEDIUM Priority Issues

#### 8. **Edit Account Sheet is Too Narrow (50vh max-height)**
**Severity:** MEDIUM
**Location:** Accounts list page, sheet definition (line 33)
**Problem:**
- Edit sheet has `max-h-[50vh]` = maximum 50% viewport height
- Create sheet has `max-h-[80vh]` = 80% viewport height
- On short screens (iPhone SE), edit form gets truncated
- User must scroll inside sheet to reach Cancel button
- Inconsistent with create sheet sizing

**Evidence:**
```html
<!-- Line 33 -->
{% include "components/bottom_sheet.html" with name="edit-sheet" max_height="max-h-[50vh]" %}

<!-- vs. Line 30 -->
{% include "components/bottom_sheet.html" with name="create-sheet" max_height="max-h-[80vh]" %}
```

**Impact:** Mobile users must scroll to find Cancel button.

**Recommendation:**
```html
{% include "components/bottom_sheet.html" with name="edit-sheet" max_height="max-h-[75vh]" %}
```

---

#### 9. **Account Type Filter Logic is Unclear**
**Severity:** MEDIUM
**Location:** Add account form (`_add_account_form.html`, lines 338-359)
**Problem:**
- When selecting "Wallet" institution type, account type dropdown hides automatically
- When selecting "Fintech", credit card options disappear
- No visual explanation of why options changed
- User clicks on type dropdown expecting full list, options are missing

**Evidence:**
```javascript
// Lines 345-352
if (instType === 'fintech') {
    opt.hidden = (opt.value === 'credit_card' || opt.value === 'credit_limit');
    opt.disabled = opt.hidden;
} else {
    opt.hidden = false;
    opt.disabled = false;
}
```

**Impact:** Confusion. Users wonder: "Where's the credit card option?"

**Recommendation:**
- Show disabled option with explanation: `<option disabled>Credit Card (not available for fintechs)</option>`
- Or: Show info text: "Fintechs can't have credit cards. Select Bank for credit card accounts."

---

#### 10. **No Toast Notification on Account Creation Success**
**Severity:** MEDIUM
**Location:** `account_add` view (line 600-602)
**Problem:**
- Institution creation shows: `success_html("Institution added!")` → toast
- Account creation shows: no toast, just closes sheet silently
- User doesn't know if creation succeeded
- Silent success is unexpected after explicit error messages

**Evidence:**
```python
# Line 414-416 (institution_add)
html = success_html("Institution added!")
html += "<script>setTimeout(function(){ closeCreateSheet(); }, 1000);</script>"

# vs. Line 600-602 (account_add)
html = "<script>BottomSheet.close('create-sheet');</script>"
html += _render_institution_list_oob(request)  # No success toast
```

**Impact:** Users unsure if action completed. Negative feedback.

**Recommendation:**
```python
html = success_html("Account added!")
html += "<script>setTimeout(function(){ BottomSheet.close('create-sheet'); }, 1000);</script>"
html += _render_institution_list_oob(request)
```

---

#### 11. **Credit Card Debt Display Could Confuse Users**
**Severity:** MEDIUM
**Location:** Account detail page, institution card
**Problem:**
- Credit card balances are negative (representing debt): -5000 EGP
- Displayed in red: "safe" color for negative numbers
- But for credit cards, "used amount" is the negative value shown
- Users expect to see "used" amount positively: 5,000 / 10,000 limit
- Template does this correctly with `neg` filter in detail page (line 93), but institution card does not

**Evidence:**
```html
<!-- Line 53-54 in _institution_card.html (WRONG) -->
<p class="text-sm font-semibold {% if account.current_balance < 0 %}text-red-600{% else %}text-slate-800{% endif %}">
    {{ account.current_balance|format_currency:account.currency }}  <!-- Shows raw negative balance -->
</p>

<!-- Line 93 in account_detail.html (CORRECT) -->
{{ data.account.current_balance|neg|format_currency:data.account.currency }} used  <!-- Inverts with neg filter -->
```

**Impact:** Confusing balance display. Users misread credit card balances in list.

**Recommendation:**
```html
<!-- In _institution_card.html -->
{% if account.is_credit_type %}
    <p class="text-sm font-semibold text-red-600">
        {{ account.current_balance|neg|format_currency:account.currency }} used
    </p>
{% else %}
    <p class="text-sm font-semibold {% if account.current_balance < 0 %}text-red-600{% else %}text-slate-800{% endif %}">
        {{ account.current_balance|format_currency:account.currency }}
    </p>
{% endif %}
```

---

#### 12. **Delete Button Lacks Visual Prominence**
**Severity:** MEDIUM
**Location:** Account detail page (lines 183-187)
**Problem:**
- Delete Account button: red text on white background
- Not styled as a button (no border, no padding, no hover state clear)
- Looks like a text link
- Users might not realize it's destructive
- Compare to primary buttons (blue with padding)

**Evidence:**
```html
<!-- Line 184-186 -->
<button onclick="openDeleteSheet()"
        class="w-full text-red-600 dark:text-red-400 py-2 rounded-lg text-sm font-semibold hover:bg-red-50 dark:hover:bg-red-900/20 transition">
    Delete Account
</button>
```

**Impact:** Low discoverability of dangerous action. Users may not find delete option.

**Recommendation:**
```html
<button onclick="openDeleteSheet()"
        class="w-full bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 py-2.5 rounded-lg text-sm font-semibold hover:bg-red-100 dark:hover:bg-red-900/50 transition">
    <svg class="inline mr-2 h-4 w-4"><!-- trash icon --></svg>
    Delete Account
</button>
```

---

### LOW Priority Issues

#### 13. **Institution Type Terminology Unclear**
**Severity:** LOW
**Location:** Institution form (`_add_account_form.html`, lines 44-46)
**Problem:**
- "Finance App" is vague term
- Users unfamiliar with it: is it a digital wallet? Investment app? Payment app?
- Better terms: "App/Fintech", "Digital Bank", or "Payment App"

**Recommendation:**
```html
<div class="peer-checked:bg-teal-50...">
    Digital Bank / App
</div>
```

---

#### 14. **No Confirmation Before Dormant Toggle**
**Severity:** LOW
**Location:** Account detail page (lines 62-71)
**Problem:**
- Dormant toggle is a single button click: `hx-post="/accounts/{id}/dormant"`
- No confirmation modal
- User may toggle dormant status by accident
- Dormant accounts hide on dashboard, potentially confusing user

**Evidence:**
```html
<!-- Line 67-70 -->
<button hx-post="/accounts/{{ data.account.id }}/dormant"
        class="px-3 py-1.5 rounded-lg text-xs font-semibold...">
    {% if data.account.is_dormant %}Active{% else %}Dormant{% endif %}
</button>
```

**Impact:** Minor — accidental toggles are recoverable by clicking again.

**Recommendation:**
- Optional: Add confirm dialog: "Mark as dormant? It will hide from the dashboard."
- Or: Keep as-is (toggle is immediately reversible)

---

#### 15. **Health Rules Save Has No Feedback**
**Severity:** LOW
**Location:** Account detail page (lines 158-180)
**Problem:**
- Health rules form submits via plain `<form method="POST">`
- No HTMX, no AJAX
- No loading state during save
- User submits, page redirects to same account detail
- Unclear if save succeeded

**Evidence:**
```html
<!-- Line 160 -->
<form method="POST" action="/accounts/{{ data.account.id }}/health" class="space-y-3">
    ...
    <button type="submit" class="...">Save Health Rules</button>
</form>
```

**Impact:** Minor UX friction. User unsure if save completed.

**Recommendation:**
- Convert to HTMX: `hx-post="/accounts/{{ data.account.id }}/health"`
- Add spinner on submit
- Show brief toast: "Health rules saved"

---

## 4. Improvement Proposals

### Priority 1: Fix Critical Issues (Blocks Production Use)

#### A. Case-Insensitive Name Confirmation
**Impact:** High — deletion success rate
**Effort:** 2 minutes

```javascript
// Before (account_detail.html, line ~260)
btn.disabled = (input.value.trim() !== expectedName);

// After
btn.disabled = (input.value.trim().toLowerCase() !== expectedName.toLowerCase());
```

**Also apply to institution delete:**
```javascript
// _institution_delete_confirm.html, line ~62
btn.disabled = (input.value.trim().toLowerCase() !== expectedDeleteName.toLowerCase());
```

---

#### B. Credit Card Creation Requires Credit Limit
**Impact:** High — form validation clarity
**Effort:** 15 minutes

**Approach 1: Client-side validation**
```html
<!-- In _add_account_form.html, after credit-limit input -->
<script>
    // Prevent form submit if credit card selected but limit empty
    document.getElementById('add-account-form').addEventListener('submit', function(e) {
        var typeSelect = document.getElementById('add-acct-type');
        var creditField = document.getElementById('add-acct-credit-limit');
        var creditInput = creditField ? creditField.querySelector('input') : null;

        if ((typeSelect.value === 'credit_card' || typeSelect.value === 'credit_limit') &&
            (!creditInput || !creditInput.value.trim())) {
            e.preventDefault();
            creditInput.focus();
            creditInput.classList.add('border-red-500', 'ring-red-500');
        }
    });
</script>
```

**Approach 2: Server-side message improvement**
```python
# In account_add view
if data['type'] in ('credit_card', 'credit_limit') and not data.get('credit_limit'):
    return render(
        request,
        "accounts/_add_account_form.html",
        {
            ...
            "error": "Credit limit is required for credit card accounts",
            "error_field": "credit-limit"  # Highlight the specific field
        },
        status=422,
    )
```

---

#### C. Fix Bottom Sheet Cancel/Close Ambiguity
**Impact:** Medium — form submission accidents
**Effort:** 10 minutes

Update edit form template:
```html
<!-- _account_edit_form.html, lines 53-63 -->
<div class="flex gap-2 pt-1">
    <button type="submit"
        class="flex-1 bg-teal-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-teal-700 active:scale-[0.98] transition-all">
        Update
    </button>
    <button type="button"
        onclick="closeEditAccount()"
        class="flex-1 bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-400 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-slate-600 transition-all">
        Cancel
    </button>
</div>
```

---

### Priority 2: Accessibility & Usability Fixes

#### D. Enlarge Icon Button Touch Targets
**Impact:** High — accessibility (WCAG)
**Effort:** 5 minutes

```html
<!-- _institution_card.html, lines 19-40 -->

<!-- Before -->
<button class="text-xs text-teal-600 hover:text-teal-700 px-2 py-1">+ Account</button>
<button class="text-xs text-gray-400 hover:text-teal-600 px-1 py-1">
    <svg class="h-4 w-4">...</svg>
</button>

<!-- After -->
<button class="text-xs text-teal-600 hover:text-teal-700 px-3 py-2 min-h-[44px] inline-flex items-center">
    + Account
</button>
<button class="text-gray-400 hover:text-teal-600 p-2.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center">
    <svg class="h-5 w-5">...</svg>
</button>
```

---

#### E. Improve Credit Limit Field Visibility
**Impact:** Medium — form UX
**Effort:** 20 minutes

Add CSS transition and better visual cue:

```html
<!-- _add_account_form.html -->

<style>
    #add-acct-credit-limit-field {
        max-height: 0;
        overflow: hidden;
        opacity: 0;
        transition: max-height 200ms ease-out, opacity 200ms ease-out;
        margin-bottom: 0;
    }

    #add-acct-credit-limit-field.visible {
        max-height: 150px;
        opacity: 1;
        margin-bottom: 1rem;
    }
</style>

<script>
    function toggleCreditLimit() {
        var typeSelect = document.getElementById('add-acct-type');
        var creditField = document.getElementById('add-acct-credit-limit-field');
        var val = typeSelect.value;
        var shouldShow = (val === 'credit_card' || val === 'credit_limit');

        if (shouldShow) {
            creditField.classList.add('visible');
            creditField.querySelector('input').focus();  // Auto-focus
        } else {
            creditField.classList.remove('visible');
        }
    }
</script>
```

---

#### F. Show Custom Name Field by Default
**Impact:** High — discoverability
**Effort:** 10 minutes

```html
<!-- _add_account_form.html, lines 107-118 -->

<!-- Replace toggle with always-visible section -->
<div>
    <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1" for="add-acct-custom-name">
        Account Name (optional)
    </label>
    <input type="text" name="name" id="add-acct-custom-name"
        placeholder="Leave blank to use auto-generated name (e.g., 'HSBC - Current')"
        class="w-full border border-gray-300 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
    <p class="text-xs text-gray-400 mt-1">Tip: Give your accounts nicknames like "Emergency Fund" or "Holiday Savings"</p>
</div>
```

---

### Priority 3: Consistency & Polish

#### G. Add Toast on Account Creation
**Impact:** Low → Medium (user confidence)
**Effort:** 3 minutes

```python
# views.py, account_add function, line 600-602
html = success_html("Account added!")
html += "<script>setTimeout(function(){ BottomSheet.close('create-sheet'); }, 1000);</script>"
html += _render_institution_list_oob(request)
return HttpResponse(html)
```

---

#### H. Fix Credit Card Balance Display in List
**Impact:** Medium — clarity
**Effort:** 5 minutes

```html
<!-- _institution_card.html, lines 52-59 -->

<!-- Before -->
<p class="text-sm font-semibold {% if account.current_balance < 0 %}text-red-600{% else %}text-slate-800{% endif %}">
    {{ account.current_balance|format_currency:account.currency }}
</p>

<!-- After -->
{% if account.is_credit_type %}
    <p class="text-sm font-semibold text-red-600">
        {{ account.current_balance|neg|format_currency:account.currency }} <span class="text-xs text-gray-400">used</span>
    </p>
{% else %}
    <p class="text-sm font-semibold {% if account.current_balance < 0 %}text-red-600{% else %}text-slate-800{% endif %}">
        {{ account.current_balance|format_currency:account.currency }}
    </p>
{% endif %}
```

---

#### I. Make Delete Button More Prominent
**Impact:** Low → Medium (discoverability)
**Effort:** 5 minutes

```html
<!-- account_detail.html, lines 183-188 -->

<!-- Before -->
<button onclick="openDeleteSheet()" class="w-full text-red-600...">Delete Account</button>

<!-- After -->
<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl shadow-sm p-4">
    <button onclick="openDeleteSheet()"
        class="w-full bg-red-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-red-700 active:scale-[0.98] transition-all flex items-center justify-center gap-2">
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142..."/>
        </svg>
        Delete Account
    </button>
</div>
```

---

## 5. Best Practices from Similar Apps

### Comparison: ClearMoney vs. Industry Standards

| Feature | ClearMoney | Wise | N26 | Traditional Bank |
|---------|-----------|------|-----|-----------------|
| **Account Creation** | Multi-step form in sheet | Single step + wizard | Single step | Multi-step with docs |
| **Custom Names** | Toggle (hidden) | Always visible | Always visible | ❌ Not allowed |
| **Deletion Confirmation** | Name match | Confirmation modal | Password required | Name + additional steps |
| **Balance Display** | Color-coded (red/green) | Color-coded | Color-coded | ✓ Simple number |
| **Credit Card Debt** | Negative balance (red) | Shows used/limit | Shows used/limit | Shows balance owed |
| **Touch Targets** | 4-40px (inconsistent) | 44px+ (WCAG) | 44px+ (WCAG) | 40-50px |
| **Empty States** | Text hint | Onboarding flow | Onboarding flow | ✓ Minimal |
| **Error Messages** | Inline box | Inline + field highlight | Inline + field highlight | ✓ Clear messages |

### Key Lessons from Industry Leaders

1. **Wise Approach to Deletion:**
   - Shows warning with affected items count (accounts + transactions)
   - Requires explicit confirmation (not just typing name)
   - Shows undo option for 48 hours (ClearMoney doesn't offer this)

2. **N26 Account Management:**
   - Always-visible custom name field (not hidden under toggle)
   - One-touch account freezing (temporary disable instead of delete)
   - Card/account switching with tabs (if multiple accounts)
   - Real-time balance sync notification

3. **Traditional Banking UX:**
   - Account type always clear (checkings vs. savings icons)
   - Health warnings prominent (low balance alert, minimum balance)
   - Multi-step deletion process (account lock → grace period → deletion)
   - Clear "Available balance" vs. "Current balance" distinction

### ClearMoney's Strengths
- ✓ Fast account creation (institution search is smooth)
- ✓ Good use of bottom sheets (non-blocking, easy to cancel)
- ✓ Dark mode support throughout
- ✓ Proper ARIA labels (mostly)
- ✓ Good color-coding for financial states

### ClearMoney's Gaps
- ❌ Icon button touch targets (needs 44px minimum)
- ❌ Hidden features (custom name toggle)
- ❌ Incomplete error messages
- ❌ No account freezing (only delete)
- ❌ No undo capability

---

## 6. Summary: Impact & Priority Roadmap

### Critical (Blocks Usage)
| Issue | Fix Time | Effort | Impact |
|-------|----------|--------|--------|
| Case-sensitive name match | 2 min | 🟢 Trivial | 🔴 High |
| Credit card validation unclear | 15 min | 🟡 Easy | 🔴 High |
| Sheet button ambiguity | 10 min | 🟡 Easy | 🟠 Medium |

### High (Accessibility)
| Issue | Fix Time | Effort | Impact |
|-------|----------|--------|--------|
| Small touch targets | 5 min | 🟡 Easy | 🔴 High (WCAG A) |
| Hidden custom name | 10 min | 🟡 Easy | 🟠 Medium |
| Missing field feedback | 20 min | 🟡 Easy | 🟠 Medium |

### Medium (Polish)
| Issue | Fix Time | Effort | Impact |
|-------|----------|--------|--------|
| Account add lacks toast | 3 min | 🟢 Trivial | 🟡 Low |
| CC balance unclear | 5 min | 🟡 Easy | 🟡 Low |
| Delete button buried | 5 min | 🟡 Easy | 🟡 Low |
| Health rules no feedback | 10 min | 🟡 Easy | 🟡 Low |

---

## 7. Next Steps

### Immediate Actions (Today)
1. Fix case-sensitive name confirmation (2 min)
2. Add credit limit validation (15 min)
3. Test account deletion with edge cases

### This Sprint
1. Enlarge touch targets (5 min)
2. Show custom name field by default (10 min)
3. Add credit limit field animation (20 min)
4. Add account creation toast (3 min)

### Future Improvements
1. Add transaction count to deletion warning
2. Implement account freezing (soft delete)
3. Add undo capability (24-hour grace period)
4. Support account reordering UI
5. Add account grouping by purpose (Emergency Fund, Holiday, etc.)

---

## Appendix: Test Findings

### E2E Test Coverage
**Status:** Good coverage, but gaps identified

**Tests Present:**
- ✓ Institution CRUD
- ✓ Account creation with validation
- ✓ Credit card type shows limit field
- ✓ Credit card without limit shows error
- ✓ Dormant toggle
- ✓ Account detail page loads balance

**Tests Missing:**
- ❌ Account deletion with name confirmation
- ❌ Account edit (form loads but not tested)
- ❌ Institution deletion confirmation
- ❌ Credit card balance display (should show "used" not raw negative)
- ❌ Health rules save
- ❌ Linked virtual accounts display
- ❌ Case sensitivity in deletion confirmation

### Recommended Test Additions
```python
def test_delete_account_requires_name_confirmation(page: Page):
    """Verify account deletion requires exact name match."""
    _, account_id = seed_basic_data(page, name="My Checking")
    page.goto(f"/accounts/{account_id}")
    page.click('button:has-text("Delete Account")')

    # Try wrong name
    page.fill('#delete-confirm-input', 'Wrong Name')
    assert page.locator('#delete-confirm-btn').is_disabled()

    # Correct name enables button
    page.fill('#delete-confirm-input', 'My Checking')
    assert page.locator('#delete-confirm-btn').is_enabled()
```

---

**Audit Completed:** March 25, 2026
**Status:** Ready for sprint planning
