# Claude Code — Slash Skills Reference

Available skills in this project. Invoke via `Skill` tool or type `/<name>` in prompt.

## Development Workflow

| Skill | When to use |
|-------|-------------|
| `/commit` | Stage and commit with conventional commit message |
| `/review` | Code review of current changes — bugs, edge cases, security |
| `/qa-review` | QA review — test gaps, edge cases, functional, data, cleanup categories |
| `/simplify` | Review changed code for reuse, quality, efficiency; fix issues found |
| `/tdd` | Red-green-refactor loop for a feature or bug fix |
| `/deploy` | Deploy to production via `make deploy` |

## Research & Planning

| Skill | When to use |
|-------|-------------|
| `/codebase-memory` | Structural code queries via knowledge graph |
| `/init` | Initialize a new CLAUDE.md with codebase documentation |
| `/request-refactor-plan` | Plan a refactor via user interview; file as GitHub issue |
| `/grill-me` | Interview the user about a plan/design until shared understanding |
| `/design-an-interface` | Generate multiple radically different interface designs |

## QA & Testing

| Skill | When to use |
|-------|-------------|
| `/qa-manual` | Run a manual QA session for ClearMoney |
| `/triage-issue` | Triage a bug by exploring codebase → create GitHub issue with TDD fix plan |

## Continuous / Scheduled

| Skill | When to use |
|-------|-------------|
| `/loop [interval]` | Run a prompt on a recurring interval (self-paced if interval omitted) |
| `/schedule` | Create/manage scheduled remote agents (cron or one-time) |

## Reviews

| Skill | When to use |
|-------|-------------|
| `/ultrareview` | Multi-agent cloud review of current branch or `/ultrareview <PR#>` for a GitHub PR. User-triggered, billed; cannot be launched autonomously. Needs git repo. |
| `/caveman-review` | Ultra-compressed code review comments |
| `/security-review` | Security review of pending changes on current branch |

## Tooling / Config

| Skill | When to use |
|-------|-------------|
| `/update-config` | Configure Claude Code settings.json (hooks, permissions, env vars) |
| `/keybindings-help` | Customize keyboard shortcuts in `~/.claude/keybindings.json` |
| `/fewer-permission-prompts` | Scan transcripts and add allowlist to reduce prompts |
| `/caveman` | Ultra-compressed communication mode (saves ~75% tokens) |

## Figma Integration

| Skill | When to use |
|-------|-------------|
| `/figma:figma-implement-design` | Translate Figma designs to production code |
| `/figma:figma-generate-design` | Translate app page/view into Figma |
| `/figma:figma-generate-library` | Build/update design system in Figma from codebase |
| `/figma:figma-code-connect` | Create/maintain Figma Code Connect mappings |
| `/figma:figma-use` | Prerequisite before every `use_figma` tool call |
| `/figma:figma-create-design-system-rules` | Generate custom design system rules |

## htmx

| Skill | When to use |
|-------|-------------|
| `/htmx-expert` | htmx development help (attributes, AJAX interactions, patterns) |
