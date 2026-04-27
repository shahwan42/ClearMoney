# Claude Code — CLI-Specific Tips

Behaviors and tools specific to Claude Code (the CLI / IDE extension). Not applicable to other agents.

## Task Tracking

Use `TaskCreate` / `TaskUpdate` / `TaskList` to break work into steps and track progress within a session:

```
TaskCreate(title="Write red test for budget service", status="pending")
TaskUpdate(id=..., status="in_progress")
TaskUpdate(id=..., status="completed")
```

Tasks are session-scoped — they don't persist across conversations. Use `.tickets/` for cross-session tracking.

## Skill Tool

Invoke project skills via `Skill(skill="<name>", args="...")`:

```
Skill(skill="commit")           # runs /commit
Skill(skill="qa-review")        # runs /qa-review
Skill(skill="tdd", args="...")  # runs /tdd with args
```

Skills are defined in `.claude/skills/`. See `slash-skills.md` for the full list.

## Agent Tool

Spawn sub-agents for parallel or isolated work:

```python
Agent(
    description="Explore codebase for X",
    subagent_type="Explore",
    prompt="Find all views that handle transaction creation...",
)
```

Available types: `Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `statusline-setup`.

Use `run_in_background=True` for independent tasks; await results for dependent ones.

## Hooks

Hooks run shell commands on lifecycle events (tool calls, session start/stop). Configured in `.claude/settings.json` under `hooks`. See `.claude/rules/` (actually `.ai/rules/`) for any hook-specific setup notes.

Key hooks in this project:
- `session-start.sh` — starts PostgreSQL in remote environments
- `cbm-code-discovery-gate` — blocks Read/grep on code files, redirects to codebase-memory MCP

## Auto Memory

Persist cross-session facts via Write to `~/.claude/projects/…/memory/`:

```
Write(file_path="~/.claude/projects/.../memory/user_role.md", content="...")
```

See memory MEMORY.md index for what's already saved.

## ScheduleWakeup

Use `ScheduleWakeup` (not sleep) to self-pace recurring work. Prompt cache TTL is 5 min; sleep under 270s stays warm.

## Autonomous Mode

When `/auto` is active: execute immediately, minimize interruptions. Still confirm for irreversible/destructive ops.

## Caveman Mode

`/caveman` or `Skill(skill="caveman")` enables terse response mode (~75% token reduction). Levels: `lite`, `full`, `ultra`. Reset: "stop caveman" or "normal mode".
