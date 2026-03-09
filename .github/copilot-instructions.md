# ClearMoney — GitHub Copilot Instructions

## Project
Go personal finance tracker: chi router, HTMX, Tailwind CSS, PostgreSQL. Single-user PWA.

## Architecture
Handler → Service → Repository → PostgreSQL. No ORM — raw SQL via pgx v5/database/sql.

## Patterns
- Models: plain structs with `json`/`db` tags in `internal/models/`
- Nullable fields: pointer types (`*string`, `*float64`)
- Money: `float64` in Go, `NUMERIC(15,2)` in DB
- Errors: `fmt.Errorf("context: %w", err)` for wrapping
- Logging: `log/slog` only — `authmw.Log(r.Context()).Error("msg", "key", val)` in handlers
- Auth: PIN-based with bcrypt, HMAC session cookies
- Templates: Go html/template clone-per-page pattern with HTMX

## JSON API Handlers
Use `respondError(w, r, status, message)` for errors — auto-logs with request context.

## HTML Page Handlers
Add `authmw.Log(r.Context()).Error(...)` before `http.Error()` for 500-level responses.

## Tests
Integration tests with real PostgreSQL. Factories: `testutil.CreateInstitution(t, db, ...)`. Auth: `testutil.SetupAuth(t, db)`.

## Feature Addition Order
Migration → Model → Repository → Service → Handler → Template → Tests → Wire in router.go
