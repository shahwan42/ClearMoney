---
id: "070"
title: "Transaction attachments (receipt photos)"
type: feature
priority: low
status: done
created: 2026-03-31
updated: 2026-04-16
---

## Description

Allow users to attach receipt photos or documents to transactions for record-keeping.

## Acceptance Criteria

- [ ] Image upload field on transaction create/edit forms
- [ ] Accept common formats: JPEG, PNG, PDF (max 5MB)
- [ ] Thumbnail preview on transaction detail bottom sheet
- [ ] Full-size view on click/tap
- [ ] Delete attachment without deleting transaction
- [ ] Storage: local filesystem (with path configurable for S3 later)
- [ ] Service-layer tests for upload, delete, file validation
- [ ] E2E test for upload → view thumbnail → delete attachment

## Technical Notes

- New model: `TransactionAttachment` (FK to Transaction, file path, content type, size)
- Or add `attachment` FileField directly to Transaction model (simpler, one attachment per tx)
- Use Django's `FileField` with upload_to path scoped by user_id
- Serve via whitenoise or Django media handler
- Consider image compression on upload (Pillow)

## Progress Notes

- 2026-03-31: Created — planned as Tier 3 feature recommendation
