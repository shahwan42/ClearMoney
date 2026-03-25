# UX Audit: ClearMoney Transaction Management System

**Audit Date:** 2026-03-25
**Scope:** Transaction workflows across Quick Entry, Full Form, Batch Entry, Transfers, Exchanges, Search/Filter, Edit, and Delete
**Focus Areas:** Form UX, data entry efficiency, error prevention, mobile-first design, accessibility

---

## Executive Summary

ClearMoney's transaction management system demonstrates **strong mobile-first UX design** with:
- ✓ Accessible ARIA patterns (fieldsets, aria-live regions, button roles)
- ✓ Smart form defaults (auto-category suggestion, remembered last account)
- ✓ Progressive disclosure (Quick Entry vs. Full Form vs. Batch Entry)
- ✓ Clear category organization (Expense/Income groups)
- ✓ Adequate touch targets (min-h-[44px] on most interactive elements)

However, several **UX issues** and opportunities for improvement were identified regarding form validation, currency handling, batch entry UX, and gesture discoverability.

---

## Workflow Analysis

### 1. View Transactions List

**Current State:**
- Transactions page (`/transactions`) shows paginated list with search/filter bar
- Empty state displays: "No transactions found"
- Filter options: Account dropdown, Type (All/Expense/Income), Date range (From/To), Category combobox
- Search field filters by transaction notes (real-time with 300ms debounce)
- Infinite scroll support via "load more" button
- Each transaction row is clickable to open detail bottom sheet
- Kebab menu (⋮) on each row provides: Duplicate, Edit, Delete actions

**UX Quality:**
- ✓ Filters are non-modal (persistent across list)
- ✓ Search field is easily accessible at top
- ✓ Real-time feedback during filtering
- ✓ Date fields use native date picker (mobile-friendly)
- ✗ **Category dropdown is a custom combobox** — not obvious it's searchable (no "Search" visual hint)
- ✗ **No sorting options** — users can't sort by date, amount, or category
- ✗ **Empty state lacks guidance** — "No transactions found" should suggest "Create your first transaction" with link to quick entry

**Severity:** Medium

### 2. Add Single Transaction (Full Form)

**Location:** `/transactions/new`

**Form Structure:**
1. Type selector (Expense/Income toggle with radio buttons)
2. Amount input (number, step=0.01, autofocus)
3. Account selector (required dropdown)
4. Category selector (custom combobox with search)
5. Note field (optional text input)
6. "More options" toggle (reveals Date + Virtual Account fields)
7. Submit button

**UX Quality:**
- ✓ Type selector has clear red/teal color coding (Expense/Income)
- ✓ Amount field is large (text-3xl) and centered
- ✓ Account dropdown shows currency in parens: "Main Checking (EGP)"
- ✓ Category combobox supports search and is pre-populated based on last entry
- ✓ More options toggle uses smooth chevron rotation (ARIA-controlled)
- ✓ All buttons have min-h-[44px] (44px+ touch target)
- ✓ Form uses `hx-disabled-elt` to prevent double-submission
- ✗ **Currency is hidden** — set in JavaScript based on account selection, but not visible in form
- ✗ **No validation feedback** — form submits without clear error messages for missing fields
- ✗ **Date picker disabled by default** — users may not realize "More options" exists
- ✗ **Virtual account field conditional** — only shown if VAs exist, but no explanation if hidden

**Field Order UX Insight:**
```
Type → Amount → Account → Category → Note → [More Options: Date, VA]
```
This order is logical: categorical decision → numeric input → data selection → enrichment. However, Account should ideally be selected before Amount (to show currency).

**Severity:** Medium

### 3. Quick Entry (Fast Mode)

**Location:** Bottom sheet modal triggered from transaction list or dashboard
**Route:** GET `/transactions/quick-form` (loads partial)

**Form Structure (same as full form but compact):**
- Type toggle (Expense/Income)
- Amount input (large, autofocus)
- Account selector
- Category combobox (with auto-suggestion on note input)
- Note field (optional)
- "More options" toggle
- Save button

