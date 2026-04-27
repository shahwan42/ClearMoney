---
globs: "backend/**/*.py"
---
# Django Coding Conventions

## Style

- **Prefer `pyproject.toml`** for all Python tool configuration (pytest, coverage, mypy, ruff, etc.).
  - Root workspace: `/pyproject.toml` defines workspace members (`backend` + `e2e`)
  - Per-project config: `backend/pyproject.toml` (pytest, ruff, mypy, coverage) and `e2e/pyproject.toml` (Playwright pytest config)
  - Unified venv: `.venv` at repo root, created by `uv sync`; all dependencies managed by root `uv.lock`
- **Always set `db_table`** in every model's `Meta` class. All models live in `core/models.py`.
- **Write clean, Pythonic code** — list/dict comprehensions, f-strings, context managers, PEP 8.
- **Always add type annotations** — every function needs parameter types and return type. Use `AuthenticatedRequest` (from `core.types`) instead of `HttpRequest` in views. Run `uv run mypy .` from `backend/` to verify — zero errors required.
- **Document on every level**: module-level docstring → class-level for non-obvious classes → inline comments only where logic isn't self-evident.

## Code Formatting

Use `make format` to auto-format all Python code:

```bash
make format    # Runs ruff format + ruff check --fix (modifies files in-place)
make lint      # Verify formatting + linting + type checking (read-only check)
```

**When to use:**
- After writing code: `make format` to auto-fix style issues
- Before committing: `make lint` to verify zero errors
- Never manually fix formatting — let ruff handle it

**Important:** If files are already staged and ruff modifies them (e.g., formatting line wraps), **re-stage the formatted files before committing**:
```bash
git add <modified-files>    # Re-stage after ruff format
git commit -m "..."
```
If you forget, amend the commit: `git add <files> && git commit --amend --no-edit`

**Ruff rules:**
- Line length: 88 characters
- Import sorting: isort-compatible
- Python target: 3.12

## After Completing a Task

Always run tests and do a code review before declaring done:

- `make test` (Django unit tests)
- `make format` (auto-format code)
- `make lint` (ruff + mypy — zero errors required)
- Code review: check all changed files for bugs, edge cases, test gaps

## Commit Messages

Use conventional commits: `type: concise description` (under ~72 chars)

- `feat:` new feature — `fix:` bug fix — `refactor:` code restructure — `docs:` documentation — `chore:` tooling/config — `test:` test additions

## Error Handling Conventions

### Exception Hierarchy

| Exception | Use When |
|-----------|----------|
| `ValueError` | Validation failures (invalid input, business rule violations) |
| `ObjectDoesNotExist` | Resource not found (from `django.core.exceptions`) |
| `IntegrityError` | Database constraint violations (let bubble — do not catch) |

### Service Layer Rules

**CRUD operations:**
- Raise `ValueError` for validation errors (missing fields, invalid values, business rule violations)
- Raise `ObjectDoesNotExist` for "not found" — callers handle via view-level error responses
- Let `IntegrityError` bubble up uncaught — it signals critical data issues

**Batch operations:**
- Log errors and continue (partial success is acceptable)
- Aggregate errors for a final summary, do not raise on first failure

**Background jobs (management commands, startup jobs):**
- Catch all exceptions, log with context, continue processing
- Never let one failing item halt the entire job

### Anti-patterns to Avoid

- **Do not** return error strings or `None` from service methods — always raise an exception
- **Do not** catch bare `Exception` in service CRUD methods — catch specific exceptions only
- **Do not** use generic error messages — include identifiers (ID, field name) for debugging

### Example

```python
# Good
def delete(self, account_id: str) -> None:
    count, _ = self._qs().filter(id=account_id).delete()
    if count == 0:
        raise ObjectDoesNotExist(f"Account not found: {account_id}")
    logger.info("account.deleted id=%s", account_id)

# Bad
def delete(self, account_id: str) -> str | None:
    try:
        count, _ = self._qs().filter(id=account_id).delete()
        if count == 0:
            return "account not found"
        return None
    except IntegrityError:
        raise
```
