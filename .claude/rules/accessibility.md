---
globs: "backend/templates/**/*.html,static/**/*.js"
---
# ARIA Accessibility Standards

All new and modified templates/JS MUST follow these rules:

- **Dialogs/modals**: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` → title, focus trap on open, restore focus on close
- **Dropdowns**: `aria-haspopup="menu"` + `aria-expanded` on trigger; `role="menu"` on container; `role="menuitem"` on items; arrow key navigation
- **Toggles**: `aria-pressed` or `role="switch"` + `aria-checked`; active nav items: `aria-current="page"`
- **HTMX targets**: `aria-live="polite"` for updates, `"assertive"` for errors; `aria-busy="true"` during loading
- **Forms**: every input needs `<label for="">` or `aria-label`; errors use `role="alert"` + `aria-describedby`; invalid fields: `aria-invalid="true"`; radio groups: `<fieldset>` + `<legend>`
- **Icon-only buttons**: must have `aria-label`
- **CSS charts**: `aria-label` with data summary or visually-hidden data table; SVG charts: `<title>`, `<desc>`, `role="img"`
- **Touch gestures** (swipe-to-delete, pull-to-refresh): always provide a keyboard/button alternative
- **Page structure**: `<html lang="en">`, skip-to-content link, semantic landmarks (`<main>`, `<nav aria-label="...">`, etc.), toast container: `aria-live="polite"` + `aria-atomic="true"`