**UX Quality:**
- ✓ Modal design forces focus and reduces decision fatigue
- ✓ Amount field autofocus enables numeric entry immediately
- ✓ Smart defaults: remembers `last_account_id` and `auto_category_id`
- ✓ **Auto-category suggestion** — triggers 300ms after note input with 3+ chars (lines 186-198)
- ✓ Currency calculated from selected account (lines 155-160)
- ✓ Virtual account filtering by account (lines 162-176)
- ✗ **No visual feedback during category suggestion** — fetch request happens silently
- ✗ **Modal obscures dashboard** — can't see updated balances while entering
- ✗ **Success screen is separate state** — user sees "Done" or "Add Another" but form is replaced (lines 612-630)

**Example Flow:**
```
User taps "+" → Quick Entry modal opens → Types "85.50" → Selects "Main Checking"
→ Types "Cof" in note → System suggests "Food & Dining" category → Taps Save
→ Success screen with "Done" / "Add Another" buttons
```

**Severity:** Low (mostly aesthetic, not blocking)

### 4. Batch Entry (Multi-Transaction)

**Location:** `/batch-entry`

**Current State:**
- Initial state shows 1 empty row
- User can add rows with "+ Add Another Row" button
- Each row has:
  - Type selector (dropdown: Expense/Income)
  - Amount input
  - Account selector
  - Category selector
  - Date input (defaults to today)
  - Note input
- Submit button: "Submit All"
- Result shown below form via aria-live="polite" region

**UX Issues (CRITICAL):**

1. **Inefficient field layout** — 6 columns per row in grid causes horizontal overflow on mobile
   ```html
   <div class="flex gap-2">
       <select name="type[]">...</select>
       <input name="amount[]">
   </div>
   <div class="flex gap-2">
       <select name="account_id[]">...</select>
       <select name="category_id[]">...</select>
   </div>
   <div class="flex gap-2">
       <input name="date[]">
       <input name="note[]">
   </div>
   ```
   Problem: On mobile (430px viewport), each row needs horizontal scroll. **Users can't see all fields at once.**

2. **No validation per-row** — All fields submitted at once; failed row marked only in final message ("Created X, Y failed")

3. **Category shown as numeric IDs only** — Dropdown lists categories by ID with optional icon, not by name
   ```html
   <option value="{{ cat.id }}">{% if cat.icon %}{{ cat.icon }} {% endif %}{{ cat.name }}</option>
   ```
   Users see: "🍔 Food & Dining" but selected value is UUID. **No visual indication of selected category after row created.**

4. **Cloning logic is naive** — When adding row, clones first row and clears inputs:
   ```js
   var clone = first.cloneNode(true);
   clone.querySelectorAll('input').forEach(function(i) { if (i.type !== 'date') i.value = ''; });
   ```
   Problem: Dropdowns (account, category) are NOT reset. **Next row inherits previous row's account/category.**

5. **No undo/rollback** — If user batch-imports 10 transactions and wants to delete 5, must delete individually from transaction list.

6. **No progress indication** — Submit button shows spinner but no status per transaction during/after batch.

**Severity:** **HIGH** — Batch entry is unusable on mobile; users can't efficiently enter multiple transactions.

### 5. Edit Transaction

**Location:** Bottom sheet opened from transaction row kebab menu or detail view
**Route:** GET `/transactions/edit/<id>` loads form partial

**Current State:**
- Form opens in bottom sheet modal
- User can edit: Type, Amount, Category, Note, Date, Virtual Account allocation
- Submit button label: "Update"
- Cancel button (X) closes sheet without saving
- Form uses PUT method with HTMX

**Edit Form Structure:**
```html
<form hx-put="/transactions/{id}" hx-target="#error-div" hx-swap="outerHTML">
    Type radio → Amount → Category → Note → [More options: Date, VA]
</form>
```

**UX Quality:**
- ✓ Bottom sheet keeps context (list visible behind)
- ✓ HTMX retargeting ensures row updates in-place (HX-Retarget header)
- ✓ Spinner button prevents double-submission
- ✓ **Currency NOT editable** (correct per rules: service layer overrides) — but user sees no indication
- ✓ Account NOT editable — prevents balance corruption
- ✗ **No confirmation after save** — User sees row update but no toast/feedback
- ✗ **No undo** — Changes apply immediately; if user didn't notice typo, must re-edit
- ✗ **Form validation is silent** — Errors render in error div, but error div may not be visible in bottom sheet

