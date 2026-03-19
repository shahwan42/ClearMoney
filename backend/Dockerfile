FROM python:3.12-slim

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install deps first (cache layer), then copy source
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Collect static files (Django's own static, if any)
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Use the venv created by uv directly (no uv run overhead in production)
ENV PATH="/app/.venv/bin:$PATH"
CMD ["gunicorn", "clearmoney.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
