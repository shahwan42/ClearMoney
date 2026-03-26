# Accessibility Developer Checklist

Use this checklist when adding new features or modifying existing pages to maintain WCAG 2.1 AA compliance.

---

## Pre-Implementation Checklist

- [ ] Review ARIA patterns in `docs/accessibility/ARIA_PATTERNS_IMPLEMENTED.md`
- [ ] Identify which pattern applies to your feature
- [ ] Copy pattern from documented examples
- [ ] Ensure semantic HTML foundation (before adding ARIA)

---

## HTML & Semantic Structure

- [ ] Use semantic tags: `<main>`, `<nav>`, `<form>`, `<button>`, `<a>`, etc.
- [ ] Avoid `<div onclick="">` — use `<button>` for clickable content
- [ ] Heading hierarchy is correct: H1 → H2 → H3 (no skipping levels)
- [ ] Page has one `<h1>` title
- [ ] `<html lang="en">` is set
- [ ] `<form>` wraps all form controls

---

## Form Accessibility

### Labels
- [ ] Every input has associated `<label for="">` OR `aria-label`
- [ ] `id` on input matches `for` on label
- [ ] Label text is descriptive (not "Field")
- [ ] Icon-only inputs have `aria-label`

### Validation
- [ ] Required fields marked with `required` attribute
- [ ] Error messages use `role="alert"`
- [ ] Error message includes TEXT (not color-only)
- [ ] Error linked to field with `aria-describedby` (optional, but recommended)
- [ ] Form doesn't auto-submit on field change

### Structure
- [ ] Radio groups wrapped in `<fieldset>` with `<legend>`
- [ ] Checkbox groups properly labeled
- [ ] Submit button clearly labeled (not "Send" or "Go")

---

## Color & Contrast

### Text Contrast (WCAG 1.4.3)
- [ ] All text vs. background: minimum 4.5:1 ratio
- [ ] Test in **light mode** with contrast checker
- [ ] Test in **dark mode** with contrast checker
- [ ] Focus indicators: minimum 3:1 contrast
- [ ] Placeholder text (if conveys meaning): 4.5:1 contrast

### Non-Text Contrast (WCAG 1.4.11)
- [ ] Focus rings: minimum 3:1 contrast
- [ ] Borders: minimum 3:1 contrast
- [ ] Icons: minimum 3:1 contrast (if meaningful)

### Use Tools
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- Browser DevTools: Chrome, Firefox (Accessibility Inspector)

---

## Focus & Keyboard Navigation

### Focus Indicators
- [ ] All interactive elements have visible focus indicator
- [ ] Focus ring is minimum 2px
- [ ] Focus visible in BOTH light and dark modes
- [ ] Use Tailwind: `focus:ring-2 focus:ring-teal-500`

### Tab Order
- [ ] Tab order is logical (left-to-right, top-to-bottom)
- [ ] No focus jumps unexpectedly
- [ ] No elements skip in tab order
- [ ] Negative `tabindex` only for justified reasons

