# ClearMoney React Native — UI/UX Flows & Screens

Complete specification of screens, layouts, interactions, mobile patterns, and accessibility requirements.

---

## 1. Authentication Screens

### Login/Registration Screen
**Single unified entry point**

**Components:**
- Email input field
- "Sign In" button
- OR divider
- Sign up link (on desktop)
- Loading state during submission

**States:**
- **Empty:** Placeholder "you@example.com"
- **Focused:** Highlight with teal ring, clear any previous error
- **Validation Error:** Red border + error message below
- **Loading:** Button shows spinner, input disabled
- **Success:** Navigate to "Check Email" screen

**Accessibility:**
- `<label for="email">Email</label>`
- Error uses `role="alert"`
- Button min 48px tall

---

### Check Email Screen
**After successful login request**

**Message:**
```
We sent a sign-in link to:
[email]
✓ Check your email and click the link to continue
```

**Actions:**
- "Open Email App" (deep link to mail app)
- "Didn't receive a link?" → trigger resend
- "Change Email" → back to login

**Resend Behavior:**
- Rate limit: 5-minute cooldown, 3/day per email
- Show countdown timer if cooling down
- Show "Link already sent" if unexpired token exists

---

### Verification Screen
**While processing email link**

**States:**
- **Loading:** "Verifying your email..." + spinner
- **Success:** Auto-navigate to Home, show welcome animation if new user
- **Error:** "Link is invalid or expired" + resend option
- **Error (Already Used):** "Link already used" + resend option

---

## 2. Dashboard Screen

### Layout (Top to Bottom)
1. **Header:** User initials avatar, Settings gear
2. **Net Worth Card:**
   - Large bold number (e.g., "₩ 85,500")
   - Subtitle: "Your net worth"
   - Sparkline (30-day history)
   - Breakdown tooltip: "₩ 75,000 EGP, 10,500 USD"
3. **Quick Stats:**
   - Month-over-month spending ↑/↓
   - Income vs Expenses (side-by-side)
   - Velocity (daily avg spending)
4. **Credit Cards Summary:**
   - Total utilization donut chart
   - Individual card utilization bars
   - "Due Soon" alert for statements
5. **Budgets Progress:**
   - Top 3 budgets as progress bars
   - Color: green (< 80%), amber (80-100%), red (> 100%)
   - "View all budgets" link
6. **Recent Transactions:**
   - Scrollable list, newest first
   - 5–8 items, "View all" link
   - Swipe-to-delete (with undo)
7. **Action FAB:** "+" button for quick entry

### Empty State (No Data)
- "Welcome to ClearMoney!"
- Onboarding carousel (3–4 steps)
- "Create your first account" CTA

### Loading State
- Skeleton loading for each card
- Smooth fade-in on load

### Accessibility
- `aria-label="Net worth: 85,500 EGP"` on main value
- Sparkline: `role="img"` + `aria-label="Net worth trend over 30 days"`
- Links: keyboard navigation + focus ring

---

## 3. Accounts Screen

### List View
**Grouped by Institution**

```
┌─ HSBC Egypt ─────────────┐
│ Personal Savings          │
│ ₩ 15,000.50              │
├─────────────────────────┤
│ Credit Card              │
│ ₩ 15,000 used / 50,000   │ (red if > 80%)
└─────────────────────────┘

┌─ Chase ───────────────────┐
│ USD Checking              │
│ $ 5,000.00               │
└─────────────────────────┘
```

**Actions:**
- Tap account → detail screen
- Long-press → edit/delete menu
- Floating "+" button → add account
- Swipe right → toggle dormant

### Account Detail Screen
**Full account info + transactions + options**

**Sections:**
1. **Header:**
   - Account name, type badge (Savings/Credit Card)
   - Current balance (large, bold)
   - Utilization % (for credit cards)
2. **30-Day Balance Chart:**
   - Sparkline (no axes)
   - On tap: show running balance with date
