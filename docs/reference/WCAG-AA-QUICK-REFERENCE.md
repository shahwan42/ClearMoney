# WCAG 2.1 Level AA — Quick Reference

Fast lookup for common accessibility compliance issues and fixes. Use when implementing WCAG AA improvements.

## Core Principles

**POUR** — Perceivable, Operable, Understandable, Robust

## Level AA Criteria (Essential)

### 1. Perceivable — Users must perceive the content

#### 1.1.1 Non-text Content
**Issue:** Images, icons, charts without alternative text
**Fix:**
- Images: `<img alt="description">`
- Icon buttons: `<button aria-label="Icon text">🔍</button>`
- SVG charts: `<svg><title>Chart Title</title><desc>Data description</desc></svg>`
- Charts (CSS): Provide hidden data table: `<table style="display:none;" aria-label="Chart data">`

**Test:** `mcp__playwright__browser_snapshot` — verify alt text present

---

#### 1.3.1 Info and Relationships
**Issue:** Form inputs without labels, list structures unclear
**Fix:**
- Form inputs: `<label for="email">Email</label><input id="email">`
- Alternative: `<input aria-label="Email">`
- Radio groups: `<fieldset><legend>Options</legend><input type="radio"></fieldset>`
- Proper heading hierarchy: `<h1>`, `<h2>`, etc. (skip no levels)

**Test:** `make test` includes label validation; `browser_snapshot` shows labels

---

#### 1.4.3 Contrast (Minimum)
**Issue:** Text/background color ratio < 4.5:1
**Target Ratios:**
- **Normal text:** 4.5:1 (AA standard)
- **Large text (18pt+):** 3:1
- **Icons/borders:** 3:1 (non-text contrast)