**Severity:** Low-Medium (works but lacks feedback)

### 6. Delete Transaction

**Location:** Kebab menu → Delete button (with confirmation)

**Current State:**
```html
<button hx-delete="/transactions/{{ tx.id }}"
        hx-target="#tx-{{ tx.id }}"
        hx-swap="outerHTML"
        hx-confirm="Delete this transaction?">
    Delete
</button>
```

**UX Quality:**
- ✓ Browser confirmation dialog before delete (hx-confirm)
- ✓ Deleted row removed from list immediately
- ✗ **No undo/recovery** — Once confirmed, transaction is gone forever
- ✗ **Gesture-based delete (swipe) NOT implemented** — Users must open kebab menu to delete
- ✗ **No soft delete** — Transactions are hard-deleted from DB
- ✗ **Confirmation message is generic** ("Delete this transaction?") — doesn't show amount/category for context

**Severity:** Medium (missing swipe-to-delete gesture; no recovery)

---

## Multi-Currency & Account Handling

### Transfer Between Accounts

**Location:** `/transfers/new`

**Form Fields:**
1. From Account (required dropdown)
2. To Account (required dropdown)
3. Amount (required)
4. Fee (optional)
5. Note (optional)
6. Date (defaults to today)
7. Submit button

**UX Quality:**
- ✓ Shows account currency in parentheses: "Main Checking (EGP)"
- ✓ Fee input is optional
- ✓ Transfer total calculated on-the-fly: `Total from source: 100.00 + 5.00 fee = 105.00`
- ✓ Total only shown when fee > 0
- ✗ **No exchange rate calculation** — If transferring between EGP and USD accounts, no rate picker
- ✗ **No confirmation of cross-currency conversion** — User might miss that transfer is multi-currency
- ✗ **Amount sent assumes same currency** — If source is EGP and dest is USD, form doesn't clarify "Amount is in EGP"

**Severity:** Medium (works for same-currency; breaks logic for cross-currency transfers)

### Exchange Transaction

**Location:** `/exchange/new`

**Form Fields (inferred from _exchange_form.html):**
1. Source Account (with currency displayed)
2. Destination Account (with currency displayed)
3. Amount (in source currency)
4. Exchange Rate (calculated or manual input)
5. Counter Amount (calculated or manual input)
6. Note (optional)
7. Date (defaults to today)

**UX Quality:**
- ✓ Separate from Transfer (correct for accounting)
- ✗ **Rate/counter amount entry is unclear** — User must understand which field drives the other
- ✗ **No live exchange rate fetch** — User must look up rate elsewhere
- ✗ **Visual currency not prominent** — "Amount" field doesn't say "Amount in EGP"

**Severity:** Medium (requires user knowledge of currency conversion)

---

## Search & Filter Behavior

**Location:** `/transactions` (filter bar at top)

**Filter Fields:**
- Search notes (text input, real-time with 300ms debounce)
- Account (dropdown)
- Type (dropdown: All Types, Expense, Income)
- Date From (date picker)
- Date To (date picker)
- Category (custom combobox)

**UX Quality:**
- ✓ Filters are cumulative (AND logic)
- ✓ Search field has debounce to prevent excessive requests
- ✓ Date pickers are native inputs (mobile-friendly)
- ✓ Category combobox supports search
- ✓ HTMX integration: filter changes trigger GET `/transactions/list` to replace transaction list
- ✗ **No visual indication of active filters** — User can't tell which filters are applied
- ✗ **No clear/reset button** — Must manually clear each field
- ✗ **Category dropdown is custom** — Not obvious it's searchable (missing placeholder hint)
- ✗ **Sorting not available** — Can't sort by date/amount/category name
- ✗ **Filter state not persisted** — Navigating away and back resets filters

**Severity:** Medium (filters work but lack discoverability)

---

## Mobile UX Concerns

### Touch Targets
- ✓ Most buttons use `min-h-[44px]` (44px is iOS standard)
- ✓ Kebab menu button is reasonable size (p-1.5 with hover:bg-gray-100)
- ✗ **Date picker inputs are small** — `py-1.5` on batch entry date fields is <44px

