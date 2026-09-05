# Pre-Feasibility Engine (control-bim-pf-engine) Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH"

# Install system dependencies for CairoSVG, Pillow, and ezdxf
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# Install project dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-interaction --no-ansi

# Copy project source and assets
COPY src/ ./src/
COPY tools/ ./tools/
COPY docs/ ./docs/
COPY tests/fixtures/ ./tests/fixtures/
COPY simple_room.dxf ./

# Create artifacts directory
RUN mkdir -p artifacts/jobs artifacts/evaluations artifacts/replays artifacts/feasibility

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
