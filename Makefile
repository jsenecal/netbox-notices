NAME=netbox-notices
VERFILE=./notices/__init__.py
NETBOX_DIR=/opt/netbox/netbox
PLUGIN_NAME=notices
REPO_PATH=/opt/netbox-notices
VENV_PY_PATH=/opt/netbox/venv/bin/python3
INITIALIZER_PATH=${REPO_PATH}/.devcontainer/initializers
DEMO_DATA_PATH=${REPO_PATH}/.devcontainer/netbox-demo-data
NETBOX_VERSION=v$(shell grep '^version' /opt/netbox/pyproject.toml | head -1 | cut -d'"' -f2 | cut -d. -f1,2)

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[0-9a-zA-Z_-]+\.*[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

# Development targets (for use within devcontainer)
.PHONY: runserver
runserver: ## Start NetBox development server
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py runserver 0.0.0.0:8008

.PHONY: shell
shell: ## Open Django shell
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py shell

.PHONY: nbshell
nbshell: ## Open NetBox shell
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py nbshell

.PHONY: dbshell
dbshell: ## Open database shell
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py dbshell

.PHONY: migrate
migrate: ## Run database migrations
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py migrate

.PHONY: migrations
migrations: ## Create new migrations for the plugin
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py makemigrations $(PLUGIN_NAME)

.PHONY: showmigrations
showmigrations: ## Show migration status
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py showmigrations $(PLUGIN_NAME)

.PHONY: test
test: setup ## Run plugin tests with pytest
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py makemigrations $(PLUGIN_NAME) --check
	${VENV_PY_PATH} -m pytest ${REPO_PATH}/tests/

.PHONY: test-verbose
test-verbose: setup ## Run plugin tests with verbose output
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py makemigrations $(PLUGIN_NAME) --check
	${VENV_PY_PATH} -m pytest ${REPO_PATH}/tests/ -vv

.PHONY: test-quick
test-quick: ## Run plugin tests without migration check (faster)
	${VENV_PY_PATH} -m pytest ${REPO_PATH}/tests/ --tb=short --cov=notices --cov-report=term-missing

.PHONY: collectstatic
collectstatic: ## Collect static files
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py collectstatic --no-input

.PHONY: createsuperuser
createsuperuser: ## Create a superuser
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py createsuperuser

.PHONY: rqworker
rqworker: ## Start RQ worker
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py rqworker

.PHONY: trace_paths
trace_paths: ## Run NetBox trace_paths utility
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py trace_paths

.PHONY: setup
setup: ## Setup/reinstall the plugin in editable mode
	uv pip install --no-cache-dir -e ${REPO_PATH}

.PHONY: reinstall
reinstall: setup ## Alias for setup

.PHONY: lint
lint: ## Run code linting checks
	${VENV_PY_PATH} -m ruff check .

.PHONY: format
format: ## Format code with ruff
	${VENV_PY_PATH} -m ruff format .

.PHONY: fix
fix: ## Run ruff with --fix
	${VENV_PY_PATH} -m ruff check --fix .

.PHONY: clean
clean: ## Clean build artifacts
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# NetBox Initializers (Demo Data)
.PHONY: example_initializers
example_initializers: ## Copy example initializers to .devcontainer
	mkdir -p ${INITIALIZER_PATH}
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py copy_initializers_examples --path ${INITIALIZER_PATH}

.PHONY: load_initializers
load_initializers: ## Load initializer data from .devcontainer/initializers
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py load_initializer_data --path ${INITIALIZER_PATH}

.PHONY: initializers
initializers: ## Setup and load demo data via initializers
	-rm -rf ${INITIALIZER_PATH}
	-mkdir ${INITIALIZER_PATH}
	-${VENV_PY_PATH} ${NETBOX_DIR}/manage.py copy_initializers_examples --path ${INITIALIZER_PATH}
	-for file in ${INITIALIZER_PATH}/*.yml; do sed -i "s/^# //g" "$$file"; done
	-${VENV_PY_PATH} ${NETBOX_DIR}/manage.py load_initializer_data --path ${INITIALIZER_PATH}

# NetBox Community Demo Data (https://github.com/netbox-community/netbox-demo-data)
.PHONY: clone-demo-data
clone-demo-data: ## Clone netbox-demo-data repository
	@if [ -d "${DEMO_DATA_PATH}" ]; then \
		echo "Updating existing netbox-demo-data..."; \
		cd ${DEMO_DATA_PATH} && git pull; \
	else \
		echo "Cloning netbox-demo-data..."; \
		git clone --depth 1 https://github.com/netbox-community/netbox-demo-data.git ${DEMO_DATA_PATH}; \
	fi

.PHONY: load-demo-data
load-demo-data: clone-demo-data ## Load NetBox community demo data (WARNING: drops existing database!)
	@echo "NetBox version detected: ${NETBOX_VERSION}"
	@if [ ! -f "${DEMO_DATA_PATH}/sql/netbox-demo-${NETBOX_VERSION}.sql" ]; then \
		echo "ERROR: Demo data for NetBox ${NETBOX_VERSION} not found!"; \
		echo "Available versions:"; \
		ls -1 ${DEMO_DATA_PATH}/sql/*.sql 2>/dev/null | sed 's/.*netbox-demo-/  /' | sed 's/.sql//'; \
		exit 1; \
	fi
	@echo "WARNING: This will DROP and recreate the NetBox database!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@echo "Dropping and recreating database..."
	PGPASSWORD=$${DB_PASSWORD} psql -h $${DB_HOST:-postgres} -U $${DB_USER:-netbox} -d postgres -c "DROP DATABASE IF EXISTS netbox;"
	PGPASSWORD=$${DB_PASSWORD} psql -h $${DB_HOST:-postgres} -U $${DB_USER:-netbox} -d postgres -c "CREATE DATABASE netbox;"
	@echo "Loading demo data for NetBox ${NETBOX_VERSION}..."
	PGPASSWORD=$${DB_PASSWORD} psql -h $${DB_HOST:-postgres} -U $${DB_USER:-netbox} -d netbox < ${DEMO_DATA_PATH}/sql/netbox-demo-${NETBOX_VERSION}.sql
	@echo "Running migrations for plugin..."
	${VENV_PY_PATH} ${NETBOX_DIR}/manage.py migrate
	@echo "Demo data loaded! Login with admin/admin"

.PHONY: load-plugin-demo
load-plugin-demo: ## Load plugin demo data (run after load-demo-data)
	@echo "Loading plugin demo data..."
	${VENV_PY_PATH} ${REPO_PATH}/.devcontainer/load_plugin_demo.py

.PHONY: demo-data-versions
demo-data-versions: clone-demo-data ## List available demo data versions
	@echo "Available NetBox demo data versions:"
	@ls -1 ${DEMO_DATA_PATH}/sql/*.sql 2>/dev/null | sed 's/.*netbox-demo-/  /' | sed 's/.sql//'
	@echo ""
	@echo "Current NetBox version: ${NETBOX_VERSION}"

# Composite targets
.PHONY: rebuild
rebuild: setup migrations migrate collectstatic ## Rebuild plugin (setup, migrations, static)

.PHONY: all
all: setup migrations migrate collectstatic initializers trace_paths ## Full setup with demo data

# Package building targets
.PHONY: pbuild
pbuild: clean ## Build Python package
	python3 -m pip install --upgrade build
	python3 -m build

.PHONY: pypipub
pypipub: ## Publish package to PyPI
	python3 -m pip install --upgrade twine
	python3 -m twine upload dist/*

# Release management
.PHONY: relpatch
relpatch: ## Create a patch release with bumpver
	$(eval GSTATUS := $(shell git status --porcelain))
ifneq ($(GSTATUS),)
	$(error Git status is not clean. $(GSTATUS))
endif
	git checkout main
	git remote update
	git pull origin main
	bumpver update --patch
	git push origin main --tags
