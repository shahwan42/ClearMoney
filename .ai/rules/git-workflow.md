# Git Workflow — Commit Practices

## Core Rules

**NEVER commit without asking first.** Always show staged changes and ask for approval before running `git commit`.

**NEVER use `git add .`** — always stage only the files relevant to the currently implemented feature or fix.

**When committing**: Only include files directly relevant to the intended change in the current chat. Ignore unrelated changes in the working directory — do not stage or commit them.

## Commit Workflow

1. **Implement and test** the feature/fix
2. **Show the user** the changes:
   ```bash
   git status
   git diff --cached
   ```
3. **Ask for approval**: "Ready to commit? Staging: [list of files]"
4. **Wait for user confirmation** before running `git commit`
5. **If unrelated files are staged**, unstage them first:
   ```bash
   git reset HEAD filename.py
   ```

## Commit Messages

Use conventional commits: `type: concise description` (under ~72 chars)

- `feat:` new feature
- `fix:` bug fix
- `refactor:` code restructure
- `docs:` documentation
- `chore:` tooling/config
- `test:` test additions

Example: `fix: ensure auth fixture depends on db fixture for proper execution order`

## Rationale

- Keeps git history clean and focused
- Makes reverting individual changes safe
- Prevents mixing unrelated work
- Allows user to control when changes are persisted
- Example: If fixing a bug in feature A, don't include files from feature B even if they're modified

## Special Cases

### Accidentally Staged Wrong Files

```bash
# Unstage a file before committing
git reset HEAD path/to/file.py

# Or see all staged changes and unstage selectively
git diff --cached
git reset HEAD  # unstage all
git add specific-file.py  # re-stage only what you want
```

### Multiple Features in Working Directory

Always commit one feature/fix at a time. If you have unrelated changes:

```bash
# Show what's modified
git status

# Only stage files for THIS change
git add backend/feature_a/models.py backend/feature_a/views.py

# Commit
git commit -m "feat: add feature A"

# Later, stage and commit feature B separately
git add backend/feature_b/...
git commit -m "feat: add feature B"
```

### Never Force Push

Avoid `git push --force` unless explicitly authorized. It can overwrite upstream work.
