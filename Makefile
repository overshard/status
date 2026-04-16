# Django + Vite Makefile


.PHONY: run runserver vite clean push pull update scheduler
.DEFAULT: run


SERVER_URL = $(shell git config --get remote.server.url | cut -d ':' -f 1)
PROJECT_NAME = $(shell basename $(PWD))


run: install
	@echo "run ----------------------------------------------------------------"
	${MAKE} -j2 runserver vite

runserver:
	uv run python manage.py runserver 0.0.0.0:8000

vite:
	bun run dev

scheduler:
	uv run python manage.py scheduler


install: node_modules/touchfile .venv/touchfile db.sqlite3

node_modules/touchfile: package.json
	@echo "install node deps --------------------------------------------------"
	bun install
	touch $@
	@echo "> all node deps installed"

.venv/touchfile: pyproject.toml
	@echo "install python deps ------------------------------------------------"
	uv sync
	touch $@
	@echo "> all python deps installed"

db.sqlite3:
	@echo "create database ----------------------------------------------------"
	uv run python manage.py migrate
	@echo "> database created"


push:
	@echo "push ---------------------------------------------------------------"
	git remote | xargs -I R git push R master

pull:
	@echo "pull ---------------------------------------------------------------"
	rsync -avz $(SERVER_URL):/srv/data/$(PROJECT_NAME)/db/db.sqlite3 db.sqlite3
	rsync -avz $(SERVER_URL):/srv/data/$(PROJECT_NAME)/media/ media
	@echo "> all files copied"


update: install
	@echo "update -------------------------------------------------------------"
	uv lock --upgrade
	bun update --latest
	@echo "> all deps updated"


clean:
	@echo "clean --------------------------------------------------------------"
	rm -rf node_modules
	rm -rf .venv
	rm -rf db.sqlite3
	rm -rf media
	@echo "> all files removed"
