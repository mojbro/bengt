FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
 && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Dependency layer — install deps before project code for cache friendliness.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Project layer — editable install of the backend package.
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

EXPOSE 3501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3501"]
