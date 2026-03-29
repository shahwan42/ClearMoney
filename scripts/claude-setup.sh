#!/usr/bin/env bash
# Claude Code SessionStart hook — bootstraps the ClearMoney dev environment.
#
# Idempotent: safe to run multiple times. Each step checks current state first.
# Only starts the PostgreSQL container (not Django) to avoid port 8000 conflicts.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

DB_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable"
STATUS=()

# --- 1. Ensure .env exists (Docker Compose requires env_file: .env) ---
if [ ! -f .env ]; then
    cp .env.example .env
    STATUS+=("env: created .env from .env.example")
else
    STATUS+=("env: .env already exists")
fi

# --- 2. Start PostgreSQL via Docker (db service only) ---
if docker compose ps db --format '{{.Status}}' 2>/dev/null | grep -qi "up"; then
    STATUS+=("docker: PostgreSQL already running")
else
    docker compose up -d db 2>&1 | tail -3
    # Wait for DB to become healthy (up to 30s)
    for _ in $(seq 1 15); do
        if docker compose ps db --format '{{.Status}}' 2>/dev/null | grep -qi "healthy"; then
            break
        fi
        sleep 2
    done
    STATUS+=("docker: started PostgreSQL")
fi

# --- 3. Install git hooks if missing or outdated ---
if [ -f .git/hooks/pre-commit ] && diff -q scripts/pre-commit .git/hooks/pre-commit >/dev/null 2>&1; then
    STATUS+=("git-hooks: pre-commit up to date")
else
    make setup-hooks 2>&1
    STATUS+=("git-hooks: installed pre-commit hook")
fi

# --- 4. Apply pending migrations ---
MIGRATION_OUTPUT=$(cd backend && DATABASE_URL="$DB_URL" uv run manage.py migrate 2>&1) || true
if echo "$MIGRATION_OUTPUT" | grep -q "No migrations to apply"; then
    STATUS+=("migrations: all up to date")
else
    STATUS+=("migrations: applied pending migrations")
fi

# --- 5. Start dev server in background if port 8000 is free ---
if curl -s -o /dev/null -w '%{http_code}' http://0.0.0.0:8000/ 2>/dev/null | grep -qE '^(200|301|302|403)'; then
    STATUS+=("server: already running on :8000")
else
    DISABLE_RATE_LIMIT=true DATABASE_URL="$DB_URL" \
        nohup bash -c "cd '$PROJECT_DIR/backend' && uv run manage.py runserver 0.0.0.0:8000" \
        > /tmp/clearmoney-devserver.log 2>&1 &
    SERVER_PID=$!
    sleep 3
    if curl -s -o /dev/null -w '%{http_code}' http://0.0.0.0:8000/ 2>/dev/null | grep -qE '^(200|301|302|403)'; then
        STATUS+=("server: started on :8000 (PID $SERVER_PID, rate limiting disabled)")
    else
        STATUS+=("server: FAILED to start — check /tmp/clearmoney-devserver.log")
    fi
fi

# --- 6. Git status ---
GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
GIT_DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$GIT_DIRTY" = "0" ]; then
    STATUS+=("git: branch '$GIT_BRANCH', working tree clean")
else
    STATUS+=("git: branch '$GIT_BRANCH', $GIT_DIRTY uncommitted change(s)")
fi

# --- Build JSON output for Claude Code hook system ---
REPORT=""
for line in "${STATUS[@]}"; do
    REPORT="${REPORT}  - ${line}\n"
done

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Dev environment ready. Status:\n${REPORT}\nReminder: run 'make test' to record baseline test count, then 'make lint' to verify zero errors (delivery-checklist.md pre-flight steps 1-2)."
  }
}
EOF
