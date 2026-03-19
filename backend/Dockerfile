FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Collect static files (Django's own static, if any)
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "clearmoney.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
