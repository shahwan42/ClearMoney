---
id: "117"
title: "QA Comprehensive Test Plan for Implemented Features"
type: feature
priority: high
status: pending
created: 2026-04-17
updated: 2026-04-17
---

## Description
This ticket serves as a comprehensive Quality Assurance test plan covering all implemented features and critical bug fixes in the ClearMoney application. As a Senior QA Engineer, use this test document to execute structured testing. Each capability is broken down into specific positive flows, edge cases, negative tests, and potential enhancements. Checked items denote passing scenarios; findings and bugs should be reported linking back to these cases.

---

## 011: Merge transfer & exchange into Move Money tab
**Functional Tests:**
- [ ] Navigate to the "Move Money" tab; verify UI layout renders without errors on desktop and mobile.
- [ ] Execute a standard transfer between two same-currency accounts. Verify atomic balance updates (source minus amount, dest plus amount).
- [ ] Execute an exchange between two different-currency accounts. Verify correct target currency conversion logic is applied.
**Edge Cases & Negative Tests:**
- [ ] Attempt to move money with amount `0` or a negative value; verify validation kicks in.
- [ ] Select the exact same source and destination account; verify UI error prevents submission.
- [ ] Initiate an exchange while exchange rates API is unavailable or missing data; verify fallback mechanism or graceful error.
**Enhancement Opportunities:**
- [ ] Add a confirmation dialog showing the calculated conversion rate before final execution.

## 012 & 020: Add optional fee to transactions & Recurring Rules
**Functional Tests:**
- [ ] Create an expense transaction with a fee; verify total deduction is `amount + fee`.
- [ ] Create an income transaction with a fee; verify total addition is `amount - fee`.
- [ ] Set up a recurring money movement rule that includes a fee. Let cron execute it and verify balance changes correctly account for the fee.
**Edge Cases & Negative Tests:**
- [ ] Enter a negative fee value; verify form validation blocks submission.
- [ ] Enter a fee larger than the transaction amount (for income). Verify correct ledger subtraction (possibly resulting in net negative).
- [ ] Modify an existing transaction to remove a fee; verify account balance is accurately re-adjusted.

## 013, 014, 015 & 018: UI Form Constraints & Submissions
**Functional Tests:**
- [ ] Enter a note exceeding the maximum character limit in Quick-Entry. Verify the field stops accepting characters or shows a validation error.
- [ ] Attempt the same note length check on the Edit Form. Verify parity with Quick-Entry.
- [ ] Use the Quick-Entry date picker; try to pick a date in the future. Verify future dates are disabled/invalidated.
**Edge Cases & Negative Tests:**
- [ ] Type inside a category combobox while nesting in another form. Hit Enter. Verify the parent form *does not* unexpectedly submit.
- [ ] Paste a giant wall of text into the note payload directly via API. Verify backend validation kicks in with a 400 response.

## 017 & 019: Budgets Module Updates
**Functional Tests:**
- [ ] Modify an existing active budget (limit up or down); verify progress bars instantly reflect the new ratio.
- [ ] Click an active budget row; verify the details view displays a list of ALL contributing transactions for that month.
- [ ] Verify the sum of the contributing transactions exactly matches the "Spent" value on the budget card.
**Edge Cases & Negative Tests:**
- [ ] Update a budget limit to `0`. Verify behavior (should it delete or just mark as exceeded?).
- [ ] Categorize an expense on the very last day/minute of the month. Verify it registers against the correct month's budget.
**Enhancement Opportunities:**
- [ ] Pagination or infinite scroll for the contributing transactions view if a user has 100+ transactions in a budget.

