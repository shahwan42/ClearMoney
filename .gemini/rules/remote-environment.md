# Remote Environment Setup (Gemini Code on the web)

## How It Works

A **SessionStart hook** (`.gemini/hooks/session-start.sh`) runs automatically when a Gemini Code remote session starts. It:

1. Starts PostgreSQL 16 (`pg_ctlcluster 16 main start`)
2. Creates the `clearmoney` database user and database (idempotent)
3. Exports `DB_URL` with port 5432 via `$GEMINI_ENV_FILE`

After the hook runs, all `make` targets work identically to local dev — no manual setup needed.

## Why Port 5432 (Not 5433)

| Environment | PG Port | How PG Runs |
|-------------|---------|-------------|
| Local dev (Docker) | 5433 | `docker compose up` maps 5433→5432 (avoids Colima conflict) |
| Remote (Gemini Code) | 5432 | Native PG 16 on host, started by session hook |
| CI (GitHub Actions) | 5432 | PG 16 service container |
| Production | 5432 | Docker internal network |

The Makefile defaults to port 5433 (`DB_URL ?=`). The session hook exports `DB_URL` with port 5432, which overrides the default since `?=` only sets if unset.

## Troubleshooting

- **"connection refused on 5433"** — Hook didn't run or `DB_URL` not exported. Run manually:
  ```bash
  GEMINI_CODE_REMOTE=true GEMINI_ENV_FILE=/dev/null .gemini/hooks/session-start.sh
  export DB_URL="postgres://clearmoney:clearmoney@localhost:5432/clearmoney?sslmode=disable"
  ```
- **"role clearmoney does not exist"** — PG started but user not created. Run the hook again.
- **PG won't start** — Check `pg_lsclusters` to verify PG 16 is installed.
