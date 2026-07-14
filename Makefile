.DEFAULT_GOAL := help

DEA_LEVEL_DIRS ?= l0 l1
ROOT_CLEAN_PATHS := build .pytest_cache __pycache__ pytest-of-*

VENV_DIR := $(abspath ./.venv)

ifeq ($(OS),Windows_NT)
VENV_PYTHON_DEFAULT := $(VENV_DIR)/Scripts/python.exe
else
VENV_PYTHON_DEFAULT := $(VENV_DIR)/bin/python
endif

HOST_PYTHON ?= $(shell if command -v python3 >/dev/null 2>&1; then printf '%s' python3; else printf '%s' python; fi)
VENV_PYTHON := $(shell if [ -x "$(VENV_DIR)/bin/python" ]; then printf '%s' "$(VENV_DIR)/bin/python"; elif [ -x "$(VENV_DIR)/Scripts/python.exe" ]; then printf '%s' "$(VENV_DIR)/Scripts/python.exe"; else printf '%s' $(VENV_PYTHON_DEFAULT); fi)
PYTHON ?= $(shell if [ -x "$(VENV_DIR)/bin/python" ]; then printf '%s' "$(VENV_DIR)/bin/python"; elif [ -x "$(VENV_DIR)/Scripts/python.exe" ]; then printf '%s' "$(VENV_DIR)/Scripts/python.exe"; else printf '%s' $(HOST_PYTHON); fi)

VENV_UV_FLAGS := --quiet
VENV_PIP_FLAGS := --quiet --disable-pip-version-check
VENV_QUIET_LABEL := (quiet)

# Extract dev + docs dependencies from the root pyproject.toml (requires Python 3.14+ for tomllib).
PIP_DEPS_CMD = import tomllib,pathlib;\
	g=tomllib.loads(pathlib.Path('pyproject.toml').read_text()).get('dependency-groups',{});\
	print(' '.join(d for d in g.get('dev',[])+g.get('docs',[]) if isinstance(d,str)))

.PHONY: help venv clean clean-all test test-all _check-level-dirs _check-python _clean-root-paths

help:
	@printf '%s\n' \
		'Dea monorepo maintenance workflow' \
		'' \
		'Targets:' \
		'  help               Show this help text.' \
		'  venv               Create or sync the shared monorepo `./.venv` (prefer `uv`, fall back to `python -m venv` + `pip`).' \
		'  test               Run `make test` in each registered level without dedicated trace sweeps.' \
		'  test-all           Run full validation, including dedicated trace sweeps, in each registered level.' \
		'  clean              Run `make clean` in each registered level, then remove root caches/artifacts.' \
		'  clean-all          Run `make clean-all` in each registered level, then remove root caches/artifacts.' \
		'' \
		'Registered levels:' \
		'  DEA_LEVEL_DIRS=$(DEA_LEVEL_DIRS)' \
		'' \
		'Level-specific development commands still run inside a level directory.' \
		'Example: `cd l0 && make test-all`'

_check-level-dirs:
	@for level in $(DEA_LEVEL_DIRS); do \
		if [ ! -d "$$level" ]; then \
			printf 'error: registered level directory `%s` does not exist\n' "$$level" >&2; \
			exit 2; \
		fi; \
		if [ ! -f "$$level/Makefile" ]; then \
			printf 'error: registered level directory `%s` does not contain a Makefile\n' "$$level" >&2; \
			exit 2; \
		fi; \
	done

_check-python:
	@$(PYTHON) -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" 2>/dev/null \
		|| { printf 'error: Python 3.14+ is required (found: %s)\n' \
			"$$($(PYTHON) -c 'import sys; print(".".join(map(str,sys.version_info[:3])))' 2>/dev/null || echo 'none')" >&2; exit 1; }

