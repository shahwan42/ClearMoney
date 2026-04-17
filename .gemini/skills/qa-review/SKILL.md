---
name: qa-review
description: QA review of current changes — test gaps, edge cases, bugs
disable-model-invocation: false
---

Act as a QA engineer and review the current uncommitted changes.

1. Run `git diff HEAD` to see all changed files
2. For each changed template, view, or service file:
   - Identify behaviours introduced or modified
   - Check the corresponding test file for coverage of those behaviours
3. Look specifically for these gap categories:

   **Functional gaps**
   - Happy path present but no error/validation path tested
   - New conditional logic (if/else, template tags) with only one branch tested
   - Default values or fallback behaviour assumed but not asserted

   **State & interaction gaps**
   - Toggles, collapsibles, or HTMX interactions where only the initial state is tested
   - JS-driven state changes (disabled, hidden, value swaps) not verified at the HTML level
   - Server-side context variables that drive client-side behaviour (e.g. `{% if x %}...{% endif %}` in scripts) with no test for the false branch

   **Data gaps**
   - Edge cases: empty string vs None, zero amounts, missing optional fields
   - Boundary data: duplicate flows, prefill/dup context, user with vs without related records (e.g. virtual accounts)

   **Cleanup gaps**
   - Test fixtures that insert rows but never clean them up (use `connection.cursor()` DELETE or rely on transaction rollback)

4. For each gap found, state:
   - What is untested
   - What the risk is if it breaks
   - A concrete test stub (class + method name + one-line assertion comment)

5. After listing all gaps, ask: "Want me to write all these tests?"
   - If yes: write them TDD-style (RED first — run and confirm fail, then implement fixes if any bugs are uncovered)
   - Mark each test with a comment `# gap: <category>` so it's easy to find later
