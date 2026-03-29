#!/bin/bash
set -euo pipefail

# Only run in Claude Code remote environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# ── Start PostgreSQL 16 ─────────────────────────────────────────────────────
echo "Starting PostgreSQL 16..."
sudo pg_ctlcluster 16 main start 2>/dev/null || true

# Wait for PG to accept connections
for i in 1 2 3 4 5; do
  pg_isready -h localhost -p 5432 -q && break
  sleep 1
done

# ── Create database user (idempotent) ────────────────────────────────────────
if ! sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='clearmoney'" | grep -q 1; then
  echo "Creating database user..."
  sudo -u postgres psql -c "CREATE USER clearmoney WITH PASSWORD 'clearmoney' CREATEDB"
fi

# ── Create database (idempotent) ─────────────────────────────────────────────
if ! sudo -u postgres psql -tc "SELECT 1 FROM pg_catalog.pg_database WHERE datname='clearmoney'" | grep -q 1; then
  echo "Creating database..."
  sudo -u postgres createdb -O clearmoney clearmoney
fi

# ── Export DB_URL for all make targets ───────────────────────────────────────
# Remote PG runs on port 5432 (local dev uses 5433 via Docker)
echo 'export DB_URL="postgres://clearmoney:clearmoney@localhost:5432/clearmoney?sslmode=disable"' >> "$CLAUDE_ENV_FILE"

echo "Remote DB ready on port 5432."
