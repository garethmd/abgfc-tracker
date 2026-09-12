FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

RUN mkdir -p /data/media
EXPOSE 8000
# Migrate, make sure reference data + coach login exist, then serve.
CMD ["sh", "-c", "uv run python -m scripts.seed && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
