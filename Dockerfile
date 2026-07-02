# Stage 1: Build SvelteKit UI
FROM node:22-alpine AS ui-builder
WORKDIR /ui
COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm ci
COPY web-ui/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.13-slim

WORKDIR /app

# System deps (ffmpeg for conversion)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Runtime dependencies
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.34" "pydantic>=2.0"

# yt-dlp for media downloads
RUN pip install --no-cache-dir yt-dlp

# Dev dependencies (linting, type checking, testing)
RUN pip install --no-cache-dir "pytest>=8.0" "httpx2>=2.0" "ruff>=0.11" "mypy>=1.15"

# Copy and install the package itself
COPY pyproject.toml ./
COPY tube_explore/ tube_explore/
COPY tests/ tests/
RUN pip install --no-cache-dir .

# Copy built UI
COPY --from=ui-builder /ui/build /app/web-ui/build

EXPOSE 8000

CMD ["uvicorn", "tube_explore.api:app", "--host", "0.0.0.0", "--port", "8000"]