venv: _check-python
	@if command -v uv >/dev/null 2>&1; then \
		if [ -n "$$DEA_DEBUG_VENV" ]; then \
			printf '%s\n' 'make venv debug: entering uv sync branch'; \
			printf 'make venv debug: workdir %s\n' "$$(pwd)"; \
			printf 'make venv debug: VENV_DIR=%s\n' "$(VENV_DIR)"; \
			printf 'make venv debug: PYTHON=%s\n' "$(PYTHON)"; \
			printf 'make venv debug: VENV_PYTHON=%s\n' "$(VENV_PYTHON)"; \
			printf 'make venv debug: UV_PROJECT_ENVIRONMENT=%s\n' "$(VENV_DIR)"; \
			command -v uv || true; \
			uv --version || true; \
			if command -v cygpath >/dev/null 2>&1; then \
				printf 'make venv debug: cygpath -w VENV_DIR=%s\n' "$$(cygpath -w "$(VENV_DIR)")"; \
			fi; \
			ls -ld "$(VENV_DIR)" 2>/dev/null || true; \
			ls -l "$(VENV_DIR)/Scripts" 2>/dev/null || true; \
			ls -l "$(VENV_DIR)/bin" 2>/dev/null || true; \
		fi; \
		if [ -x "$(VENV_PYTHON)" ]; then \
			printf '%s\n' 'make venv: syncing existing ./.venv with uv $(VENV_QUIET_LABEL)'; \
		fi; \
		uv_project_environment="$(VENV_DIR)"; \
		if [ "$(OS)" = "Windows_NT" ] && command -v cygpath >/dev/null 2>&1; then \
			uv_project_environment="$$(cygpath -w "$(VENV_DIR)")"; \
		fi; \
		UV_PROJECT_ENVIRONMENT="$$uv_project_environment" uv sync $(VENV_UV_FLAGS) --all-groups; \
	elif [ -x "$(VENV_PYTHON)" ]; then \
		printf '%s\n' 'make venv: refreshing existing ./.venv with pip $(VENV_QUIET_LABEL)'; \
		"$(VENV_PYTHON)" -m pip install $(VENV_PIP_FLAGS) $$("$(VENV_PYTHON)" -c "$(PIP_DEPS_CMD)"); \
	else \
		$(PYTHON) -m venv "$(VENV_DIR)"; \
		_vp="$$(if [ -x "$(VENV_DIR)/bin/python" ]; then printf '%s' "$(VENV_DIR)/bin/python"; else printf '%s' "$(VENV_DIR)/Scripts/python.exe"; fi)"; \
		"$$_vp" -m pip install $(VENV_PIP_FLAGS) $$("$$_vp" -c "$(PIP_DEPS_CMD)"); \
	fi

clean: _check-level-dirs
	@for level in $(DEA_LEVEL_DIRS); do \
		printf '==> %s: make clean\n' "$$level"; \
		$(MAKE) -C "$$level" clean || exit $$?; \
	done
	@$(MAKE) _clean-root-paths

clean-all: _check-level-dirs
	@for level in $(DEA_LEVEL_DIRS); do \
		printf '==> %s: make clean-all\n' "$$level"; \
		$(MAKE) -C "$$level" clean-all || exit $$?; \
	done
	@$(MAKE) _clean-root-paths

_clean-root-paths:
	@for pattern in $(ROOT_CLEAN_PATHS); do \
		for path in $$pattern; do \
			if [ -e "$$path" ]; then \
				printf '==> removing %s\n' "$$path"; \
				rm -rf -- "$$path"; \
			fi; \
		done; \
	done

test: _check-level-dirs
	@for level in $(DEA_LEVEL_DIRS); do \
		printf '==> %s: make test\n' "$$level"; \
		$(MAKE) -C "$$level" test || exit $$?; \
	done

test-all: _check-level-dirs
	@for level in $(DEA_LEVEL_DIRS); do \
		printf '==> %s: make test-all\n' "$$level"; \
		$(MAKE) -C "$$level" test-all || exit $$?; \
	done
