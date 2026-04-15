# Ticketing Workflow — AI-Managed Development Tracking

This rule instructs Claude to automatically manage tickets for all ClearMoney development tasks. Tickets live in `.tickets/` as markdown files. Ahmed never manually edits tickets — Claude handles all lifecycle management.

## Core Principles

- **Automatic ticket lifecycle**: Claude creates, moves, closes tickets without user intervention
- **File-based**: Markdown in `.tickets/` folder, tracked in git
- **Frontmatter-driven**: YAML frontmatter (`id`, `title`, `type`, `priority`, `status`, `created`, `updated`) is the source of truth
- **Progress notes**: Claude appends dated notes to each ticket's "Progress Notes" section
- **One ticket per dev task**: Feature, bug fix, refactor, or chore gets a ticket

## Ticket Lifecycle

### 1. On Task Start (Before Implementation)

When Claude begins work on a non-trivial task (features, bug fixes, refactors, improvements):

1. **Check for existing ticket**:
   - Scan `.tickets/wip/` for a matching ticket (same title or related)
   - If found: move to `wip/` if not already there, update `updated` field to today

2. **Create new ticket if needed**:
   - Find next available `id` by scanning all existing `.tickets/*/*.md` files and taking max ID + 1 (zero-padded 3 digits)
   - Create file at `.tickets/wip/<id>-<slug>.md` (slug is kebab-case title)
   - Auto-fill frontmatter:
     - `id`: "001" (or next)
     - `title`: from user's request
     - `type`: derived from task (bug | feature | improvement | chore)
     - `priority`: medium (default; ask if high/low is obvious)
     - `status`: wip
     - `created`: today's date (2026-03-27 format)
     - `updated`: today's date
   - Add initial progress note: `- 2026-03-27: Started — [what Claude is working on]`

3. **Reference the ticket**: In responses, mention the ticket ID (e.g., "Ticket #001: Unified transaction form")

### 2. During Work

- **Append progress notes** when making significant decisions, hitting blockers, or changing approach
  - Format: `- YYYY-MM-DD: [description]`
  - Example: `- 2026-03-27: Added E2E test for happy path, all 3 criteria passing`
- Do not update frontmatter fields (`id`, `created`, `status`) — only Claude updates those

### 3. On Task Completion — Atomic with Commit

**CRITICAL: Ticket closure MUST be part of the same commit as the feature/fix.** Never defer ticket closure to a separate step — if context fills or the session ends between the commit and ticket cleanup, WIP goes stale.

**Workflow: close ticket → stage ticket files → stage code → commit together.**

1. **Move ticket to `done/`** (whether from `wip/` or `pending/`):
   - **From `wip/`**: Rename file: `.tickets/wip/<id>-<slug>.md` → `.tickets/done/<id>-<slug>.md`
   - **From `pending/`**: Keep file in place, just update frontmatter
   - Update frontmatter:
     - `status`: → done
     - `updated`: today's date
   - Add final progress note: `- YYYY-MM-DD: Completed — [what was delivered, key commits, or summary]`

2. **Regenerate INDEX.md**

3. **Stage ticket files alongside code changes**:
   ```bash
   git add .tickets/done/<id>-<slug>.md .tickets/INDEX.md
   # If from wip/, also stage the deletion of the old wip/ file
   git add .tickets/wip/<id>-<slug>.md
   # Then stage the feature/fix code files
   git add backend/app/file.py ...
   git commit -m "feat: description"
   ```

**Why:** The ticket move and the code change are one logical unit. Including both in the same commit guarantees they stay in sync — no orphaned WIP tickets.

### 4. On Rejection / Cancellation

If a task is cancelled, blocked, or explicitly won't-fix:

1. **Move ticket to `rejected/`**:
   - Rename: `.tickets/wip/<id>-<slug>.md` → `.tickets/rejected/<id>-<slug>.md`
   - Update frontmatter:
     - `status`: wip → rejected
     - `updated`: today's date
   - Add note: `- 2026-03-27: Rejected — [reason: dependency blocked, user cancelled, not feasible, etc.]`

2. **Regenerate INDEX.md**

## Ticket File Format

**Location**: `.tickets/<status>/<id>-<slug>.md`
**Naming**: three-digit zero-padded ID + kebab-case slug, e.g., `001-unified-transaction-form.md`

```markdown
---
id: "001"
title: "Unified transaction form"
type: feature              # bug | feature | improvement | chore
priority: medium           # low | medium | high
status: wip                # pending | wip | done | rejected
created: 2026-03-27
updated: 2026-03-27
---

## Description

What needs to be done and why (derived from user's request).

## Acceptance Criteria

- [ ] First acceptance criterion
- [ ] Second acceptance criterion

## Progress Notes

- 2026-03-27: Started — Exploring transaction views, understanding form structure
- 2026-03-27: Completed — Form refactored, 5 tests added, E2E passing
```

