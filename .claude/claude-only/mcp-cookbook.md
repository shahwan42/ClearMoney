# Claude Code — MCP Tool Cookbook

Quick reference for MCP tools available in this project.

## django-ai-boost (Django project introspection)

| Tool | Use |
|------|-----|
| `mcp__django-ai-boost__run_check` | Django system check — faster than `make lint` for just checks |
| `mcp__django-ai-boost__list_models` | Fast schema lookup — prefer over reading `core/models.py` |
| `mcp__django-ai-boost__list_migrations` | Check applied/pending migrations |
| `mcp__django-ai-boost__list_urls` | Verify routes are registered |
| `mcp__django-ai-boost__list_management_commands` | See all management commands |
| `mcp__django-ai-boost__database_schema` | Full DB schema |
| `mcp__django-ai-boost__query_model` | Query a model with filters |
| `mcp__django-ai-boost__get_setting` | Read a Django setting value |
| `mcp__django-ai-boost__reverse_url` | Reverse a URL by name |
| `mcp__django-ai-boost__read_recent_logs` | Tail application logs |

## playwright (Browser automation / QA)

| Tool | Use |
|------|-----|
| `mcp__playwright__browser_navigate` | Navigate to URL |
| `mcp__playwright__browser_snapshot` | Inspect accessibility/ARIA tree |
| `mcp__playwright__browser_take_screenshot` | Capture page screenshot |
| `mcp__playwright__browser_click` | Click an element |
| `mcp__playwright__browser_fill` | Fill an input |
| `mcp__playwright__browser_evaluate` | Run JS in page context |
| `mcp__playwright__browser_press_key` | Press keyboard key (Tab, Escape, etc.) |
| `mcp__playwright__browser_console_messages` | Read browser console |
| `mcp__playwright__browser_network_requests` | Inspect network traffic |
| `mcp__playwright__browser_wait_for` | Wait for selector/event |

**Do NOT use `mcp__playwright__*` to run the E2E test suite — use `make test-e2e` instead.**

### QA Patterns

```python
# Verify ARIA tree
mcp__playwright__browser_snapshot()

# Keyboard nav
mcp__playwright__browser_press_key("Tab")
mcp__playwright__browser_press_key("Escape")

# Dark mode toggle for contrast check
mcp__playwright__browser_evaluate("document.documentElement.classList.toggle('dark')")

# 200% zoom test
mcp__playwright__browser_evaluate("document.body.style.zoom = '2.0'")
```

## codebase-memory (Knowledge graph)

| Tool | Use |
|------|-----|
| `mcp__codebase-memory-mcp__search_graph` | Find functions/classes by name pattern |
| `mcp__codebase-memory-mcp__trace_path` | Trace call chains / data flow |
| `mcp__codebase-memory-mcp__get_code_snippet` | Read source by qualified name |
| `mcp__codebase-memory-mcp__search_code` | Graph-augmented grep |
| `mcp__codebase-memory-mcp__get_architecture` | Project structure overview |
| `mcp__codebase-memory-mcp__query_graph` | Complex Cypher queries |
| `mcp__codebase-memory-mcp__index_repository` | Index repo if not yet indexed |
| `mcp__codebase-memory-mcp__index_status` | Check index freshness |

**Always use codebase-memory tools FIRST for code exploration. Fall back to Grep/Read only for text content.**

## chrome-devtools (Alternative browser)

Use `mcp__chrome-devtools__*` as alternative to playwright for browser interaction when needed.

## context7 (Library documentation)

Use `mcp__context7__query-docs` / `mcp__context7__resolve-library-id` when looking up docs for any library, framework, SDK, or CLI tool — even well-known ones. Training data may be stale.
