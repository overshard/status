FROM alpine:3.21

ENV LANG="C.UTF-8" \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY --from=oven/bun:alpine /usr/local/bin/bun /usr/local/bin/bun

RUN apk add --update --no-cache \
      python3 py3-pip \
      nodejs \
      chromium libstdc++ nss harfbuzz freetype font-noto font-noto-extra font-noto-emoji

WORKDIR /app

COPY pyproject.toml uv.lock package.json bun.lock /app/
RUN bun install --frozen-lockfile && \
    uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:/app/node_modules/.bin:$PATH"

RUN bun run build && \
    uv run python manage.py collectstatic --noinput && \
    chmod +x /app/entrypoint.py

RUN addgroup -S -g 1000 app && \
    adduser -S -h /app -s /sbin/nologin -u 1000 -G app app && \
    chown -R app:app /app
USER app:app
