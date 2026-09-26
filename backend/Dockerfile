FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr and writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install system dependencies needed for Playwright and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first for caching dependencies
COPY pyproject.toml /app/

# Install python dependencies and playwright with chromium
RUN pip install --upgrade pip && \
    pip install .[dev] && \
    playwright install --with-deps chromium

# Copy application source code
COPY . /app/

# Expose API port
EXPOSE 8000

# Default entrypoint runs migrations and starts uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