## 021: Net Worth Debt Calculation
**Functional Tests:**
- [ ] Create a loan (liability/debt) account or person with negative balance.
- [ ] Verify Dashboard "Net Worth" subtracts this debt aggregate from total assets accurately.
**Edge Cases & negative Tests:**
- [ ] Move money from an asset account to pay off a debt. Verify Net Worth does not artificially change (since it's purely a zero-sum transfer).
- [ ] View Net worth with only debt active and 0 assets. Verify negative display state.

## 022–040: I18N and RTL Infrastructure
**Functional Tests:**
- [ ] Toggle language preference in Settings from English to Arabic. Verify immediate layout flip (RTL).
- [ ] Verify main templates (Auth, Dashboard, Accounts, Budgets, Move Money) render correctly in RTL without clipping or overlap.
- [ ] Verify Categories, validation errors, and pushing notifications output the correct translated text.
**Edge Cases & Negative Tests:**
- [ ] Inspect mobile view in RTL. Ensure horizontal scrolling isn't broken.
- [ ] Switch to a non-existent language parameter via URL tampering. Verify fallback to English (or user default).

## 060: Bank Statement CSV Import
**Functional Tests:**
- [ ] Upload a standard valid CSV; proceed to column mapping. Verify form state retention correctly assigns columns.
- [ ] Run parser on Preview step; verify correct visual parsing and `suggest_category()` accurately hitting expected categories.
- [ ] Submit batch payload. Verify `TransactionService.batch_create()` creates everything in one atomic transaction, updating account balance.
**Edge Cases & Negative Tests:**
- [ ] Upload an identical file twice. Verify duplicate detection successfully flags conflicting rows (Warn, don't block).
- [ ] Upload > 5MB file / > 10,000 rows. Verify size limitation blocks process securely.
- [ ] Alter transaction file with missing amounts/dates. Verify preview step flags validation errors per-row.

## 061: Global Search
**Functional Tests:**
- [ ] Open header search overlay. Type a query matching a transaction note. Verify 300ms debounce response showing the transaction in list partial.
- [ ] Search by an exact amount and category prefix; verify results appear.
- [ ] Click a result; verify it navigates directly to the proper transaction bottom sheet/details.
**Edge Cases & Negative Tests:**
- [ ] Enter HTML/Script tags as the query; verify XSS handling and no breakage.
- [ ] Search for a transaction belonging to another user. Verify strict data isolation (return 0 results).
**Enhancement Opportunities:**
- [ ] Add faceted search filters (e.g. `category:Food >500`) directly in the header.

## 062: Savings Goals Auto-Allocation
**Functional Tests:**
- [ ] Create a Virtual Account (VA) with `monthly_target` and toggle `auto_allocate` ON.
- [ ] Simulate the confirmation of an income recurring rule. Verify system automatically sweeps `monthly_target` amount to VA.
**Edge Cases & Negative Tests:**
- [ ] Income size is less than the VA monthly target. Verify graceful partial allocation or failure notification.
- [ ] Multiple VAs have `auto_allocate` on. Verify the system allocates priority or distributes correctly without exceeding income.

## 063: Spending Insights and Trends
**Functional Tests:**
- [ ] Navigate to Trends. Verify SVG sparklines render accurately across 3/6/12 month periods.
- [ ] Verify "Anomaly callout" triggers correctly when an expense is > X% above the moving average.
- [ ] Calculate `(income - expenses) / income` manually; verify UI's "Monthly savings rate" percentage is accurate.
**Edge Cases & Negative Tests:**
- [ ] View trends for a completely empty account. Verify empty states render without math errors (Divide by zero avoidance).

## 064: Transaction Tags
**Functional Tests:**
- [ ] Append multiple tags to an expense on creation.
- [ ] Verify the "Spending by Tag" report aggregates the amounts properly.
- [ ] Filter transaction list by tag. Verify it strictly returns matching tags.
**Edge Cases & Negative Tests:**
- [ ] Delete a Tag from Settings. Verify it's cascaded/removed from related transactions without deleting the transactions.
- [ ] Add 100+ tags. Verify auto-suggest dropdown performance and scrolling.

## 065: Budget Templates & Rollover
**Functional Tests:**
- [ ] Click "Copy last month". Verify budgets are instantiated with identical limits, skipping duplicates.
- [ ] Create a budget with `rollover_enabled=True`. End the month with unspent funds; verify the new month starts with limit + last month's remaining.
**Edge Cases & Negative Tests:**
- [ ] Hit the rollover maximum cap. Verify balance doesn't infinitely accumulate beyond the set limit.
- [ ] Overspend a rollover-enabled budget. Verify the negative balance correctly reduces the subsequent month's available budget limit.

## 067: Account Reconciliation
**Functional Tests:**
- [ ] Enter a "real bank balance" into the Reconcile form. Verify correct calculated offset matching unverified transactions.
- [ ] Check off transactions to mark as `is_verified`. Verify the variance approaches zero.
**Edge Cases & Negative Tests:**
- [ ] Try locking in reconciliation without zero variance. Ensure system logs the forced adjustment accurately (or blocks it).
- [ ] Enter extreme decimal digits. Check math precision against DB (NUMERIC(15,2)).

## 068: Financial Calendar
**Functional Tests:**
- [ ] Navigate to `/calendar`. Verify recurring rules are placed on correct due dates with assigned color codes.
- [ ] Click on a specific day grid; verify modal/view shifts to view activity specifically for that day.
**Edge Cases & Negative Tests:**
- [ ] Change timezone on the local machine vs server timezone. Ensure dates map identically to UTC boundary rules.

## 069 & 070: PDF Exports & Transaction Attachments
**Functional Tests:**
- [ ] Generate a PDF report for a given month. Open PDF to check layout and data (Top 5 categories, net worth).
- [ ] Attach a photo receipt to an expense. Verify thumbnail generates. Verify click expands to full size.
**Edge Cases & Negative Tests:**
- [ ] Upload a 10MB file, or an executable (`.exe`). Verify restriction to standard image types and < 5MB file sizes.
- [ ] Delete a transaction. Verify the filesystem attachment is concurrently deleted (no orphaned files).

## 071: Smart Spending Alerts
**Functional Tests:**
- [ ] Process a transaction putting a budget at 85% capacity. Verify Push Notification triggers regarding threshold.
- [ ] Create an anomalous transaction outside deviation. Verify immediate alert notification routing.
**Edge Cases & Negative Tests:**
- [ ] Turn off alerts in user settings. Verify backend skips dispatching via Push/Email.
- [ ] Make 10 transactions grouped in one hour that pass the threshold. Ensure debouncing/rate-limiting prevents spamming the user.

## 072 & 076: Net Worth & Spending Velocity Projections
**Functional Tests:**
- [ ] View Spending Velocity dashboard card. Determine correctness of "Daily budget remaining: X EGP/day for Y days".
- [ ] Verify projection state shifts coloring correctly: Green, Amber (At Risk), Red (Overspend tracking).
- [ ] Look at Net worth projection graph. Verify known recurring rules modify the future plot visually.
**Edge Cases & Negative Tests:**
- [ ] View velocity on day 31 of a month. Check boundary conditions regarding remaining days denominator.
- [ ] Change an upcoming recurring income rule aggressively. Verify projection graph immediately reacts and shifts the optimistic trajectory.

---
**Prepared by:** Senior QA Engineer / AI Assistant  
**Next Steps:** QA to allocate test runs, check off completed scenarios, and open corresponding Bug tickets if anomalies are detected during runs.

## Progress Notes

- 2026-04-17: Reopened — Reset all test checklist items to pending for fresh manual QA execution
