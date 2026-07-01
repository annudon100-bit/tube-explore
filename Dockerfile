FROM python:3.13-slim

WORKDIR /app

# Runtime dependencies
RUN pip install --no-cache-dir fastapi>=0.115 uvicorn>=0.34 pydantic>=2.0

# Dev dependencies (linting, type checking, testing)
RUN pip install --no-cache-dir pytest>=8.0 httpx>=0.27 ruff>=0.11 mypy>=1.15

# Copy and install the package itself
COPY pyproject.toml ./
COPY tube_explore/ tube_explore/
COPY tests/ tests/
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "tube_explore.api:app", "--host", "0.0.0.0", "--port", "8000"]