3. **Metadata (if credit card):**
   - Statement day & due day
   - Days until due (e.g., "Due in 5 days")
   - Interest-free period remaining
4. **Health Config:**
   - Min balance warning (if set)
   - Status indicator (⚠️ if below)
5. **Recent Transactions:**
   - 20–30 items, paginated
   - Swipe-to-delete each
   - Pull-to-refresh entire list
6. **Action Buttons:**
   - "Edit Account"
   - "Mark Dormant"
   - "Delete Account" (with confirmation)

### Create/Edit Account Form
**Bottom sheet or modal**

**Fields:**
- Type (dropdown): Savings, Current, Prepaid, Cash, Credit Card, Credit Limit
- Name (text) — auto-fills if blank
- Currency (dropdown): EGP, USD
- Initial Balance (number, decimal) — for credit cards, skipped
- Credit Limit (number, decimal) — only shown for credit card types
- Institution (dropdown) — required, shows user's institutions

**Validation:**
- Type required
- Name auto-fill if blank: "{Institution} - {Type}"
- Credit limit required for credit types
- Initial balance defaults to 0

**Submit:** "Create Account" or "Save Changes"

---

## 4. Transactions Screen

### List View (Filtered & Paginated)
**Grouped by date (newest first)**

```
┌─ Today ─────────────────┐
│ 12:35 PM  Coffee        │
│           ₩ -50         │ (category icon)
├─────────────────────────┤
│ 08:00 AM  Salary        │
│           ₩ +5,000      │ (income, green)
└─────────────────────────┘

┌─ Yesterday ─────────────┐
│ 6:45 PM  Groceries      │
│         ₩ -350          │
└─────────────────────────┘
```

**Filter Bar (Below Header):**
- Account dropdown
- Category dropdown (optgroup: Expenses | Income)
- Type toggle: All / Expense / Income
- Date range: [From] to [To]
- Search box: matches note

**Actions:**
- Tap tx → detail screen
- Swipe-to-delete (undo available for 3 sec)
- Pull-to-refresh
- Scroll down → load next 50

### Transaction Detail Screen
**Full tx info + edit/delete options**

**Display:**
- Date & time
- Type badge (Expense/Income/Transfer)
- Amount (large, bold)
- Currency
- Account
- Category (if present) + icon
- Note (if present)
- Tags (if present)
- Created timestamp
- Edit button
- Delete button

---

## 5. Transaction Entry Flows

### Quick Entry (Minimal Form)
**Fast, smart defaults**

```
┌──────────────────────────┐
│ Amount: [150]            │
├──────────────────────────┤
│ Account: [Last Used ▼]   │
│ Category: [Last Used ▼]  │
├──────────────────────────┤
│ Note: [optional]         │
├──────────────────────────┤
│ [More Options ▼]         │
│ (Date + Virtual Account) │
└──────────────────────────┘
```

**Defaults:**
- Type: Expense
- Account: Last used
- Category: Last used
- Date: Today
- Currency: From account

**More Options (Expandable):**
- Date picker
- Virtual Account allocation

**Submit:** "Save" button (min 48px)

---

### Full Transaction Form
**All fields exposed**

**Fields:**
1. Type (radio): Expense, Income
2. Amount (number, decimal) — must be > 0
3. Account (dropdown) — required
4. Category (combobox with search) — optional
5. Note (text area) — optional
6. Date (date picker) — defaults to today
7. Time (time picker, optional)
8. Tags (text field, comma-separated)
9. Virtual Account (dropdown, optional)

**Validation:**
- Amount > 0
- Account required
- Category optional but if selected must exist
- Date defaults to today
- Currency enforced from account

**Submit:** "Save Transaction"

---

### Transfer Form
**Same-currency or cross-currency**

**Fields:**
1. From Account (dropdown) — required
2. Amount (number) — required, > 0
3. To Account (dropdown) — required, must differ from source
4. Exchange Rate (number, optional) — if currencies differ
5. Counter Amount (number, auto-calc or editable) — if currencies differ
6. Fee Amount (number, optional, ≥ 0)
7. Date (date picker, defaults today)

