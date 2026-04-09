FROM alpine:3.16

ENV LANG "C.UTF-8"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN apk add --update --no-cache \
      python3 py3-pip \
      nodejs yarn \
      chromium libstdc++ nss harfbuzz freetype font-noto font-noto-extra font-noto-emoji

WORKDIR /app

COPY pyproject.toml uv.lock package.json yarn.lock /app/
RUN yarn install && \
    uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:/app/node_modules/.bin:$PATH"

RUN webpack --config webpack.config.js --mode production && \
    python3 manage.py collectstatic --noinput

RUN addgroup -S -g 1000 app && \
    adduser -S -h /app -s /sbin/nologin -u 1000 -G app app && \
    chown -R app:app /app
USER app:app
