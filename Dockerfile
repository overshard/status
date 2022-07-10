# A dockerfile to run an status server
#
# Status can run very simply as long as we have a few basics:
# - python w/ pipenv
# - node w/ yarn
# - sqlite3
# - chromium


FROM alpine:3.16

RUN apk add --update --no-cache \
      build-base python3-dev postgresql-dev \
      python3 py3-pip \
      nodejs yarn \
      chromium libstdc++ nss harfbuzz freetype font-noto font-noto-extra font-noto-emoji && \
    pip install --upgrade pipenv

RUN addgroup -S -g 1000 app && \
    adduser -S -h /app -s /sbin/nologin -u 1000 -G app app && \
    chown -R app:app /app

WORKDIR /app

COPY Pipfile Pipfile.lock package.json yarn.lock /app/
RUN yarn install && pipenv install --system

COPY . .

RUN webpack --config webpack.config.js --mode production && \
    rm -rf node_modules && \
    python3 manage.py collectstatic --noinput

USER app:app
