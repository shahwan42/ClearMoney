---
globs: "backend/**/*.py,backend/templates/**/*.html"
---
# Common Pitfalls

- **Credit card balance signs**: CC balances are stored as negative numbers (representing debt). Display with `neg` template filter when showing "amount used".
- **Category dropdowns**: Use `<optgroup label="Expenses">` and `<optgroup label="Income">`.
- **Transaction currency**: Never trust the form's currency field — the service layer overrides it from the account.
