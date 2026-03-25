# Multi-Currency UX Patterns — Research Summary

**Date:** March 2026
**Purpose:** Guide design decisions for ClearMoney's multi-currency features
**Based on:** Financial app UX research, design systems (Wise, Revolut, PayPal, N26, Alipay), W3C accessibility standards

---

## 1. Currency Selection UI Patterns

### 1.1 Display Format: Code Over Symbol

**Why:** Currency symbols like `$` are ambiguous—multiple countries use them. Currency codes (ISO 4217) are unambiguous.

**Best Practice (from Wise Design System):**
- Format: `[CODE] [NAME]` → "AUD Australian dollar", "GBP British pound"
- Use this in dropdowns, display fields, and currency picker lists
- Display full name on desktop; code-only acceptable on mobile if space-constrained

**When Displaying Amounts:**
- Before number for amounts: `HKD 778.0`, `USD 1,250.50`
- After number for exchange rates: `1 USD = 6.8079 CNY`

**Reduces confusion:** International users won't misinterpret `$100` (USD? AUD? SGD?) as `USD 100`.

### 1.2 Currency Selector Placement

**Web/Desktop:**
- Dropdowns: currency selector inline with amount input
- Panel/modal: larger list of currencies, searchable
- Pinning: ability to pin favourite currencies to top of list

**Mobile Web & Apps (from Wise design system):**
- **Mobile web:** Bottom sheet for currency selection
- **Mobile native:** Full-page surface for currency selector
- **Rationale:** More screen space, easier touch interaction, avoids cramming into small UI

**Example interaction:**
```
[Input: 100] [USD ▼]  ← tap to open currency selector
```

### 1.3 Dropdown vs. Combobox Trade-off

| Pattern | Best For | Notes |
| --- | --- | --- |
| **Searchable combobox** | 50+ currencies | User types "GBP" or "British" to narrow list |
| **Grouped dropdown** | <30 frequently-used currencies | Group by region: "Europe", "Asia", "Africa" or by frequency: "Recent", "All" |
| **Recent currencies** | Quick re-selection | Show 3–5 most-recently-used at top |
| **Favourites pinning** | Power users with specific currencies | Allow users to star currencies they use often |

**Mobile-first rule:** Always allow searching/filtering—mobile keypads make long scrolling painful.

---

## 2. Multi-Currency Data Display

### 2.1 Transaction Lists with Multiple Currencies

**Problem:** Mixing currencies in a transaction list without context causes confusion.

**Solutions:**

**Option A: Show Original Currency + Converted (if applicable)**
```
Groceries Store
USD 45.50
Display: "USD 45.50"  (original currency, always visible)
Optional: "≈ EGP 1,368" (converted to account's base, less prominent)
```

**Option B: Show Original Only, Expand on Detail**
```
List view: "USD 45.50"
Detail view: Shows "USD 45.50" + conversion rate used + converted amount
```

**Why:** Users care about what they actually spent (original currency) first. Conversion is secondary context.

**ISO 4217 Currency Code Placement:**
- Before amount: `USD 45.50` or `GBP 128.75`
- Prevents ambiguity (no relying on locale-specific symbols)
- Consistent across international users

### 2.2 Account Balance Display (Multi-Currency Accounts)

**Scenario:** User has accounts in USD, EUR, GBP. Dashboard shows total net worth.

**Recommended Pattern:**

**Primary Display (account list):**
```
My Checking (USD)
$1,250.50

My Savings (EUR)
€2,340.00

My Spending (GBP)
£500.25
```

**Secondary Display (dashboard summary):**
```
NET WORTH (in my base currency)
≈ USD 4,520.10

Breakdown:
USD 1,250.50
EUR 2,340.00 (≈ USD 2,500.00)
GBP 500.25 (≈ USD 636.60)
```

**Key decisions:**
- Show each account in its **native currency** (primary)
- Show consolidated total in **user's base/home currency** (secondary)
- Exchange rates used should be **labeled as reference rates** ("≈" symbol or disclaimer)
- Rate timestamp: "Updated 2 hours ago" or "Real-time rate"

### 2.3 Reports & Dashboard Charts with Multiple Currencies

**Problem:** Pie charts and bar charts don't work across currencies (can't add USD 100 to EUR 100 directly).

**Solutions:**

**Option A: Single Base Currency**
- Convert all amounts to user's chosen base currency for reporting
- Show original currency in detail/drill-down
- Clear note: "All amounts converted to USD for comparison"

**Option B: Separate Charts per Currency**
- Show donut for USD expenses, separate donut for EUR expenses
- Clear labeling: "USD Expenses (Top Categories)", "EUR Expenses"
- Useful when user has truly separate spending patterns in different currencies

**Option C: Hybrid (Recommended for personal finance)**
- Dashboard: Shows base currency totals for quick insight
- Reports: Ability to filter by currency
- Export: CSV includes both original and converted amounts