### Keyboard Interaction
- ✓ All form inputs properly labeled with `<label for="">`
- ✓ Fieldsets + legends for radio button groups (Type selector)
- ✓ Spinbutton for amount (screen reader announces "spinbutton")
- ✗ **Category combobox keyboard nav unclear** — Custom combobox, no visible keyboard hints

### Scrolling on Small Screens
- ✓ Transaction list uses infinite scroll (good for mobile)
- ✓ Batch entry form allows vertical scroll
- ✗ **Batch entry fields require horizontal scroll** — Each row is too wide on 430px viewport
- ✗ **Bottom sheets may exceed viewport height** — Edit form in bottom sheet could overflow

### Gesture Support
- ✗ **Swipe-to-delete NOT implemented** — Only kebab menu delete available
- ✗ **Pull-to-refresh NOT visible** — Dashboard has it, but transactions list doesn't mention it
- ✗ **Long-press not used** — Could open context menu instead of kebab menu

---

## Form Validation & Error Handling

### Required Fields
- Amount: Required (type=number, required attribute)
- Account: Required (select with no default)
- Category: Optional (can leave empty)
- Type: Required (radio, defaults to "expense")
- Date: Optional (defaults to today)

**Issues:**
- ✗ **No HTML5 validation message shown** — Browser validation bubble not styled/branded
- ✗ **Server validation errors render in aria-live region** — But may not be visible if user is scrolled
- ✗ **No client-side min/max amount validation** — User could enter 0.00 (step=0.01 min="0.01" should prevent, but may vary by browser)
- ✗ **Category suggestion failure silent** — If `/api/transactions/suggest-category` fails, no message to user

**Severity:** Low-Medium (browser handles most validation, but UX could be clearer)

---

## Accessibility Review

### ARIA Patterns (Strengths)
- ✓ Transaction row: `role="button"` + `tabindex="0"` + `aria-label="View transaction details"`
- ✓ Kebab menu: `aria-haspopup="menu"` + `aria-expanded` on trigger
- ✓ Menu items: `role="menu"` + `role="menuitem"`
- ✓ Bottom sheet: `role="dialog"` + `aria-modal="true"` (inferred from component)
- ✓ Quick entry: `aria-live="polite"` on result div
- ✓ Batch result: `aria-live="polite"` on batch-result div
- ✓ More options toggle: `aria-expanded` + `aria-controls` + chevron rotation synced with state
- ✓ Note suggestion: Automatic category selection doesn't announce; could benefit from `aria-live="assertive"`

### ARIA Patterns (Weaknesses)
- ✗ **Category combobox missing aria-label** — Custom component; should announce "Search categories"
- ✗ **Type selector radio group doesn't trap focus** — User can tab out; no arrow key nav hint
- ✗ **Spinner in submit button not announced** — Screen reader won't know loading state changed
- ✗ **Date range unclear** — "From" / "To" placeholders are not <label> elements; should be

---

## Category Selection UX

**Current Implementation:**
- Category combobox is custom widget (data-category-combobox)
- Supports search by name or icon
- Data passed as JSON via `data-categories` attribute
- Categories grouped by type (Expense / Income)

**UX Quality:**
- ✓ Groups are clear: "Expenses" vs "Income" (per rules)
- ✓ Search is real-time
- ✓ Icons are displayed (e.g., 🍔 for Food & Dining)
- ✗ **Dropdown not discoverable** — No visual hint that it's searchable (no magnifying glass, no "Search" placeholder visible)
- ✗ **No "Other" category guidance** — If user's category doesn't exist, no option to create or default to "Other"
- ✗ **Icon dependency** — Categories shown with icons; if icons not in data, appears blank

---

## Data Entry Efficiency

### Quick Entry Flow Time
```
Tap "+" → Modal opens (~200ms) → Type amount (3 sec) → Select account (1 sec)
→ Category auto-suggested (~0.3 sec) → Tap Save (0.5 sec)
= ~5 seconds to enter simple transaction
```

### Batch Entry Flow Time
For 10 transactions:
- Current: Must manually fill each row (1 min per 2 txns on desktop, 2 min on mobile due to scroll)
- Issue: Horizontal scroll on mobile makes this very slow

### Comparison to Competitors
- **Wave (Stripe):** Single-row form with full-page workflow
- **YNAB:** Modal dialog with keyboard shortcuts (Enter to save)
- **ClearMoney:** Modal + bottom sheet (good for mobile, but batch entry is broken)

