# ClearMoney Makefile — common development commands.
#
# Usage: make <target>
#
# Like: composer scripts, manage.py commands, or package.json scripts.
.PHONY: run test test-fast test-e2e lint format clean up down logs reconcile reconcile-fix deploy deploy-logs shell inspectdb snapshots startup-jobs makemigrations migrate fake-initial setup-hooks coverage coverage-check

DB_URL ?= postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable

# Start the Django development server on :8000.
run:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py runserver 0.0.0.0:8000

# Run Django tests with verbose output (rate limiting disabled).
test:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest -v

# Run Django tests in parallel (rate limiting disabled).
test-fast:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest -v -n auto

# Auto-format code with ruff (modifies files).
format:
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

# Run linting (ruff + ruff format check + mypy).
lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && DATABASE_URL="$(DB_URL)" uv run mypy .

# Run end-to-end tests using Playwright.
test-e2e:
	cd e2e && DATABASE_URL="$(DB_URL)" uv run pytest -v

# Run tests with coverage report (HTML + terminal).
coverage:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest --cov --cov-report=term-missing --cov-report=html

# Check coverage meets threshold (for CI).
coverage-check:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest --cov --cov-fail-under=60

# Remove build artifacts.
clean:
	rm -rf backend/staticfiles/

# Start all Docker services in detached mode.
up:
	docker compose up -d --build

# Stop and remove all Docker containers.
down:
	docker compose down

# Stream logs from all Docker containers.
logs:
	docker compose logs -f

# Check if any account balances are out of sync with transaction history.
reconcile:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py reconcile_balances

# Same as reconcile, but auto-fixes any discrepancies found.
reconcile-fix:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py reconcile_balances --fix

# Take daily snapshots.
snapshots:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py take_snapshots

# Run all startup background jobs.
startup-jobs:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py run_startup_jobs

# Open Django shell.
shell:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py shell

# Inspect current DB schema as Django models.
inspectdb:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py inspectdb

# Generate new Django migrations.
makemigrations:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py makemigrations

# Apply pending Django migrations.
migrate:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py migrate

# Fake initial migrations (mark existing tables as migrated without running SQL).
fake-initial:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py migrate --fake-initial

# Install git hooks (run once after clone).
setup-hooks:
	cp scripts/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Git hooks installed."

# Deploy to production VPS via SSH.
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
