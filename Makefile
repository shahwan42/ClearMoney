# ClearMoney Makefile — common development commands.
#
# Usage: make <target>
#
# Like: composer scripts, manage.py commands, or package.json scripts.
.PHONY: run test test-fast test-e2e lint format dead clean up down logs reconcile reconcile-fix deploy deploy-test deploy-test-cleanup deploy-logs ensure-vapid-keys shell inspectdb snapshots startup-jobs makemigrations migrate fake-initial setup-hooks coverage coverage-check messages compile-messages createsuperuser qa-user qa-login qa-seed qa-teardown qa-reset

DB_URL ?= postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable

# Start the Django development server on :8000.
run:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py runserver 0.0.0.0:8000

# Run Django tests with verbose output (rate limiting disabled).
test:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest

# Run Django tests in parallel (rate limiting disabled).
test-fast:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest -n auto

# Auto-format code with ruff (modifies files).
format:
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

# Run linting (ruff + ruff format check + mypy + import-linter).
lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && DATABASE_URL="$(DB_URL)" uv run mypy .
	cd backend && uv run lint-imports

# Detect unused Python code (dead code). Findings require human triage — not wired into lint.
dead:
	cd backend && uv run vulture . vulture_whitelist.py --min-confidence 60 --exclude migrations,tests,conftest.py

# Run end-to-end tests using Playwright.
test-e2e:
	cd e2e && DATABASE_URL="$(DB_URL)" uv run pytest

# Run tests with coverage report (HTML + terminal).
coverage:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest --cov --cov-report=term-missing --cov-report=html

# Check coverage meets threshold (for CI).
coverage-check:
	cd backend && DATABASE_URL="$(DB_URL)" DISABLE_RATE_LIMIT=true uv run pytest --cov --cov-fail-under=60

# Extract translatable strings into .po files.
messages:
	cd backend && uv run manage.py makemessages -l ar --ignore=static_src --ignore=static

# Compile .po files to .mo for runtime use.
compile-messages:
	cd backend && uv run manage.py compilemessages

# Create a Django admin superuser. Requires DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD env vars.
createsuperuser:
	cd backend && DJANGO_SUPERUSER_EMAIL="$(DJANGO_SUPERUSER_EMAIL)" DJANGO_SUPERUSER_PASSWORD="$(DJANGO_SUPERUSER_PASSWORD)" uv run manage.py create_superuser

# Remove build artifacts.
clean:
	rm -rf backend/staticfiles/ backend/locale/*/LC_MESSAGES/*.mo
	rm -rf backend/staticfiles/

COMPOSE := $(shell command -v docker-compose 2> /dev/null || echo "docker compose")

# Start all Docker services in detached mode.
up:
	$(COMPOSE) up -d --build

# Stop and remove all Docker containers.
down:
	$(COMPOSE) down

# Stream logs from all Docker containers.
logs:
	$(COMPOSE) logs -f

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

# Run post-deploy smoke verification inside the production Django container.
deploy-test:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && sudo docker compose -f docker-compose.prod.yml exec -T django python manage.py deploy_smoke_test"

# Remove any leftover deploy-smoke sentinel data from production (idempotent).
deploy-test-cleanup:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && sudo docker compose -f docker-compose.prod.yml exec -T django python manage.py deploy_smoke_test --cleanup-only"

# Stream production logs from the VPS.
deploy-logs:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && sudo docker compose -f docker-compose.prod.yml logs -f"

# Generate VAPID keys on production if not already configured (idempotent, safe to re-run).
ensure-vapid-keys:
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && sudo docker compose -f docker-compose.prod.yml run --rm --no-deps -v $(DEPLOY_DIR)/.env.prod:/tmp/.env.prod django python manage.py generate_vapid_keys --output /tmp/.env.prod --if-missing"

# Backup production database to local backups/ directory.
backup-prod:
	@date_str=$$(date +%Y-%m-%d); \
	base="backups/clearmoney_backup_$$date_str"; \
	count=1; \
	while [ -f "$$base$$( [ $$count -gt 1 ] && echo _$$count || echo ).dump" ]; do \
		count=$$((count + 1)); \
	done; \
	filename="$$base$$( [ $$count -gt 1 ] && echo _$$count || echo ).dump"; \
	ssh $(DEPLOY_HOST) "cd $(DEPLOY_DIR) && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U clearmoney -Fc clearmoney" > "$$filename"

# ── QA Helpers ─────────────────────────────────────────────────────────────────
QA_EMAIL ?= qa@clearmoney.app
QA_PASSWORD ?= qatest123

# Create a QA superuser. Usage: make qa-user  or  make qa-user EMAIL=x PASSWORD=y
qa-user:
	cd backend && DATABASE_URL="$(DB_URL)" DJANGO_SUPERUSER_EMAIL="$(QA_EMAIL)" DJANGO_SUPERUSER_PASSWORD="$(QA_PASSWORD)" uv run manage.py create_superuser

# Print the magic-link login URL for a QA user (dev mode — no email sent).
# Usage: make qa-login  or  make qa-login EMAIL=qa@clearmoney.app
qa-login:
	cd backend && DATABASE_URL="$(DB_URL)" uv run python -c "\
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clearmoney.settings'); django.setup(); \
from auth_app.models import AuthToken; \
t = AuthToken.objects.filter(email='$(QA_EMAIL)', used=False).order_by('-created_at').first(); \
print('http://localhost:8000/auth/verify?token=' + t.token if t else 'No token found — submit login form first') \
" 2>/dev/null || (echo "No token — try: curl -s -X POST http://localhost:8000/login -d 'email=$(QA_EMAIL)'")

# Seed standard QA test data (institution, accounts, budgets, transactions).
qa-seed:
	cd backend && DATABASE_URL="$(DB_URL)" uv run manage.py qa_seed --email "$(QA_EMAIL)"

# Delete all data for a QA user (accounts, transactions, budgets, etc.) + the user itself.
qa-teardown:
	cd backend && DATABASE_URL="$(DB_URL)" uv run python -c "\
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clearmoney.settings'); django.setup(); \
from auth_app.models import User; \
u = User.objects.filter(email='$(QA_EMAIL)').first(); \
u.delete() if u else print('User not found'); \
print('Teardown complete for $(QA_EMAIL)') \
" 2>/dev/null

# Full reset: teardown + create user + seed data.
qa-reset: qa-teardown qa-user qa-seed
	@echo "QA environment reset for $(QA_EMAIL)"