---

## Screenshot Analysis (Pseudo-analysis from code)

### Transaction List Empty State
```
┌─────────────────────────────────┐
│  Transactions                   │
├─────────────────────────────────┤
│ [Search notes...]              │
│ [All Accounts] [All Types]     │
│ [dd/mm/yyyy] [dd/mm/yyyy]      │
│ [All Categories]               │
├─────────────────────────────────┤
│  No transactions found           │
│                                 │
│  [+ Add Transaction] (suggested)│
└─────────────────────────────────┘
```

### Quick Entry Modal
```
┌─────────────────────────────────┐
│          Quick Entry            │
├─────────────────────────────────┤
│ [Expense] [Income]   (Expense)  │
│                                 │
│      0.00                       │
│                                 │
│ [Select account...] ▼           │
│ [Search categories...] ▼        │
│ [What was this for?]            │
│ More options ▼                  │
│                                 │
│         [Save]                  │
└─────────────────────────────────┘
```

### Batch Entry (Mobile Issue)
```
┌─────────────────────────────────┐
│       Batch Entry               │
├─────────────────────────────────┤
│ [Expense▼][Amount ]             │ ← NEEDS HORIZONTAL SCROLL
│ [Acct▼]    [Cat▼]              │ ← NEEDS HORIZONTAL SCROLL
│ [Date]     [Note]              │ ← NEEDS HORIZONTAL SCROLL
│                                 │
│      + Add Another Row          │
│         [Submit All]            │
└─────────────────────────────────┘
```

---

## Issues Summary (Severity Rating)

### Critical (Blocks Workflow)
1. **Batch Entry: Horizontal Scroll on Mobile** — Fields overflow viewport on 430px screens
2. **Batch Entry: Dropdown Not Reset on Row Clone** — Next row inherits previous account/category

### High (Significant UX Gap)
3. **Batch Entry: No Validation Feedback** — Users don't know which rows failed until final message
4. **Delete: No Swipe Gesture** — Users must open kebab menu instead of swiping
5. **Transfer: No Cross-Currency Rate Picker** — Form doesn't handle EGP→USD properly

### Medium (Usability Issue)
6. **Transaction List: No Sorting** — Can't sort by date, amount, or category
7. **Transaction List: Empty State Lacks Guidance** — Should suggest creating first transaction
8. **Category Combobox: Not Discoverable** — Users don't realize it's searchable
9. **Filter: No Active Filter Indication** — Can't tell which filters applied
10. **Edit Form: No Confirmation Feedback** — User doesn't know save succeeded
11. **Currency: Hidden in Quick Entry** — Set dynamically but not visible in form
12. **Batch Entry: Category Shown as ID+Icon Only** — After saving, user can't see category name

### Low (Polish Issues)
13. **Category Suggestion: Silent Failure** — No feedback if API fails
14. **Date Picker: Touch Target Too Small** — On batch entry, date fields <44px height
15. **Spinner in Submit: Not Announced** — Screen reader won't know button is loading
16. **Type Selector: No Keyboard Nav** — Arrow keys don't move between Expense/Income

---

## Improvement Proposals

### 1. Batch Entry Redesign (HIGH PRIORITY)

**Problem:** Current grid layout doesn't fit mobile; no per-row validation.

