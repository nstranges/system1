# The deployed app: one container where the server also serves the built client.
# The repo layout is kept under /app because the server finds .env, the playbook and its data from the repo root.

FROM oven/bun:1.3.6 AS client
WORKDIR /app/app/client
COPY app/client/package.json app/client/bun.lock ./
RUN bun install --frozen-lockfile
COPY app/client/ ./
# Vite bakes the publishable key into the bundle, so it's needed at build time (Railway passes variables as args).
ARG CLERK_PUBLISHABLE_KEY
ENV CLERK_PUBLISHABLE_KEY=$CLERK_PUBLISHABLE_KEY
RUN bun run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.0 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app/app/server
# Dependencies first, so code changes don't reinstall them.
COPY app/server/pyproject.toml app/server/uv.lock app/server/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app/server/ ./
RUN uv sync --frozen --no-dev
COPY .claude/skills/system1-onboard/playbook.md /app/.claude/skills/system1-onboard/playbook.md
COPY --from=client /app/app/client/dist /app/app/client/dist
ENV STATIC_DIR=/app/app/client/dist
CMD ["sh", "-c", "uv run --no-sync uvicorn system1.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
