# One image: the React app is built in stage 1, and FastAPI serves it next to the API in stage 2.

# ---- stage 1: build the web app
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- stage 2: the API
FROM python:3.14-slim AS app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist ENVIRONMENT=prod
WORKDIR /app/backend

# dependencies first: this layer is cached until uv.lock changes
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist /app/frontend/dist

# never run as root inside the container
RUN useradd --create-home --uid 1000 spendwise && chown -R spendwise /app
USER spendwise
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["uv", "run", "--no-sync", "spendwise", "serve", "--host", "0.0.0.0", "--port", "8000"]
