---
id: "173"
title: "Virtual account: show containing account in listing and detail"
type: improvement
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Show the linked bank account in both the virtual accounts listing and the detail page.

## Acceptance Criteria

- [ ] Listing: each VA card shows `Account Name · CURRENCY` subtitle below the name
- [ ] Listing: unlinked VAs show `No account linked` in same subtitle slot
- [ ] Listing: "unlinked" badge removed
- [ ] Detail: header shows linked account as tappable link to `/accounts/{id}` with `Account Name · CURRENCY`
- [ ] Detail: unlinked VAs show plain `No account linked` text (no link)

## Progress Notes

- 2026-04-27: Started — template-only changes, data already available in both contexts
- 2026-04-27: Completed — listing shows account name · currency subtitle; detail header shows tappable link to account; unlinked VAs show "No account linked" in both
