# Feature Delivery Checklist

After completing a feature, follow these steps in order:

1. **Run tests** — `make test`
2. **Run e2e + lint** — `make test-e2e && make lint`
3. **Code review** — check all changed files for bugs, edge cases, test gaps
4. **QA review** — run `/qa-review` to check for test gaps across functional, state/interaction, data, and cleanup categories
5. **Update documentation** — `docs/features/` if applicable
6. **Restart the app** — `make run` so the user can try it at `http://0.0.0.0:8000`
7. **Show manual test steps** — list the exact UI steps
8. **Ask to commit** — once approved