**Validation:**
- Both accounts exist
- Different accounts
- Same currency OR exchange rate provided
- Amount > 0, fee ≥ 0
- Resolve exchange: require ≥ 2 of (amount, rate, counter_amount)

**Submit:** "Create Transfer"

---

### Batch Entry
**Multiple transactions at once**

**Table-like Interface:**
| Amount | Account | Category | Note | Date |
|--------|---------|----------|------|------|
| 100    | Savings | Food     | ...  | 2026-03-25 |
| 50     | Cash    | Transport| ...  | 2026-03-25 |

**Actions:**
- Add row (button at bottom)
- Delete row (swipe-left or ⊗ icon)
- Edit inline
- Submit: "Save All" (validates all before submitting)

**Behavior:**
- Non-atomic (best-effort); if one fails, return error for that row
- Show success count + errors

---

## 6. Categories Screen

### List View
**Two tabs or optgroup: Expenses | Income**

```
┌─ Expenses ──────────────┐
│ 🍔 Food & Groceries     │
│ 🚗 Transport            │
│ 💊 Health              │
└─────────────────────────┘

┌─ Income ────────────────┐
│ 💰 Salary              │
│ 💼 Freelance           │
└─────────────────────────┘
```

**Actions:**
- Tap category → detail (shows usage count, transactions)
- "+" button → create category
- Long-press → edit/delete menu

### Create Category Form
**Dialog or bottom sheet**

**Fields:**
- Name (text) — required
- Icon (emoji picker) — optional
- Type (radio): Expense, Income — defaults to Expense

**Validation:**
- Name required, non-empty
- Prevents duplicate names

---

## 7. Budgets Screen

### List View
**All budgets for current month**

```
┌─ Food & Groceries ──────┐
│ 70% of ₩ 500           │
│ ₩ 350 spent            │
│ ₩ 150 remaining        │
│ [=====─────] (amber bar)│
└─────────────────────────┘

┌─ Transport ─────────────┐
│ 30% of ₩ 200           │
│ ₩ 60 spent             │
│ ₩ 140 remaining        │
│ [==────────] (green bar)│
└─────────────────────────┘
```

**Status Colors:**
- Green: < 80%
- Amber: 80–100%
- Red: > 100%

**Actions:**
- Tap budget → detail
- "+" button → create budget
- Swipe-to-delete → confirm & delete

### Create Budget Form
**Modal or bottom sheet**

**Fields:**
- Category (dropdown) — required
- Monthly Limit (number, decimal) — required, > 0
- Currency (dropdown) — defaults to EGP

**Validation:**
- Category required, not already budgeted
- Limit > 0
- Unique per (user, category, currency)

---

## 8. People Screen (Loans)

### List View
**People owed to / owed by**

```
┌─ People ────────────────┐
│ Ahmed                   │
│ You owe ₩ 250 EGP      │
├─────────────────────────┤
│ Mom                     │
│ Owes you ₩ 500 EGP     │
└─────────────────────────┘
```

**Actions:**
- Tap person → detail
- "+" button → add person
- Swipe-to-delete → confirm

### Person Detail Screen
**Debt summary + transaction history**

**Sections:**
1. **Balance:**
   - Person's name
   - EGP balance (if ≠ 0)
   - USD balance (if ≠ 0)
   - Status: "Owes you" / "You owe" / "Settled"
2. **Transactions:**
   - List of all loans + repayments
   - Grouped by type (loan_out, loan_in, repay)
3. **Actions:**
   - "Record Loan"
   - "Record Repayment"
   - "Delete Person"

### Record Loan Form
**Dialog/modal**

**Fields:**
- Loan Type (radio): I Lent Them, They Lent Me
- Amount (number, decimal) — > 0
- Account (dropdown) — required
- Note (text) — optional
- Date (date picker) — defaults today