---

## 3. Currency Conversion Interface

### 3.1 When & How to Show Exchange Rates

**When to show:**
- **Before transfer:** Exact rate user will receive
- **After transfer:** Rate actually used (rates change in real-time)
- **In transaction details:** Reference rate if conversion occurred
- **In reports:** Used for cross-currency transactions

**What to display:**
```
Exchange Rate
1 USD = 50.10 EGP
(Reference rate. Actual rate may differ.)

Sending: USD 100
Receiving: ≈ EGP 5,010
Fee: USD 2
```

**Transparency matters (from Wise research):**
- Show exact fee in currency being sent
- Show final amount user receives
- Timestamp of rate used
- Option to lock rate for X minutes if available

### 3.2 Currency Conversion UI Patterns

**Pattern A: Inline Converter (single input)**
```
Amount: [100] [USD ▼]
↓ converts to ↓
Result: [5,010] [EGP ▼]
Rate: 1 USD = 50.10 EGP (real-time)
```
✅ Mobile-friendly, simple UX
❌ Less control over precision

**Pattern B: Dual Input (source & destination)**
```
Sending          Receiving
[100] [USD ▼]    [5,010] [EGP ▼]

Rate: 1 USD = 50.10 EGP
You pay: USD 102 (incl. fee)
```
✅ Shows both sides, clear fee breakdown
❌ More complex UI

**Pattern C: Swap Button**
```
[100] [USD ▼]
      ⇅ (swap button)
[5,010] [EGP ▼]
```
✅ Lets users switch source/destination instantly
✅ Great for "what if I send from my EUR account instead?"

**Real-time vs. Locked rates:**
- **Real-time:** Best for quotes, information (no commitment)
- **Locked:** Used during checkout/transfer (5–10 min lock typical)
- Clear visual distinction: Lock icon 🔒 vs. refresh icon 🔄

---

## 4. Account/Wallet Currency Assignment

### 4.1 Single-Currency Accounts (Recommended)

**Pattern:** Each account has exactly one currency, set at creation.

```
Account creation form:
[Account Name: "Savings"]
[Currency: USD ▼]
[Institution: Bank XYZ]
```

**Rationale:**
- ✅ Simple mental model (1 account = 1 currency)
- ✅ No ambiguity about balance (balance *is* in that currency)
- ✅ Clear transfer rules (USD to USD = no conversion, USD to EUR = conversion)
- ✅ ClearMoney's current model

**Best practice:** Disable currency change after account creation (or require manual reconciliation flow).

### 4.2 Multi-Currency Wallets (Advanced)

**Pattern:** Single account holds multiple currency balances (like Wise, Revolut, N26).

```
My Account (with multiple currencies)
USD: $1,250.50
EUR: €340.00
GBP: £120.75
```

**Trade-off:**
- ✅ More flexible (single account, any currency)
- ❌ Adds complexity (which currency for auto-spend? conversion rates?)
- ❌ Requires clear UI to show breakdown per currency

**If implementing:** Reserve for future. Not in ClearMoney MVP scope.

---

## 5. Mobile-Friendly Currency Selection

### 5.1 Touch-Optimized Patterns

**Mobile Dropdown (bottom sheet):**
```
[Tap to change currency]
┌──────────────────┐
│ Search: [USD   ] │  ← searchable
├──────────────────┤
│ ✓ USD (selected) │
│   EUR            │
│   GBP            │
│   JPY            │
│   CNY            │
│   [Show more]    │
└──────────────────┘
```

**Rationale:**
- Bottom sheet scrolls within safe thumb zone
- Large tap targets (44–48px minimum)
- Search bar at top for quick filtering
- Selected option marked with checkmark

### 5.2 Gesture Patterns

**Swipe to change currency (power users):**
- Swipe left/right on amount field → cycle through favourite currencies
- ✅ Fast after learning curve
- ❌ Not discoverable; must be explained in onboarding or tooltips

**Tap & hold for currency details:**
- Hold currency selector → shows exchange rates to other currencies
- ✅ Power users can make quick decisions
- ✅ Doesn't clutter default view

---

## 6. Accessibility for Currency Inputs & Display

### 6.1 ARIA Patterns for Currency Input

**HTML structure with labels:**
```html
<label for="amount">Amount</label>
<input
  id="amount"
  type="text"
  inputmode="decimal"
  aria-label="Amount to send"
  aria-describedby="currency-help"
  required
/>

<label for="currency">Currency</label>
<select id="currency" aria-label="Select currency">
  <option value="USD" selected>USD - United States Dollar</option>
  <option value="EUR">EUR - Euro</option>
</select>

<span id="currency-help" role="status">
  Enter a valid amount. Fee will be calculated.
</span>
```

