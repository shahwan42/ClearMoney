---
id: "001"
title: "Setup AI-first ticketing system"
type: chore
priority: medium
status: done
created: 2026-03-27
updated: 2026-03-27
---

## Description

Build a file-based, AI-managed ticketing system to track ClearMoney development tasks. Tickets live in `.tickets/` as markdown files tracked in git. Claude automatically creates, moves, and closes tickets without manual intervention from Ahmed.

## Acceptance Criteria

- [x] Folder structure created (pending/, wip/, done/, rejected/)
- [x] Ticket format defined with YAML frontmatter
- [x] Ticketing workflow rule written (`.claude/rules/ticketing-workflow.md`)
- [x] INDEX.md auto-generation mechanism designed
- [x] CLAUDE.md updated with ticketing references
- [x] Initial INDEX.md created (empty)
- [x] First ticket created and moved to done

## Progress Notes

- 2026-03-27: Started — Exploring ClearMoney structure, designing AI-first ticketing system
- 2026-03-27: Completed — All components in place: folder structure, rule file, INDEX.md, CLAUDE.md updated. System ready for production use.