**Currency:**
- Enforced from account (override rule applies)

**Validation:**
- Amount > 0
- Account exists + belongs to user

---

## 9. Virtual Accounts Screen

### List View
**Envelope budgeting overview**

```
┌─ Vacation Fund ────────┐
│ ₩ 1,500 / ₩ 5,000     │
│ 30% complete           │
│ [======────────] ✈️     │
└──────────────────────┘

┌─ Emergency ────────────┐
│ ₩ 3,000 / ₩ 10,000    │
│ 30% complete           │
│ [======────────] 🆘     │
└──────────────────────┘
```

**Warnings (if any):**
- ⚠️ "Total allocations exceed account balance"

**Actions:**
- Tap VA → detail
- "+" button → create VA
- Swipe-to-delete → confirm

### Create Virtual Account Form
**Bottom sheet**

**Fields:**
- Name (text) — required
- Target Amount (number, optional)
- Icon (emoji picker) — optional
- Color (color picker) — defaults to teal
- Linked Account (dropdown, optional)
- Exclude from Net Worth (toggle) — defaults false

**Validation:**
- Name required, non-empty

---

## 10. Recurring Rules Screen

### Pending Rules View
**Rules due today**

```
┌─ Pending Today ────────┐
│ Netflix Subscription   │
│ ₩ 50 Expense          │
│ [Confirm] [Skip]      │
└──────────────────────┘
```

**Actions:**
- Confirm → create transaction + advance due date
- Skip → advance due date, stay pending

### All Rules View
**List of all recurring rules**

```
Active Rules:
├─ Netflix (monthly, next 2026-04-15)
├─ Gym (weekly, next 2026-03-28)
└─ Salary (monthly, next 2026-04-01)
```

**Actions:**
- Tap rule → detail
- Toggle active/inactive
- Swipe-to-delete → confirm

---

## 11. Reports Screen

### Monthly Report
**Category breakdown + trends**

**Controls:**
- Month/Year picker
- Currency filter (EGP, USD, All)

**Sections:**
1. **Spending by Category (Donut Chart):**
   - Visual: CSS conic-gradient (8-color palette)
   - Legend: category name + amount + %
   - Tap slice → show transactions in that category
2. **Income vs Expenses (Bar Chart):**
   - Visual: CSS flexbox bars
   - Bar labels: amount + percent
3. **Summary:**
   - Total income
   - Total expenses
   - Net (income - expenses)

**Accessibility:**
- Donut chart: `role="img"` + `aria-label="Spending breakdown: Food 35%, Transport 20%..."`
- Bar chart: Visually-hidden data table for screen readers

---

## 12. Settings Screen

### Options
- **Dark Mode Toggle**
  - Button: "☀️ Enable Dark Mode" / "🌙 Disable Dark Mode"
  - Persistent: localStorage (web) or NSUserDefaults (iOS)
  - `role="switch"` + `aria-checked`
- **CSV Export**
  - Date range picker (from / to)
  - "Download CSV" button
  - Success toast: "File downloaded"
- **Push Notifications**
  - Toggle: "Enable push notifications"
  - Request permission on toggle
- **About**
  - App version
  - "Built with ❤️ using React Native"

### Accessibility
- All toggles have `role="switch"` + `aria-checked`
- Labels clearly associated with controls
- Focus ring visible on all buttons

---

## 13. Mobile-Specific UX Patterns

### Bottom Sheet Modal
**For forms (account, category, budget, etc.)**

- Slides from bottom
- Swipe-down to dismiss (or close button)
- Slight blur on background
- Rounded top corners (16px radius)
- Safe-area bottom padding

### Swipe-to-Delete
**On transaction list**

- Swipe left: reveal delete button
- Delete button: red background
- Confirm: "Are you sure? (Undo available for 3 sec)"
- Undo: Auto-dismiss after 3 seconds

### Pull-to-Refresh
**On transaction list, account detail**

