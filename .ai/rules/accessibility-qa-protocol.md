# Accessibility QA Protocol — WCAG AA Testing

Structured verification protocol for validating accessibility fixes before commit. Use this for any ARIA, keyboard, or contrast changes.

## Verification Gates (Run Before Commit)

```bash
mcp__django-ai-boost__run_check   # Django check (Claude Code) or: python manage.py check
make lint                          # ruff + mypy — zero errors required
make test                          # all tests pass
make test-e2e                      # Playwright tests pass
```

## Per-Improvement QA Checklist

### 1. Accessibility Tree Inspection

Use `mcp__playwright__browser_snapshot` (Claude Code) or browser DevTools accessibility panel to inspect ARIA tree:

- ✓ All form inputs have associated labels (visible `<label>` or `aria-label`)
- ✓ All interactive elements have semantic roles (button, link, menuitem, etc.)
- ✓ All ARIA attributes present and correct (aria-pressed, aria-expanded, aria-live, aria-modal, etc.)
- ✓ No duplicate IDs or broken aria-labelledby references
- ✓ Modal has `role="dialog"`, `aria-modal="true"`, `aria-labelledby`

### 2. Keyboard Navigation Testing

Use `mcp__playwright__browser_press_key` (Claude Code) or manually tab through the page in browser:

- ✓ Tab key traverses all interactive elements in logical order (left-to-right, top-to-bottom)
- ✓ Focus indicator visible (2px outline minimum, 3:1+ contrast against background)
- ✓ Shift+Tab reverses order
- ✓ Arrow keys navigate dropdowns/menus (↑↓ moves between options, ← → closes)
- ✓ Enter activates buttons/links
- ✓ Escape closes modals/dropdowns
- ✓ Modal focus trapped (Tab doesn't escape, Escape closes)
- ✓ Check `mcp__playwright__browser_console_messages` (Claude Code) or browser DevTools console — zero JS errors

### 3. Color Contrast Validation

For each color pair (text + background):

- ✓ **Text/background**: 4.5:1 minimum for normal text, 3:1 for large text (18pt+)
- ✓ **Focus ring**: 4.5:1 contrast against surrounding colors
- ✓ **Placeholder text**: 4.5:1 if it conveys meaning
- ✓ **Icons/borders**: 3:1 non-text contrast
- ✓ **Both light and dark modes**: test both themes

**Testing approach:**
```javascript
// In browser_evaluate:
const element = document.querySelector('selector');
const style = window.getComputedStyle(element);
const bgColor = style.backgroundColor;
const textColor = style.color;
// Compare with online contrast checker: https://webaim.org/resources/contrastchecker/
```

### 4. Screen Reader Validation

Use accessibility inspector in browser (or simulate with `browser_snapshot`):

- ✓ Form labels announced (not just visually present)
- ✓ Error messages announced via `role="alert"` or `aria-live="assertive"`
- ✓ Button purposes clear from aria-label + text
- ✓ Active navigation items: `aria-current="page"` announced
- ✓ Toggle/switch states: aria-pressed/aria-checked announced

### 5. Visual Confirmation

- ✓ `mcp__playwright__browser_take_screenshot` (Claude Code) or capture screenshot manually — light mode
- ✓ Toggle dark mode: `browser_evaluate(() => document.documentElement.classList.toggle('dark'))`
- ✓ Screenshot again — verify dark mode contrast
- ✓ Zoom to 200%: `browser_evaluate(() => document.body.style.zoom = '2.0')`
  - No horizontal scrolling
  - All interactive elements remain accessible
  - Text readable

### 6. Mark Complete

Update TodoWrite with this improvement marked done, then commit:

```bash
git add <specific files only>
git commit -m "fix: [WCAG criterion] - [specific improvement]"
```

## Common WCAG AA Criteria Reference

| Criterion | Issue | Verification |
|-----------|-------|--------------|
| 1.1.1 Non-text Content | Missing alt/aria-label on images/icons | `mcp__playwright__browser_snapshot` (Claude Code) or browser accessibility inspector |
| 1.3.1 Info and Relationships | Unlabeled form inputs | All inputs have `<label for="">` or `aria-label` |
| 1.4.3 Contrast (Minimum) | Text/background < 4.5:1 | Contrast checker confirms 4.5:1+ |
| 1.4.11 Non-text Contrast | Borders/icons < 3:1 | Contrast checker confirms 3:1+ |
| 2.1.1 Keyboard | Feature not keyboard accessible | Tab/arrow/Enter/Escape work as expected |
| 2.4.3 Focus Order | Tab order illogical/jumps | Focus moves left-to-right, top-to-bottom |
| 2.4.7 Focus Visible | Focus indicator invisible | 2px outline, 3:1 contrast visible |
| 3.3.1 Error Identification | Errors by color only | Text + border highlight, not color alone |
| 4.1.2 Name, Role, Value | Interactive element lacks label | aria-label + role present |
| 4.1.3 Status Messages | Dynamic updates not announced | `aria-live="polite"` or `"assertive"` on container |

## Autonomous Error Recovery

**Tests fail (>3 attempts):**
- Use `browser_snapshot` to inspect actual ARIA tree
- Verify HTML structure — ARIA attributes on correct elements
- Check `WebFetch` for WCAG spec: is aria-labelledby pointing to valid ID?
- Run `mcp__django-ai-boost__run_check` (Claude Code) or `python manage.py check` for Django errors

**Contrast issues:**
- Use [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- Test computed colors with `browser_evaluate()`
- If color system is inconsistent, consider CSS custom properties

**Keyboard nav broken:**
- Use `browser_press_key("Tab")` repeatedly, inspect with `browser_snapshot()`
- Verify all interactive elements are focusable (no negative tabindex without reason)
- Check z-index — focus indicators may be hidden behind other elements
- Ensure modals set initial focus: `element.focus()`

**Lint/mypy errors:**
- ARIA attributes are HTML, not Python — mypy won't error
- Verify Jinja2 template syntax (quotes, closing tags)
- Run `make lint` to catch template issues

## Success Criteria

✅ All form inputs have labels
✅ All interactive elements keyboard accessible
✅ All focus indicators visible and 3:1+ contrast
✅ All text/background pairs 4.5:1+ contrast
✅ All modals have focus management + Escape to close
✅ All error messages linked via aria-describedby or role="alert"
✅ `make test && make test-e2e && make lint` all pass
✅ Browser console has zero errors
✅ Both light and dark modes compliant
