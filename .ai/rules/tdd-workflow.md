# TDD for All Development (RED → GREEN → Refactor)

Every code change — features, bug fixes, refactors — follows strict TDD. Write failing tests FIRST, then implement just enough to pass, then refactor. **Never skip RED**: always run the test and confirm it fails before writing implementation.

## New Features

1. **Schema & Models**: Add/modify models in `core/models.py` → `make makemigrations` → review migration → `make migrate`
2. **Service (RED → GREEN)**: Write failing tests in `<app>/tests/test_services.py` first, then implement `<app>/services.py`
3. **View & Templates (RED → GREEN)**: Write failing tests in `<app>/tests/test_views.py` first, then implement view, URL, and templates
4. **E2E & Docs**: Write Playwright tests in `e2e/tests/`; add/update docs in `docs/features/`

## Bug Fixes

1. **Reproduce (RED)**: Write a test that exposes the bug — run it and confirm it fails
2. **Fix (GREEN)**: Implement the minimal fix to make the test pass
3. **Refactor**: Clean up if needed, ensure no regressions with `make test`

## Refactors

1. **Cover (RED → GREEN)**: If the code being refactored lacks tests, write tests for current behavior first — confirm they pass
2. **Refactor**: Restructure the code — tests must stay green throughout
3. **Verify**: Run `make test` to confirm no regressions