**Key attributes:**
- `<label for="">`: Associates label with input
- `aria-describedby`: Links to help text or error message
- `aria-required="true"`: Indicates required field
- `aria-invalid="true"`: On validation error
- `role="alert"`: For error messages (screen reader announces immediately)

### 6.2 Number Input Challenges

**Problem:** `<input type="number">` has browser inconsistencies.

**Solution:** Use `type="text" inputmode="decimal"` instead:
```html
<input
  type="text"
  inputmode="decimal"
  placeholder="0.00"
  pattern="[0-9]*([\.,][0-9]{1,2})?"
/>
```

**Why:**
- ✅ Consistent across iOS, Android, desktop
- ✅ Accepts both `.` and `,` for decimal separator
- ✅ Works with international keyboards
- ✅ Screen readers treat it as normal text input

### 6.3 Currency Display for Screen Readers

**Problem:** Screen readers read symbols oddly ("dollar sign 100" vs. "100 dollars").

**Solution: Hide visual symbol, use aria-label:**
```html
<span aria-label="100 US dollars">
  <span aria-hidden="true">USD</span> 100.00
</span>
```

Or provide a visually-hidden explanation:
```html
<span class="currency-amount">
  USD 100.00
  <span class="sr-only">(100 US dollars)</span>
</span>
```

**CSS for screen-reader-only text:**
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

### 6.4 Color Contrast for Multi-Currency Data

**Issue:** Currency codes often displayed in secondary color.

**Standard:** WCAG AA requires 4.5:1 contrast ratio for text.

**Example (fails accessibility):**
```html
<span style="color: #999;">USD</span> 100.00
<!-- Gray on white: ~2:1, fails WCAG AA -->
```

**Better:**
```html
<span style="color: #555; font-weight: 600;">USD</span> 100.00
<!-- Dark gray, bold: ~7:1, passes WCAG AAA -->
```

---

## 7. How Leading Apps Present Currency Information

### 7.1 Wise (Transparent & Detailed)

| Feature | Implementation |
| --- | --- |
| **Currency selector** | Code + name: "GBP British pound" |
| **Exchange rates** | Real-time, with timestamp |
| **Fee breakdown** | Explicit amount in source currency |
| **Platform-specific UI** | Web (panel), mobile (bottom sheet) |
| **Conversion display** | "You send: USD 100" → "Recipient gets: GBP 80.50" |

**Philosophy:** Transparency builds trust. Show every number.

### 7.2 Revolut (Customization & Widgets)

| Feature | Implementation |
| --- | --- |
| **Multi-currency wallet** | Single account, multiple balances |
| **Quick swap** | Fast conversion between currencies (with in-app rate) |
| **Currency conversion calculator** | Built into spend tracking |
| **Customizable widgets** | Users add/remove currency cards from dashboard |
| **Auto-conversion option** | At spending time or prompt user |

**Philosophy:** Power users want control. Give customization options.

### 7.3 PayPal (Simplicity & Progressive Disclosure)

| Feature | Implementation |
| --- | --- |
| **Currency selector** | Minimal, only shown when needed |
| **Conversion on-demand** | Prompt user only at checkout |
| **Transparent fees** | Shown before confirming transaction |
| **Avoid overload** | Hide exchange rates until necessary |

**Philosophy:** Keep default flow simple. Advanced info available on request.

### 7.4 N26 (Minimalist Mobile-First)

| Feature | Implementation |
| --- | --- |
| **Card currency** | Set once at account creation |
| **Spend in other currency** | Shows conversion immediately in transaction |
| **Rates & fees** | Disclosed in transaction detail (after purchase) |
| **UI simplicity** | All currency logic handled by API, minimal UI |

**Philosophy:** Mobile users want quick actions, not detailed financial analysis.

---

## 8. Key Recommendations for ClearMoney

### 8.1 Short Term (MVP)

✅ **What to do:**
1. **Display currency codes, not symbols** in all transaction lists and reports
   - "USD 100.50" not "$100.50"
   - Prevents confusion with `$` (AUD, CAD, SGD, HKD, etc.)

2. **Show original currency primary, converted secondary**
   ```
   Expense: USD 45.50
   (≈ EGP 2,275 at rate 1 USD = 50.0 EGP)
   ```
   - User cares about actual spend first
   - Conversion is context for planning

3. **Currency selector uses bottom sheet on mobile**
   - Searchable (user types "USD" or "GBP")
   - Touch-friendly (48px+ tap targets)
   - Shows recent currencies at top

4. **Account detail shows balance in account's currency only**
   - No automatic conversion on account card
   - Conversion available on tap if desired

### 8.2 Medium Term (Q2–Q3 2026)

