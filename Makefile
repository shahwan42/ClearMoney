# ClearMoney Makefile — common development commands.
#
# Makefiles define "targets" (commands) that you run with `make <target>`.
# They're the Go ecosystem's standard for project automation — similar to:
#   - Laravel: composer scripts or artisan commands
#   - Django: manage.py commands
#   - Node: package.json scripts
#
# .PHONY tells Make these aren't real files — they're just command names.
# Without this, if a file named "test" existed, `make test` would do nothing.
# See: https://www.gnu.org/software/make/manual/html_node/Phony-Targets.html
.PHONY: run build test test-integration test-e2e test-e2e-migration lint clean up down logs migrate-create seed reconcile reconcile-fix deploy deploy-logs django-run django-shell django-test django-inspectdb

# Start the development server. `go run` compiles and runs in one step.
# Like: `php artisan serve` or `python manage.py runserver`
run:
	DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" go run ./cmd/server

# Compile the binary to bin/clearmoney. Unlike `go run`, this creates a
# standalone executable you can deploy without the Go toolchain.
# Like: `composer build` or creating a Django wheel package.
build:
	go build -o bin/clearmoney ./cmd/server

# Run all tests with verbose output. `./...` is Go's wildcard pattern
# meaning "this package and all sub-packages recursively".
# Like: `php artisan test` or `python -m pytest`
test:
	go test ./... -v

# Run integration tests against a real PostgreSQL database.
# - TEST_DATABASE_URL: connection string (port 5433 because Colima uses 5432)
# - -count=1: disable test caching (always re-run, important for DB tests)
# - -p 1: run packages serially (not in parallel) to avoid DB race conditions
# Like: `php artisan test --env=testing` or `pytest --ds=settings.test`
test-integration:
	TEST_DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" go test ./... -v -count=1 -p 1

# Run golangci-lint to check for code quality issues.
# Like: `php artisan lint` or `flake8` / `ruff` in Python.
lint:
	golangci-lint run --timeout=5m

# Run end-to-end tests using Playwright (requires running server on :8080).
# Like: `php artisan dusk` (Laravel Dusk) or Django's LiveServerTestCase.
# The Playwright config auto-starts the Go server if not already running.
test-e2e:
	cd e2e && npx playwright test

# Run only Django migration e2e tests (cross-app session, data consistency, UI parity).
# Requires both Go (:8080) and Django (:8000) servers — Playwright starts them automatically.
test-e2e-migration:
	cd e2e && npx playwright test tests/17-django-migration.spec.ts

# Remove compiled binaries.
clean:
	rm -rf bin/

# Start all Docker services (app + PostgreSQL) in detached mode.
# --build rebuilds the app image if Dockerfile or source changed.
# Like: `sail up -d` (Laravel Sail) or `docker compose` for Django.
up:
	docker compose up -d --build

# Stop and remove all Docker containers (data in volumes persists).
down:
	docker compose down

# Stream logs from all Docker containers. -f = follow (live tail).
# Like: `tail -f storage/logs/laravel.log` or Django's console output.
logs:
	docker compose logs -f

# Populate the database with sample development data.
# Like: `php artisan db:seed` or `python manage.py loaddata fixtures.json`
seed:
	DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" go run ./cmd/seed

# Check if any account balances are out of sync with transaction history.
# Reports discrepancies without making changes (read-only audit).
reconcile:
	DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" go run ./cmd/reconcile

# Same as reconcile, but auto-fixes any discrepancies found.
# Like running a database repair command.
reconcile-fix:
	DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" go run ./cmd/reconcile -- --fix

# Create a new database migration file pair (up + down).
# Usage: make migrate-create name=add_foo_column
# Like: `php artisan make:migration` or `python manage.py makemigrations`
#
# The @ prefix suppresses command echoing (cleaner output).
# $$ escapes $ in Makefiles (shell sees single $).
# printf "%06d" pads the number with leading zeros (000018, 000019, etc.).
migrate-create:
	@if [ -z "$(name)" ]; then echo "Usage: make migrate-create name=<migration_name>"; exit 1; fi
	@next=$$(printf "%06d" $$(ls internal/database/migrations/*.up.sql 2>/dev/null | wc -l)); \
	touch "internal/database/migrations/$${next}_$(name).up.sql"; \
	touch "internal/database/migrations/$${next}_$(name).down.sql"; \
	echo "Created: $${next}_$(name).{up,down}.sql"

# Deploy to production VPS via SSH.
# Pushes local commits, pulls on the server, rebuilds and restarts containers.
# Like: `cap production deploy` (Capistrano) or `fab deploy` (Fabric).
DEPLOY_HOST ?= hetzner-keeper
DEPLOY_DIR ?= ~/ClearMoney
deploy:
	@echo "Pushing latest changes..."
	git checkout main
	git push
	@echo "Deploying to $(DEPLOY_HOST)..."
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && git pull && sudo docker compose -f docker-compose.prod.yml up -d --build"
	@echo "Deploy complete. App running at https://clearmoney.shahwan.me"

# Stream production logs from the VPS.
deploy-logs:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && sudo docker compose -f docker-compose.prod.yml logs -f"

# --- Django commands (Strangler Fig migration) ---
# These run the Django app that serves migrated routes (/settings, /reports, /export).
# Like `python manage.py runserver` but with the correct DATABASE_URL.

django-run:
	cd backend && DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" uv run manage.py runserver 0.0.0.0:8000

django-shell:
	cd backend && DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" uv run manage.py shell

django-test:
	cd backend && DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" uv run pytest -v

django-inspectdb:
	cd backend && DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" uv run manage.py inspectdb

django-lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
