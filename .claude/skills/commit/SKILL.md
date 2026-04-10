---
name: commit
description: Stage and commit changes with a conventional commit message
disable-model-invocation: false
---

Create a git commit for the current changes:

1. Run `git status` and `git diff` to understand what changed
2. Run `git log --oneline -5` to match the repo's commit message style
3. Stage the relevant files (prefer specific files over `git add -A`)
4. Write a conventional commit message: `type: concise description` (under ~72 chars)
   - `feat:` new feature — `fix:` bug fix — `refactor:` code restructure — `docs:` documentation — `chore:` tooling/config — `test:` test additions
5. End the commit message with: `Co-Authored-By: <WHAT'S YOUR NAME?>`
6. Run `git status` after to verify success

Do NOT push to the remote unless explicitly asked.
