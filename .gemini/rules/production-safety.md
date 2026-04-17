# Production Safety — No Breaking Changes

This application is live in production with real user data. Every change MUST be backward-compatible unless the user explicitly states otherwise.

- **Database migrations**: Additive only — NO dropping columns, renaming tables, or altering column types that break existing data. Use multi-step migrations (add new → migrate data → drop old) if schema changes are needed.
- **API/Route changes**: Do NOT remove or rename existing endpoints. Add new ones instead.
- **Config/Environment**: Do NOT remove or rename existing env vars. Add new ones with sensible defaults.
- **Dependencies**: Do NOT remove or upgrade dependencies with breaking changes without explicit approval.
- **Data integrity**: Never run destructive operations (DELETE, TRUNCATE, DROP) against production data.
- **Default behavior**: Changes that alter existing behavior must default to the current behavior unless the user opts in.

When in doubt, ask before making a change that could affect production.
