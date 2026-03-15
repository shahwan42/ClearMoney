# Bottom Sheet Component

Reusable slide-up sheet with swipe-to-dismiss, used across accounts, account detail, and quick entry.

## Key Files

| File | Purpose |
|------|---------|
| `static/js/bottom-sheet.js` | Shared `BottomSheet` JS module (open/close/swipe) |
| `internal/templates/partials/bottom-sheet.html` | Reusable Go template partial |
| `internal/templates/layouts/base.html` | Loads `bottom-sheet.js` via `<script defer>` |

## Usage

### Template (HTML)

Use the `bottom-sheet` partial with `dict` parameters:

```html
{{template "bottom-sheet" (dict "Name" "my-sheet")}}
{{template "bottom-sheet" (dict "Name" "my-sheet" "ZOverlay" "z-[80]" "ZSheet" "z-[90]" "MaxHeight" "max-h-[50vh]")}}
{{template "bottom-sheet" (dict "Name" "my-sheet" "Persist" true)}}
```

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `Name` | yes | — | Unique ID prefix (e.g., `"edit-sheet"`) |
| `ZOverlay` | no | `z-[60]` | Overlay z-index class |
| `ZSheet` | no | `z-[70]` | Sheet z-index class |
| `MaxHeight` | no | `max-h-[85vh]` | Max height class |
| `Persist` | no | false | If true, content is not cleared on close |

The partial generates: overlay div + sheet div (with drag handle + content area). Element IDs follow the pattern `{Name}-overlay`, `{Name}-sheet`, `{Name}-handle`, `{Name}-content`.

### JavaScript

```javascript
// Open with HTMX content loading
BottomSheet.open('my-sheet', {url: '/my-form'});

// Open with HTMX trigger event
BottomSheet.open('my-sheet', {trigger: 'load-my-form'});

// Open with callback
BottomSheet.open('my-sheet', {onOpen: function(s) { /* s.content, s.sheet, etc. */ }});

// Close (animates down, clears content after 300ms)
BottomSheet.close('my-sheet');
```

### Backward-Compatible Aliases

Define thin wrapper functions so Go handlers and template partials can call named functions:

```javascript
function openMySheet() { BottomSheet.open('my-sheet', {url: '/my-form'}); }
function closeMySheet() { BottomSheet.close('my-sheet'); }
```

Go handlers can then return `<script>closeMySheet();</script>` to close the sheet after a successful form submission.

## Architecture

- **Auto-init**: Sheets with `data-bottom-sheet` attribute are auto-registered on `DOMContentLoaded` and `htmx:afterSettle`.
- **Swipe-to-dismiss**: Touch listeners on the drag handle. Dragging >100px down closes the sheet.
- **Scroll lock**: `document.body.style.overflow = 'hidden'` while open.
- **Content clearing**: On close, `innerHTML` is cleared after 300ms (matches animation). Use `data-bottom-sheet-persist` to keep inline content.
- **Stacking**: Use higher z-index values when sheets may overlap (e.g., accounts page uses `z-[80]/z-[90]` to stack above the quick-entry sheet at `z-[60]/z-[70]`).

## Where Bottom Sheets Are Used

| Page | Sheets | Names |
|------|--------|-------|
| Accounts (`accounts.html`) | 4 | `create-sheet`, `delete-sheet`, `account-sheet`, `edit-sheet` |
| Account Detail (`account-detail.html`) | 2 | `edit-account`, `delete` (persistent) |
| Bottom Nav (`bottom-nav.html`) | 1 | `quick-entry` (custom: has tab bar) |
