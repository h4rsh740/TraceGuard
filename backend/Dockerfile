# TraceGuard Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (libpq-dev for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and migration files
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY pyproject.toml /app/pyproject.toml

ENV PYTHONPATH=/app
EXPOSE 8000

# Run alembic migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
