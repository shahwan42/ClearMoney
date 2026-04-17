# Ticket-First Workflow — Mandatory Pre-Code Gate

Every implementation task (feature, bug fix, refactor, chore) **MUST have an open ticket in `.tickets/wip/` before the first code change is made.** This is a mandatory gate, not optional.

## Pre-Implementation Checklist

Before writing any code, running any tests, or making any changes:

1. **Scan `.tickets/wip/`** for a matching ticket (same or related title)
   - If found: confirm it's up-to-date, update `updated` field to today, continue
   - If not found: proceed to step 2

2. **Create a new ticket** using the protocol in `.gemini/rules/ticketing-workflow.md`:
   - Find next available ID (scan all `.tickets/*/*.md` files, take max ID + 1)
   - Create file at `.tickets/wip/<id>-<slug>.md`
   - Auto-fill frontmatter: `id`, `title`, `type`, `priority`, `status: wip`, `created`, `updated`
   - Add initial progress note: `- YYYY-MM-DD: Started — [what Gemini is working on]`

3. **Reference the ticket ID** in your first response:
   ```
   Working on Ticket #XXX: [title]
   ```

4. **Continue implementation** with the ticket ID present and active

---

## Scope — When Tickets Are Required

**Tickets required for:**
- New features
- Bug fixes (user-facing or internal)
- Refactors (internal restructuring, not trivial renames)
- Improvements (enhancements to existing features)
- Chores (dependency upgrades, infrastructure, tooling)
- Any change requiring TDD (RED → GREEN)
- Any change touching multiple files or apps

**Tickets NOT required for:**
- Typos in comments or documentation
- Single-line fixes in one file (obvious corrections)
- Questions or research-only tasks (no code written)
- Documentation-only changes (no code, no migrations, no config changes)
- Commit message improvements
- Debugging notes that don't reveal a ticket-worthy bug

**Rule of thumb:** If you're about to run `git add` and `git commit`, create or locate a ticket first.

---

## Integration with Other Rules

- **Ticketing workflow** (`.gemini/rules/ticketing-workflow.md`): Defines ticket mechanics (create, move, close, reject). This rule enforces **when** to use them.
- **Git workflow** (`.gemini/rules/git-workflow.md`): After ticket is created, follow commit practices (show changes, ask approval, use conventional commits).
- **TDD workflow** (`.gemini/rules/tdd-workflow.md`): After ticket is created, write RED tests first.
- **Delivery checklist** (`.gemini/rules/delivery-checklist.md`): After ticket is created, follow feature delivery steps.

---

## Why This Matters

- **Traceability**: Every code change is tied to a work item with context, acceptance criteria, and progress notes
- **Scope control**: Writing a ticket forces thinking about what needs to be done *before* diving into code
- **Async communication**: Ahmed and Gemini can reference ticket IDs instead of relying on conversation history
- **Recovery**: If context fills or session restarts, ticket ID is the entry point back to in-flight work
- **Completeness**: Ensures work is not abandoned mid-way or lost in conversation churn

---

## Example: Starting Work

**User asks:** "Add dark mode toggle to settings"

**Gemini response:**

```
Working on Ticket #009: Add dark mode toggle to settings

Creating ticket...

- Scanning .tickets/wip/ ... no existing ticket
- Creating .tickets/wip/009-add-dark-mode-toggle.md
- Title: "Add dark mode toggle to settings"
- Type: feature
- Priority: medium (default; could ask if critical)
- Status: wip
- Acceptance criteria: [list of what "done" means]
- Progress note: "- 2026-03-27: Started — Exploring settings page structure"

Now proceeding with implementation...
```

Then follows normal workflow: understand code → write RED test → implement → verify → commit.

---

## No Exceptions

This gate applies to **all non-trivial work**. There are no exceptions:
- High-priority fixes still need tickets (link them to the incident if needed)
- Urgent features still need tickets (create in 30 seconds, then code)
- Small improvements still need tickets (one ticket per improvement, not one per batch)

The overhead is minimal (~30 seconds to create a ticket) and the traceability gain is significant.
