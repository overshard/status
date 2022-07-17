# Django + Webpack Makefile
# v. 2022.07.13


.PHONY: run runserver webpack check clean push pull update
.DEFAULT: run


SERVER_URL = $(shell git config --get remote.origin.url | cut -d ':' -f 1)
INSTALLED_PYTHON_VERSIONS = $(shell ls ~/.pyenv/versions/)
REQUIRED_PYTHON_VERSION = $(shell cat Pipfile | grep "^python_version " | cut -d '"' -f 2)
PROJECT_NAME = $(shell basename $(PWD))


run: check install
	@echo "run ----------------------------------------------------------------"
	${MAKE} -j2 runserver webpack

runserver:
	pipenv run python manage.py runserver

webpack:
	npx nodemon --watch webpack.config.js --exec \
		'webpack --config webpack.config.js --mode development --watch --devtool source-map'


check:
	@echo "check --------------------------------------------------------------"
	@if ! which pipenv > /dev/null; then\
		echo "> pipenv not found in PATH, please make sure it's installed along with pyenv";\
		echo "> see https://github.com/pyenv/pyenv and install the latest version of python";\
		echo "> if you have docker installed you can use https://github.com/overshard/dockerfiles/blob/master/webdev/Dockerfile";\
		exit 1;\
	fi
	@if ! which yarn > /dev/null; then\
		echo "> yarn not found in PATH, please make sure it's installed along with node";\
		echo "> see https://github.com/nvm-sh/nvm and install the latest version of node";\
		echo "> if you have docker installed you can use https://github.com/overshard/dockerfiles/blob/master/webdev/Dockerfile";\
		exit 1;\
	fi
	@if ! echo $(INSTALLED_PYTHON_VERSIONS) | grep -q $(REQUIRED_PYTHON_VERSION); then\
		echo "> python $(REQUIRED_PYTHON_VERSION) not found in ~/.pyenv/versions";\
		echo "> trying to install it for you via pyenv";\
		pyenv install $(REQUIRED_PYTHON_VERSION);\
	fi
	@echo "> all checks passed"


install: node_modules/touchfile .venv/touchfile db.sqlite3

node_modules/touchfile: package.json
	@echo "install node deps --------------------------------------------------"
	yarn install
	touch $@
	@echo "> all node deps installed"

.venv/touchfile: Pipfile
	@echo "install python deps ------------------------------------------------"
	mkdir -p .venv
	pipenv install --dev
	touch $@
	@echo "> all python deps installed"

db.sqlite3:
	@echo "create database ----------------------------------------------------"
	pipenv run python manage.py migrate
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
	pipenv update
	yarn upgrade
	@echo "> all deps updated"


clean:
	@echo "clean --------------------------------------------------------------"
	rm -rf node_modules
	rm -rf .venv
	rm -rf db.sqlite3
	rm -rf media
	@echo "> all files removed"
