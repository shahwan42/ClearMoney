---
id: "125"
title: "Add dead code detection with vulture"
type: chore
priority: medium
status: done
created: 2026-04-18
updated: 2026-04-18
---

## Description

Add vulture to detect unused Python code across the 336-file Django codebase. Create a Django-aware whitelist to suppress false positives, wire up a `make dead` Makefile target, and report findings.

## Acceptance Criteria

- [ ] vulture installed as a dev dependency in backend/pyproject.toml
- [ ] backend/vulture_whitelist.py created with Django-specific false positive suppressions
- [ ] `make dead` target added to Makefile and runs successfully
- [ ] Dead code findings reported to developer for triage

## Progress Notes

- 2026-04-18: Started — Installing vulture, building whitelist, wiring Makefile target
- 2026-04-18: Completed — vulture 2.16 installed, vulture_whitelist.py created (322 Django false-positive suppressions), `make dead` target added, vulture step added to CI lint job
