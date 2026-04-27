---
id: "166"
title: "Warn user when deleting a transfer removes both account legs"
type: improvement
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Deleting a transfer or exchange transaction silently removes both legs and reverses both account balances. Users had no warning this would happen.

## Acceptance Criteria

- [x] Detail sheet delete button shows transfer-specific armed text for transfer/exchange types
- [x] Row context menu delete shows transfer-specific confirm dialog for transfer/exchange types
- [x] Regular transactions unchanged

## Progress Notes

- 2026-04-27: Completed — Two template changes: `data-armed-text` and `hx-confirm` conditionally set for transfer/exchange types