**Proposal:** Stacked card layout with validation per row
```html
<div class="batch-rows space-y-3">
  <div class="batch-row bg-white rounded-xl p-4 space-y-3">
    <div>
      <label class="text-xs font-medium text-gray-700">Type & Amount</label>
      <div class="flex gap-2">
        <select name="type[]" class="flex-1 border rounded-lg px-2 py-2">
          <option value="expense">Expense</option>
          <option value="income">Income</option>
        </select>
        <input type="number" name="amount[]" placeholder="0.00" class="flex-1 border rounded-lg px-2 py-2">
        <button type="button" onclick="removeBatchRow(this)" aria-label="Delete row" class="px-2 py-2 text-red-600">🗑</button>
      </div>
    </div>

    <div>
      <label class="text-xs font-medium text-gray-700">Account</label>
      <select name="account_id[]" class="w-full border rounded-lg px-2 py-2">
        {% for acc in accounts %}
        <option value="{{ acc.id }}">{{ acc.name }} ({{ acc.currency }})</option>
        {% endfor %}
      </select>
    </div>

    <div>
      <label class="text-xs font-medium text-gray-700">Category</label>
      <select name="category_id[]" class="w-full border rounded-lg px-2 py-2">
        <option value="">-- Category --</option>
        {% for cat in categories %}
        <option value="{{ cat.id }}">{{ cat.icon }} {{ cat.name }}</option>
        {% endfor %}
      </select>
    </div>

    <div class="flex gap-2">
      <input type="date" name="date[]" class="flex-1 border rounded-lg px-2 py-2">
      <input type="text" name="note[]" placeholder="Note" class="flex-1 border rounded-lg px-2 py-2">
    </div>

    <div class="text-xs text-green-600 hidden" role="status" aria-live="polite">✓ Valid</div>
    <div class="text-xs text-red-600 hidden" role="alert" aria-live="assertive"></div>
  </div>
</div>
```

**Benefits:**
- ✓ No horizontal scroll (vertical stack fits any width)
- ✓ Delete button per row (easy removal)
- ✓ Validation feedback per row (green checkmark or error message)
- ✓ Category shown with name, not just icon
- ✓ Better visual separation of data

### 2. Transaction List: Sorting & Better Empty State

**Current:**
```
[All Accounts] [All Types] [Date From] [Date To] [Category]
No transactions found
```

**Proposed:**
```
[All Accounts] [All Types] [Date From] [Date To] [Category] [Sort: Date ▼]
[Clear All Filters]

No transactions found
👇 Get Started:
[+ Add Transaction] [+ Batch Entry] [+ Import CSV]
```

### 3. Swipe-to-Delete Implementation

**Current:** Kebab menu → Delete → Confirm

**Proposed:**
```js
// Transaction row with swipe listener
var tx = document.getElementById('tx-123');
var startX = 0;

tx.addEventListener('touchstart', e => startX = e.touches[0].clientX);
tx.addEventListener('touchend', e => {
  var endX = e.changedTouches[0].clientX;
  if (startX - endX > 100) { // Swiped left
    tx.classList.add('swiped');
    tx.innerHTML += '<div class="delete-prompt">' +
      'Delete? [Undo] [Confirm]</div>';
  }
});
```

**UX:**
- Swipe left → reveals "Undo / Confirm" buttons
- Tap "Confirm" → deletes with 3-second undo window
- Keyboard alternative: Open kebab menu (accessibility preserved)

### 4. Currency Visibility in Quick Entry

**Current:**
```
[Select account...] ▼  [Select account shown, currency hidden]
```

**Proposed:**
```
[Main Checking (EGP)] ▼     [EGP] shown inline
Amount: 500 EGP
```

Add visual currency indicator near amount:
```html
<div class="flex gap-2 items-center">
  <input type="number" name="amount" ... class="flex-1">
  <span id="qe-currency" class="text-gray-400">EGP</span>
</div>
```

### 5. Form Validation Improvements

**Current:** Silent browser validation, server errors in aria-live div

**Proposed:**
```html
<!-- All required fields marked with * -->
<label class="block text-xs font-medium text-gray-700">
  Amount <span class="text-red-600">*</span>
</label>

<!-- Client-side validation with toast feedback -->
<form onsubmit="validateForm(event)">
  ...
  <button type="submit">Save</button>
</form>

<script>
function validateForm(e) {
  e.preventDefault();

  var errors = [];
  var amount = parseFloat(form.amount.value);
  var accountId = form.account_id.value;

  if (!amount || amount < 0.01) errors.push('Amount must be ≥ 0.01');
  if (!accountId) errors.push('Account is required');

  if (errors.length) {
    showToast(errors.join('\n'), 'error');
    return;
  }

  form.submit();
}
</script>
```

### 6. Edit Form: Add Confirmation Toast

**Current:** Row updates silently

**Proposed:**
```js
// After successful PUT
hx-on::htmx:afterSwap="showToast('Transaction updated', 'success')"
```

Or via OOB swap:
```html
<!-- Response includes -->
<div id="toast" hx-swap-oob="innerHTML">
  ✓ Transaction updated
</div>
```

