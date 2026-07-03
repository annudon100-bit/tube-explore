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

# Pre-download yt-dlp binary (used via subprocess in ytdlp.py)
ADD https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp /usr/local/bin/yt-dlp
RUN chmod +x /usr/local/bin/yt-dlp

# Copy and install the package itself (reads deps from pyproject.toml)
COPY pyproject.toml ./
COPY tube_explore/ tube_explore/
COPY tests/ tests/
RUN pip install --no-cache-dir .

# Copy built UI
COPY --from=ui-builder /ui/build /app/web-ui/build

EXPOSE 8000

CMD ["uvicorn", "tube_explore.api:app", "--host", "0.0.0.0", "--port", "8000"]
