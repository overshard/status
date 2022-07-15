FROM alpine:3.16

ENV LANG "C.UTF-8"

RUN apk add --update --no-cache \
      python3 py3-pip \
      nodejs yarn \
      chromium libstdc++ nss harfbuzz freetype font-noto font-noto-extra font-noto-emoji && \
    pip install --upgrade pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock package.json yarn.lock /app/
RUN yarn install && \
    PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

COPY . .

ENV PATH="/app/.venv/bin:/app/node_modules/.bin:$PATH"
ENV PYTHONPATH="/app/.venv/lib/python3.10/site-packages:$PYTHONPATH"

RUN webpack --config webpack.config.js --mode production && \
    python3 manage.py collectstatic --noinput

RUN addgroup -S -g 1000 app && \
    adduser -S -h /app -s /sbin/nologin -u 1000 -G app app && \
    chown -R app:app /app
USER app:app