**Fix:**
1. Use [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
2. Verify in both light AND dark modes
3. Test computed colors: `browser_evaluate(() => window.getComputedStyle(element).color)`
4. Common fixes:
   - Focus ring: use higher contrast color (not gray)
   - Placeholder text: dark gray (gray-600+), not light gray (gray-400)
   - Disabled buttons: ensure 3:1 distinction from enabled

**Test:** Take screenshots in both modes; verify no gray text on light backgrounds

---

#### 1.4.11 Non-text Contrast
**Issue:** Icons, buttons, borders lack sufficient contrast
**Target:** 3:1 minimum for all visual components
**Fix:**
- Icon colors: ensure sufficient contrast against background
- Border colors: darken or lighten to meet 3:1
- Chart colors: test each segment for 3:1 against background

**Test:** `browser_evaluate()` to check computed colors

---

### 2. Operable — Users must operate the interface

#### 2.1.1 Keyboard
**Issue:** Feature requires mouse (swipe, hover, drag without alternative)
**Fix:**
- All functionality available via keyboard
- Provide button alternative for swipe gestures
- Implement keyboard shortcuts (?, Menu key, etc.)
- Ensure Tab works on all interactive elements

**Test:**
- `browser_press_key("Tab")` — navigate all elements
- `browser_press_key("Enter")` — activate buttons
- `browser_press_key("ArrowDown")` — navigate dropdowns

---

#### 2.4.3 Focus Order
**Issue:** Tab order illogical (jumps around, backwards, off-screen)
**Fix:**
- Remove custom tabindex unless necessary (let DOM order dictate)
- If custom tabindex needed: tabindex="0" (last in order), never positive tabindex
- Focus order: left-to-right, top-to-bottom
- Modals: trap focus (first focusable → Tab → last focusable → Tab → first again)

**Test:**
- Tab through page with `browser_press_key("Tab")`
- Inspect with `browser_snapshot` — verify focus moves logically
- Modal test: verify Tab doesn't escape, Escape closes

---

#### 2.4.7 Focus Visible
**Issue:** Focus indicator invisible or hard to see
**Target:** 2px outline, 3:1 contrast minimum
**Fix:**
```css
/* Tailwind: use focus-visible, not focus */
button:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
}

/* Or use focus ring with sufficient contrast */
input:focus {
  border: 2px solid #000; /* or accent color with 3:1 contrast */
  box-shadow: 0 0 0 3px rgba(0, 0, 255, 0.5);
}
```

**Test:**
- `browser_press_key("Tab")` — visually confirm outline appears
- Screenshot to verify outline contrast
- Check `browser_snapshot` — focus element identified

---

### 3. Understandable — Users must understand the content

#### 3.3.1 Error Identification
**Issue:** Form errors indicated by color alone, not announced
**Fix:**
- Error message text: "Email is required"
- Visual: red border + error icon (not color alone)
- Link error to input: `aria-describedby="error-msg"`
- Announce errors: `role="alert"` on error container
```html
<input aria-describedby="email-error">
<div id="email-error" role="alert">Email is required</div>
```

**Test:**
- Submit form with invalid data
- Verify error text visible
- Check `browser_snapshot` — aria-describedby linked, alert role present

---

#### 3.3.4 Error Prevention
**Issue:** Destructive action (delete) without confirmation
**Fix:**
- Add confirmation dialog before delete
- Modal should ask: "Are you sure you want to delete [item]?"
- Include "Cancel" and "Delete" buttons

**Test:** Attempt delete; confirm modal appears

---

### 4. Robust — Content works across technologies

#### 4.1.2 Name, Role, Value
**Issue:** Interactive element lacks accessible name, role, or state
**Fix:**
- Buttons: text visible or `aria-label`
- Icon buttons: ALWAYS `aria-label` if no text
- Toggles/switches: `aria-pressed="true/false"` or `aria-checked="true/false"`
- Links: descriptive text or `aria-label`
- Dropdowns: `aria-haspopup="menu"` + `aria-expanded="true/false"`

```html
<!-- Icon button -->
<button aria-label="Close menu">✕</button>

<!-- Toggle -->
<button aria-pressed="false">Dark Mode</button>

<!-- Dropdown -->
<button aria-haspopup="menu" aria-expanded="false">Options</button>
<menu role="menu">
  <menuitem>Edit</menuitem>
  <menuitem>Delete</menuitem>
</menu>
```

**Test:** `browser_snapshot` — verify aria-label, role, state attributes present

---

#### 4.1.3 Status Messages
**Issue:** Dynamic updates not announced (balance change, notification, error)
**Fix:**
- Use `aria-live` on container that updates dynamically
- `aria-live="polite"` — announce after user stops interacting
- `aria-live="assertive"` — announce immediately (errors, alerts)
- `aria-atomic="true"` — announce entire region, not just changes

```html
<!-- Toast notifications -->
<div aria-live="assertive" aria-atomic="true" role="alert">
  Payment sent successfully
</div>

<!-- Balance updates (less urgent) -->
<div aria-live="polite" id="balance">
  Current balance: $1,234.56
</div>
```

**Test:**
- Trigger update with button click
- Verify `browser_snapshot` shows aria-live region updated
- Use screen reader to verify announcement

---

## ARIA Patterns for Common Components

### Form Input
```html
<label for="email">Email Address</label>
<input id="email" type="email" required aria-describedby="email-hint">
<small id="email-hint">We'll never share your email</small>
```

### Modal / Dialog
```html
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Confirm Delete</h2>
  <p>Are you sure?</p>
  <button autofocus>Cancel</button>
  <button>Delete</button>
</div>
```

### Dropdown Menu
```html
<button aria-haspopup="menu" aria-expanded="false" aria-controls="menu">
  Options
</button>
<menu id="menu" role="menu">
  <menuitem role="menuitem">Edit</menuitem>
  <menuitem role="menuitem">Delete</menuitem>
</menu>
```

### Navigation
```html
<nav aria-label="Main">
  <a href="/" aria-current="page">Home</a>
  <a href="/accounts">Accounts</a>
  <a href="/settings">Settings</a>
</nav>
```

### Toggle / Switch
```html
<button role="switch" aria-checked="false" aria-label="Dark Mode">
  Light
</button>
```

### Tabs
```html
<div role="tablist">
  <button role="tab" aria-selected="true" aria-controls="panel-1">Tab 1</button>
  <button role="tab" aria-selected="false" aria-controls="panel-2">Tab 2</button>
</div>
<div id="panel-1" role="tabpanel">Content 1</div>
<div id="panel-2" role="tabpanel">Content 2</div>
```

---

## Testing Tools & Workflows

### Browser Tools
- **Accessibility Inspector** (DevTools → Elements → Accessibility pane)
- **Contrast Checker:** [WebAIM](https://webaim.org/resources/contrastchecker/)
- **Keyboard Testing:** Tab, Shift-Tab, Arrow keys, Escape, Enter
- **Screen Reader Simulation:** `browser_snapshot` shows ARIA tree

### Claude Code Tools
```bash
mcp__playwright__browser_snapshot          # ARIA tree inspection
mcp__playwright__browser_take_screenshot   # Visual verification
mcp__playwright__browser_press_key("Tab")  # Keyboard nav testing
mcp__playwright__browser_evaluate()        # Check DOM, colors, focus
```

### Automated Checks
```bash
make test                    # Unit tests for ARIA attributes
make test-e2e                # Playwright tests for interaction
/qa-review                   # AI quality review for gaps
```

---

## Common Fixes Summary

| Issue | WCAG | Fix |
|-------|------|-----|
| Missing label on input | 1.3.1 | Add `<label for="">` or `aria-label` |
| Color contrast too low | 1.4.3 | Increase contrast to 4.5:1 (text) or 3:1 (non-text) |
| Icon button no label | 1.1.1 | Add `aria-label` |
| Focus indicator invisible | 2.4.7 | Add 2px outline with 3:1 contrast |
| Error by color only | 3.3.1 | Add text + border, link via aria-describedby |
| Modal no focus trap | 2.4.3 | Trap focus, set initial focus, Escape to close |
| Dropdown not keyboard accessible | 2.1.1 | Add arrow key navigation, Tab to open |
| Dynamic update not announced | 4.1.3 | Add aria-live="polite" or "assertive" |
| No skip-to-content link | 2.4.1 | Add hidden skip link, keyboard accessible |
| Placeholder no label | 1.3.1 | Add `<label>` in addition to placeholder |

---

## Pre-Commit Accessibility Checklist

Before committing any accessibility fix:

- [ ] Form inputs: all have labels (visible or aria-label)
- [ ] Interactive elements: all have role and aria-label
- [ ] Modals: role="dialog", aria-modal="true", aria-labelledby
- [ ] Dynamic content: aria-live present if announced
- [ ] Contrast: 4.5:1 text, 3:1 non-text (both light + dark modes)
- [ ] Focus: 2px outline, 3:1 contrast, visible
- [ ] Keyboard: Tab/Shift-Tab, Enter, Arrow keys, Escape all work
- [ ] Tests: failing test written first, implementation passes
- [ ] `make test && make test-e2e && make lint` all pass

---

## Further Reading

- [WCAG 2.1 Official](https://www.w3.org/WAI/WCAG21/quickref/)
- [WebAIM Articles](https://webaim.org/articles/)
- [MDN ARIA Guide](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA)
- [ClearMoney Rules: accessibility.md](./../.claude/rules/accessibility.md)
- [ClearMoney Protocol: accessibility-qa-protocol.md](./../.claude/rules/accessibility-qa-protocol.md)