### Keyboard Support
- [ ] All buttons/links work with Enter key
- [ ] All form controls accessible via keyboard
- [ ] Dropdowns work with Arrow keys (Up/Down)
- [ ] Modals can be closed with Escape key
- [ ] No keyboard traps (user can't get stuck tabbing)

### First Tab Stop
- [ ] Skip-to-content link is first focusable element
- [ ] Or first interactive element on page

---

## ARIA Implementation

### Button Toggles
```html
<button aria-pressed="false" aria-label="Toggle dark mode">
    🌙
</button>
```
- [ ] Toggle buttons have `aria-pressed` attribute
- [ ] Value updates when state changes: `aria-pressed="true/false"`

### Icon-Only Buttons/Links
```html
<button aria-label="Close menu">
    <svg aria-hidden="true"><!-- icon --></svg>
</button>
```
- [ ] Icon-only buttons have `aria-label`
- [ ] SVG icons have `aria-hidden="true"` (if decorative)
- [ ] Label describes PURPOSE, not just "Button"

### Dropdown/Menu Triggers
```html
<button aria-label="Menu" aria-haspopup="menu">
    Options
</button>
```
- [ ] `aria-haspopup` on trigger button
- [ ] `aria-expanded` on trigger (optional but recommended)

### Dialogs/Modals
```html
<div role="dialog" aria-modal="true" aria-label="Title">
    <!-- Content -->
</div>
```
- [ ] Modal has `role="dialog"`
- [ ] Modal has `aria-modal="true"`
- [ ] Modal has `aria-label` or `aria-labelledby`
- [ ] Modal is `aria-hidden="true"` when closed
- [ ] Focus trapped inside modal when open
- [ ] Focus restored to trigger button when closed

### Form Inputs
```html
<label for="email">Email</label>
<input id="email" type="email" required>
```
- [ ] All inputs have labels
- [ ] Explicit `<label for="">` association
- [ ] `id` matches `for` attribute

### Live Regions
```html
<div aria-live="polite" aria-atomic="true">
    <!-- Dynamic content -->
</div>
```
- [ ] Success messages: `aria-live="polite"` (non-critical)
- [ ] Error messages: `aria-live="assertive"` (critical)
- [ ] Use `role="alert"` for errors (implicit assertive)
- [ ] Don't overuse (avoid alert fatigue)

### Navigation & Current Page
```html
<nav aria-label="Main navigation">
    <a href="/" aria-current="page">Home</a>
    <a href="/other">Other</a>
</nav>
```
- [ ] Navigation wrapped in `<nav>`
- [ ] Navigation has `aria-label` (if multiple navs)
- [ ] Current page marked with `aria-current="page"`
- [ ] Only ONE `aria-current="page"` per page

---

## Semantic HTML

### Landmarks
- [ ] Page has `<main>` for primary content
- [ ] Page has `<nav>` for navigation
- [ ] Page has `<header>` for site header (optional)
- [ ] Page has `<footer>` for site footer (optional)

### Links vs. Buttons
- [ ] Links go to pages: `<a href="...">Text</a>`
- [ ] Buttons perform actions: `<button onclick="...">Text</button>`
- [ ] Don't use `<a>` with `onclick` (use `<button>`)
- [ ] Don't use `<div>` as button (use `<button>`)

### Headings
- [ ] Headings have semantic `<h1>`, `<h2>`, `<h3>` tags
- [ ] Heading hierarchy starts at H1, doesn't skip levels
- [ ] Don't use headings for styling (use CSS instead)

---

## Dynamic Content

### HTMX / JavaScript Updates
- [ ] Updates announced to screen readers
- [ ] Use `aria-live="polite"` on updating regions
- [ ] Or use `role="alert"` for errors
- [ ] Don't update content while user focuses elsewhere (distraction)

### Loading States
- [ ] Add `aria-busy="true"` during loading
- [ ] Remove when complete
- [ ] Show loading spinner with text label

### Modal Sheet Opening
- [ ] Set initial `aria-hidden="true"`
- [ ] Change to `aria-hidden="false"` when open
- [ ] Focus first interactive element
- [ ] Trap focus inside modal
- [ ] Close with Escape

---

## Testing Checklist

### Keyboard Navigation Test
- [ ] Tab through entire page
- [ ] Verify logical order
- [ ] Verify focus visible on each element
- [ ] Verify focus doesn't disappear
- [ ] Test Escape to close modals
- [ ] Test Enter to submit forms
- [ ] Test Arrow keys on menus

### Screen Reader Test
- [ ] Test with browser accessibility inspector
- [ ] All interactive elements announced
- [ ] Form labels associated and announced
- [ ] Button purposes clear
- [ ] Error messages announced
- [ ] Live regions announced
- [ ] Page structure (landmarks, headings) announced

### Color Contrast Test
- [ ] Test in light mode
- [ ] Test in dark mode
- [ ] Use contrast checker tool
- [ ] All text ≥4.5:1
- [ ] All focus rings ≥3:1
- [ ] All borders ≥3:1

### Touch Target Size Test
- [ ] All buttons ≥44×44px
- [ ] All links ≥44×44px
- [ ] All inputs ≥44px height
- [ ] Adequate spacing between targets

### Responsive Test
- [ ] Test at 375px (mobile)
- [ ] Test at 768px (tablet)
- [ ] Test at 1920px (desktop)
- [ ] No horizontal scroll
- [ ] Touch targets maintained
- [ ] Text readable

### Zoom Test
- [ ] Zoom to 200%
- [ ] Content readable
- [ ] No horizontal scroll
- [ ] Focus indicators visible
- [ ] All interactive elements accessible

---

## Code Review Checklist

When reviewing a PR, check:

- [ ] Added semantic HTML first (before any ARIA)
- [ ] All form inputs have labels
- [ ] Focus indicators visible on interactive elements
- [ ] ARIA patterns match documented examples
- [ ] Icon-only buttons have aria-label
- [ ] Error messages include text (not color-only)
- [ ] Live regions use aria-live correctly
- [ ] Modals trap focus and support Escape
- [ ] Keyboard navigation works
- [ ] No color-only indicators
- [ ] Sufficient color contrast
- [ ] Tests include accessibility checks

---

## Common Mistakes to Avoid

| ❌ Wrong | ✅ Right |
|---------|----------|
| `<div onclick="">` | `<button>` |
| `<span role="button">` | `<button>` |
| Icon without aria-label | `aria-label="Purpose"` |
| Error by color only | Text + border + color |
| Focus ring: 1px | Focus ring: 2px minimum |
| `aria-label` on visible text | `<label for="">` on input |
| Nested interactive elements | One button inside another = bad |
| `aria-hidden` on content users need | Only on decorative icons |
| Modal without role="dialog" | `role="dialog" aria-modal="true"` |
| No focus trap on modal | Tab/Shift-Tab wraps inside modal |
| Placeholder as label | `<label>` + `placeholder` |
| No skip link | Skip-to-content as first element |
| Tab order: -1 on everything | Use tabindex only when necessary |
| Keyboard events on divs | Use semantic `<button>` or `<a>` |

---

## Template Copy-Paste Examples

### Icon-Only Button
```html
<button aria-label="Toggle dark mode" onclick="toggleTheme()">
    🌙
</button>
```

### Form Input
```html
<label for="email">Email</label>
<input type="email" id="email" name="email" required>
```

### Error Message
```html
<div role="alert" class="text-red-700">
    Email is required
</div>
```

### Modal Dialog
```html
<div role="dialog" aria-modal="true" aria-label="Confirm Delete">
    <h2>Confirm</h2>
    <p>Are you sure?</p>
    <button>Cancel</button>
    <button>Delete</button>
</div>
```

### Navigation
```html
<nav aria-label="Main navigation">
    <a href="/" aria-current="page">Home</a>
    <a href="/about">About</a>
</nav>
```

### Form with Fieldset
```html
<fieldset>
    <legend>Account Type</legend>
    <label><input type="radio" name="type"> Checking</label>
    <label><input type="radio" name="type"> Savings</label>
</fieldset>
```

---

## Resources

- [WCAG 2.1 Overview](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [MDN Web Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [WebAIM Articles](https://webaim.org/articles/)
- [Deque Color Contrast Analyzer](https://www.deque.com/color-contrast/)

---

## Questions?

Refer to:
1. `docs/accessibility/ARIA_PATTERNS_IMPLEMENTED.md` — See implemented patterns
2. `WCAG_AA_AUDIT_SUMMARY.md` — See what's required
3. Existing code — Copy patterns from similar features

**Standard:** WCAG 2.1 Level AA
**Status:** Production-Ready
**Last Updated:** 2026-03-26
