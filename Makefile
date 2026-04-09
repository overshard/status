# Django + Webpack Makefile


.PHONY: run runserver webpack check clean push pull update scheduler
.DEFAULT: run


SERVER_URL = $(shell git config --get remote.server.url | cut -d ':' -f 1)
PROJECT_NAME = $(shell basename $(PWD))


run: check install
	@echo "run ----------------------------------------------------------------"
	${MAKE} -j3 runserver webpack

runserver:
	uv run python manage.py runserver 0.0.0.0:8000

webpack:
	npx nodemon --watch webpack.config.js --exec \
		'webpack --config webpack.config.js --mode development --watch --devtool source-map'

scheduler:
	uv run python manage.py scheduler


check:
	@echo "check --------------------------------------------------------------"
	@if ! which uv > /dev/null; then\
		echo "> uv not found in PATH, please install it: https://docs.astral.sh/uv/getting-started/installation/";\
		exit 1;\
	fi
	@if ! which yarn > /dev/null; then\
		echo "> yarn not found in PATH, please make sure it's installed along with node";\
		exit 1;\
	fi
	@echo "> all checks passed"


install: node_modules/touchfile .venv/touchfile db.sqlite3

node_modules/touchfile: package.json
	@echo "install node deps --------------------------------------------------"
	yarn install
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
	yarn upgrade
	@echo "> all deps updated"


clean:
	@echo "clean --------------------------------------------------------------"
	rm -rf node_modules
	rm -rf .venv
	rm -rf db.sqlite3
	rm -rf media
	@echo "> all files removed"