- Pull down from top
- Spinner appears
- Release to refresh
- Success: toast "Updated"
- Error: toast "Failed to refresh"

### Loading Skeleton
**While fetching data**

- Card-shaped loaders (accounts, budgets)
- Line loaders (transaction list)
- Subtle animation (pulse or gradient shimmer)
- Fade-out when real content loads

### Toast Notifications
**Temporary feedback messages**

- Position: bottom of screen (above nav bar)
- Duration: 3 seconds (dismissible)
- Colors:
  - Success: green with checkmark
  - Error: red with X
  - Info: blue with ℹ️
  - Warning: amber with ⚠️

### Bottom Navigation
**Persistent tab bar**

- Tabs: Home, Accounts, Transactions, More
- Active tab: teal color, label visible
- Inactive tab: gray, label visible or icon-only
- Icons: 24–28px
- Touch target: ≥ 48px tall

---

## 14. Dark Mode Support

### Colors (Tailwind-based)
**Light Mode:**
- Background: white
- Text: slate-900
- Borders: gray-200
- Accent: teal-600

**Dark Mode:**
- Background: slate-900
- Text: slate-100
- Borders: slate-700
- Accent: teal-400 (lighter for contrast)

### Overrides for Dark Mode
- Input fields: slate-800 background, slate-100 text
- Disabled fields: darker slate-900, dimmed slate-600
- Red text (errors): red-400 (not red-600) for 4.5:1 contrast
- Green text (success): emerald-400 (not green-600)

### Persistence
- Store preference in Keychain (iOS) or SharedPreferences (Android)
- Default to system preference on first launch

---

## 15. Accessibility Requirements

### Form Labels
- Every input needs `<label for="">` or `aria-label`
- Error messages use `role="alert"` + `aria-describedby`
- Invalid fields: `aria-invalid="true"`
- Radio groups: `<fieldset>` + `<legend>`

### Buttons
- Min 48px × 48px touch target
- Icon-only buttons: must have `aria-label`
- Active nav items: `aria-current="page"`

### Color Contrast
- Text on background: 4.5:1 minimum
- Large text (18pt+): 3:1 minimum
- Don't rely on color alone (include icons, patterns, or text)

### Keyboard Navigation
- Tab through all interactive elements
- Enter to activate buttons
- Arrow keys for radio groups, dropdowns, menus
- Escape to close dialogs

### Screen Reader Support
- Page landmark: `<main>`, `<nav aria-label="...">`, `<footer>`
- ARIA live regions: `aria-live="polite"` for updates, `"assertive"` for errors
- Charts: provide `<title>`, `<desc>`, or `role="img"` + `aria-label` with data summary

---

## 16. Error States & Validation

### Field-Level Errors
```
┌────────────────────────┐
│ Email                  │
│ [invalid@example    ] ← red border
│ ✗ Invalid email format│ ← error message
└────────────────────────┘
```

### Form-Level Errors
- Toast or alert at top of form
- `role="alert"` for screen readers
- Clear, actionable message

### Network Errors
- Toast: "Network error. Please try again."
- Retry button in toast or separate CTA
- Offline indicator in status bar (optional)

### Timeout Errors
- Toast: "Request timed out. Please try again."
- Auto-retry after 3 seconds or manual retry button

---

## 17. Empty States

### No Transactions
```
┌──────────────────────┐
│ 📭                   │
│ No transactions yet  │
│ Create your first    │
│ [Quick Entry]        │
└──────────────────────┘
```

### No Accounts
```
┌──────────────────────┐
│ 🏦                   │
│ No accounts yet      │
│ Connect a bank or    │
│ [Add Account]        │
└──────────────────────┘
```

### No Budgets
```
┌──────────────────────┐
│ 📊                   │
│ No budgets           │
│ Set spending limits  │
│ [Create Budget]      │
└──────────────────────┘
```

---

**Generated from production UX analysis on 2026-03-25**
