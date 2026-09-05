FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==2.0.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies without dev tools
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy application source
COPY src/ ./src/
COPY README.md ./

# Install package
RUN pip install --no-deps -e .

EXPOSE 8000

ENTRYPOINT ["python", "-m", "argus.cli"]
CMD ["dashboard", "--host", "0.0.0.0", "--port", "8000"]