✅ **What to add:**
1. **Dashboard summary with base currency total**
   - "Net Worth: ≈ EGP 50,000" (user's home currency)
   - Breakdown by account: "USD: ≈ EGP 12,500", "EUR: ≈ EGP 10,000"
   - Rate freshness: "Updated 2 hours ago"

2. **Multi-currency expense reports**
   - Single base currency aggregate (for dashboard widgets)
   - Optional filter: "Show expenses in [USD only] [EUR only] [All currencies]"

3. **Accessibility audit**
   - Ensure all currency inputs have `aria-label` + `aria-describedby`
   - Currency codes pass WCAG AA contrast (4.5:1 minimum)
   - Test with screen reader (NVDA, JAWS, VoiceOver)

### 8.3 Long Term (Future)

🔮 **Nice-to-have:**
1. **Pinned favourite currencies** in currency selector
2. **Quick currency swap** (for power users with multi-currency accounts)
3. **Rate lock** before transfer (if/when transfers become available)
4. **Bulk currency conversion** in batch entry

---

## 9. Common Pitfalls to Avoid

| Pitfall | Why It's Bad | How to Avoid |
| --- | --- | --- |
| **Using symbols without codes** | `$100` ambiguous (USD? AUD? CAD?) | Always use ISO code: `USD 100` |
| **Rounding displayed amounts** | "You sent USD 100" but receiver got EUR 79.99 (rate changed) | Show rate timestamp; exact amounts only at point of transfer |
| **Auto-converting without asking** | User confused: "Why is my USD balance gone?" | Always ask before converting; show before/after clearly |
| **Hiding exchange rates** | Users distrust "opaque" financial decisions | Show rate, timestamp, fee breakdown upfront |
| **Currency selector buried deep** | Takes 3 taps to change currency; users miss feature | Primary UI element; searchable dropdown/bottom sheet |
| **Small fonts for codes** | Currency code hard to read on mobile | 14px+ minimum; 16px recommended |
| **No visual difference for different currencies** | User misreads USD as EUR in scrolling list | Use consistent `CODE amount` format; add subtle color if helpful |
| **Showing too many currencies** | Scroll overload on mobile; cognitive load | Show recent 5–10; provide search; group by region |

---

## 10. Design System Specifications

### Currency Code Format
- **Format:** `[CODE] [optional: full name]`
- **Examples:** `USD`, `USD United States dollar`, `GBP`
- **Font size:** 14–16px (min 12px on mobile, but not ideal)
- **Weight:** Regular for code; can bold if prominent

### Amount Format
- **Format:** `[CODE] [amount]` with thousands separator
- **Examples:** `USD 1,250.50`, `GBP 100,000.00`, `JPY 10,000` (no decimals)
- **Precision:** Display 2 decimals (most currencies); JPY/KWD/others 0; BTC 8
- **Alignment:** Right-align in tables for easy scanning

### Accessibility Baseline
- All currency inputs: `<label>` + `aria-describedby`
- All currency dropdowns: `aria-label` if no visible label
- All displays: Minimum 4.5:1 contrast ratio (WCAG AA)
- Touch targets: 44–48px minimum diameter

---

## 11. Research Sources

- [The UX of Currency Display (Workday Design)][1]
- [Fintech UX Design: Great Examples (LogRocket)][2]
- [Wise Money Input Design System][3]
- [The Best UX Design Practices for Finance Apps 2026][4]
- [Fintech Design Guide 2026 (Eleken)][5]
- [Mobile Banking App Design: Best Practices 2026 (Purrweb)][6]
- [Currency Input Patterns (UIPatterns.io)][7]
- [React Aria useNumberField Documentation][8]
- [ARIA Accessibility Standards (MDN)][9]
- [Multi-Currency Reporting Guide (Workamajig)][10]

[1]: https://medium.com/workday-design/the-ux-of-currency-display-whats-in-a-sign-6447cbc4fb88
[2]: https://blog.logrocket.com/ux-design/great-examples-fintech-ux/
[3]: https://wise.design/components/money-input
[4]: https://www.g-co.agency/insights/the-best-ux-design-practices-for-finance-apps
[5]: https://www.eleken.co/blog-posts/modern-fintech-design-guide
[6]: https://www.purrweb.com/blog/banking-app-design/
[7]: http://uipatterns.io/currency-input
[8]: https://react-spectrum.adobe.com/react-aria/useNumberField.html
[9]: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA
[10]: https://support.workamajig.com/hc/en-us/articles/360022779032--Multi-currency-reports-in-depth-guide

---

## 12. Next Steps for ClearMoney

1. **Review** this document in design/product sync
2. **Audit current UI** against patterns (currency display, input accessibility)
3. **Prioritize:** Which patterns to implement first? (Suggest: currency codes → accessibility baseline → mobile UI)
4. **Implement incrementally:** One pattern at a time, test with users, gather feedback
5. **Document** any ClearMoney-specific decisions in design system