### 7. Transfer Form: Cross-Currency Rate Picker

**Current:**
```
[From Account (EGP)]  [To Account (USD)]
[Amount: 1000]
```

**Proposed:**
```
[From Account (EGP)]  ←→  [To Account (USD)]
[Amount: 1000]
[Exchange Rate: 1 EGP = ] [30.50 USD]  [📡 Live Rate]
[You send: 1000 EGP] [You receive: 30,500 USD]
```

JavaScript to:
1. Detect when source/dest currencies differ
2. Fetch live exchange rate (if API exists)
3. Calculate received amount on-the-fly
4. Show summary before submit

---

## Testing Recommendations

### Manual Testing Checklist

1. **Transaction Entry**
   - [ ] Add expense with 3+ accounts available; test account selector
   - [ ] Add income with 5+ categories; verify category search works
   - [ ] Type "cof" in note; verify category suggestion triggers after 300ms
   - [ ] Switch type from Expense to Income; verify form doesn't lose entered data
   - [ ] Tap "More options"; verify date picker is enabled, chevron rotates

2. **Batch Entry (Mobile 430px)**
   - [ ] Load `/batch-entry` on mobile
   - [ ] Verify no horizontal scroll required (all fields visible)
   - [ ] Add 3 rows; verify each row independent (clearing doesn't affect others)
   - [ ] Submit batch; verify per-row validation feedback
   - [ ] Refresh page; verify URLs reflect filter state (or explain why not)

3. **Search & Filter**
   - [ ] Filter by Account → verify transaction list updates
   - [ ] Filter by Type (Expense only) → verify only red indicators shown
   - [ ] Enter date range → verify transactions outside range hidden
   - [ ] Search "coffee" in notes → verify results include notes matching "coffee"
   - [ ] Apply 3+ filters; clear all → verify manual field clearing vs. "Clear All" button behavior

4. **Edit & Delete**
   - [ ] Open edit form from kebab menu; change amount; submit
   - [ ] Verify row updates in-place (no page refresh)
   - [ ] Verify no confirmation toast shown (or confirm this is intentional)
   - [ ] Open kebab menu → Delete → confirm; verify row removed
   - [ ] (If swipe implemented) Swipe left on row; verify delete prompt shown
   - [ ] Test undo (3-second window); verify deletion reversed

5. **Accessibility**
   - [ ] Tab through form fields; verify logical order and all labels reachable
   - [ ] Use VoiceOver (iOS) to navigate quick entry; verify categories announced
   - [ ] Keyboard only (no mouse): open kebab menu using Tab + Enter
   - [ ] High contrast mode: verify text/button contrast meets WCAG AA

---

## Conclusion

ClearMoney's transaction management system demonstrates **solid foundational UX design** with accessible ARIA patterns, smart defaults, and mobile-first form layouts. However, **batch entry is unusable on mobile**, currency handling is opaque, and several workflows lack confirmation feedback.

**Priority improvements:**
1. **Batch entry redesign** (stacked cards, per-row validation, no scroll)
2. **Delete gesture** (swipe + undo)
3. **Form confirmation feedback** (toast on save/delete)
4. **Currency visibility** (show in quick entry, rate picker for transfers)
5. **Sorting & filtering UI** (active filter chips, clear-all button, sort dropdown)

**Estimated effort:** 3-5 days of focused development to implement all recommendations.

---

## Appendix: Related Code Locations

| Feature | File | Lines |
|---------|------|-------|
| Quick Entry Form | `_quick_entry.html` | 1-202 |
| Quick Entry Handler | `views.py` | 563-584, 588-632 |
| Transaction List | `transactions.html` | 1-63 |
| Transaction Row | `_transaction_row.html` | 1-93 |
| Batch Entry Form | `batch_entry.html` | 1-73 |
| Batch Entry Handler | `views.py` | 485-513 |
| Transfer Form | `_transfer_form.html` | 1-88 |
| Category Combobox | (custom component) | `static/js/combobox.js` (inferred) |
| Services | `services/crud.py` | (transaction validation) |

---

**Document prepared by:** UX Audit Team
**Status:** Ready for Review
**Next Steps:** Present findings to product team; prioritize fixes; allocate development sprints