### Frontmatter Fields

| Field | Format | Notes |
| --- | --- | --- |
| `id` | "001", "002", ... | Three-digit zero-padded. Assigned sequentially. |
| `title` | Short string | 50 chars max. Can be same as user's task description. |
| `type` | bug \| feature \| improvement \| chore | Derived from task context. |
| `priority` | low \| medium \| high | Default to medium. Ask user if ambiguous. |
| `status` | pending \| wip \| done \| rejected | Updated by Claude. |
| `created` | YYYY-MM-DD | Set on ticket creation. Never changes. |
| `updated` | YYYY-MM-DD | Updated every time ticket moves or is edited. |

## INDEX.md Format

**Auto-generated after every ticket operation.**

```markdown
# ClearMoney Tickets

Last updated: 2026-03-27

## In Progress

| ID | Title | Type | Priority | Updated |
| --- | --- | --- | --- | --- |
| [001](wip/001-slug.md) | Unified transaction form | feature | medium | 2026-03-27 |

## Pending

(none)

## Done

| ID | Title | Type | Priority | Updated |
| --- | --- | --- | --- | --- |

## Rejected

(none)
```

- Sorted by `updated` within each group (most recent first)
- IDs are links to the ticket file
- Use "(none)" placeholder if group is empty

## When NOT to Create a Ticket

- Trivial one-line fixes (typos, obvious renames)
- Questions or research-only tasks
- Commit message improvements
- Documentation fixes that don't require code changes
- Debugging notes (unless it reveals a bug worth tracking)

**Rule of thumb**: If it's "get user approval → implement → commit," create a ticket. If it's "oh wait, that's wrong" → fix → commit, skip the ticket.

## Ticket Operations Claude Performs

### Create Ticket
```
1. Scan max ID in .tickets/
2. Write new file to .tickets/wip/<next-id>-<slug>.md
3. Regenerate INDEX.md
```

### Move Ticket
```
1. Read ticket from source folder
2. Update status + updated fields
3. Write to destination folder
4. Delete from source folder
5. Regenerate INDEX.md
```

### Append Progress Note
```
1. Read ticket file
2. Add line: - YYYY-MM-DD: [note]
3. Update updated field to today
4. Write back
5. (Don't regenerate INDEX unless status changed)
```

### Close Ticket (Move to Done) — MUST be atomic with feature commit
```
1. Read ticket from wip/ or pending/ (wherever it lives)
2. Update: status → done, updated → today
3. Add progress note: "- YYYY-MM-DD: Completed — [summary]"
4. If from wip/: write to done/<id>-<slug>.md and delete from wip/
   If from pending/: update file in place
5. Regenerate INDEX.md
6. Stage ticket files (done/ + deleted wip/ + INDEX.md) alongside code
7. Commit everything together — never in a separate commit
```

### Reject Ticket (Move to Rejected)
```
1. Read ticket from wip/
2. Update: status → rejected, updated → today
3. Add progress note: "- YYYY-MM-DD: Rejected — [reason]"
4. Write to rejected/<id>-<slug>.md
5. Regenerate INDEX.md
```

## Example: Setting Up Ticketing System

**Task**: "Build a ticketing system"

1. Claude creates `.tickets/wip/001-setup-ticketing-system.md`
   - Type: chore
   - Priority: medium
   - Status: wip
   - Initial note: "- 2026-03-27: Started — Setting up folder structure, rule files"

2. Claude creates folder structure (`.tickets/pending/`, `.tickets/wip/`, etc.)

3. Claude creates `.claude/rules/ticketing-workflow.md` (this file)

4. Claude creates initial `.tickets/INDEX.md`

5. Claude updates `CLAUDE.md` to reference ticketing rule

6. Claude tests: reads INDEX.md to verify it loads correctly

7. Claude moves ticket to done:
   - Renames `.tickets/wip/001-*.md` → `.tickets/done/001-*.md`
   - Updates frontmatter: status → done, updated → 2026-03-27
   - Adds note: "- 2026-03-27: Completed — Ticketing system ready, rule file in place"

8. Claude regenerates `.tickets/INDEX.md`

## Integration with CLAUDE.md

Add to the Rules reference table in `CLAUDE.md`:

```markdown
| Ticketing Workflow | `.claude/rules/ticketing-workflow.md` | AI-managed development tickets, auto-created/updated by Claude |
```

## No Manual Intervention

This system is designed so Ahmed never:
- Types a ticket ID manually
- Updates a ticket's status or date manually
- Creates ticket files directly (Claude does it via Write tool)
- Regenerates INDEX.md (Claude does it)

Claude handles all of this automatically as part of its dev task execution.
