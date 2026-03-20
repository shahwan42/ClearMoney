FROM python:3.12-slim

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install deps first (cache layer), then copy source.
# Build context is project root (not backend/), so paths are prefixed.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY backend/ .

# Copy shared static files (CSS, JS, icons, manifest, service worker).
# In the container these live at /app/static_src/ — settings.py detects this path.
COPY static/ /app/static_src/

# Use the venv created by uv directly (no uv run overhead in production)
ENV PATH="/app/.venv/bin:$PATH"

# Collect static files into STATIC_ROOT for whitenoise to serve
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "clearmoney.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
