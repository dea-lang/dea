.DEFAULT_GOAL := help

VENV_DIR_REL := ../.venv
VENV_DIR := $(abspath $(VENV_DIR_REL))

ifeq ($(OS),Windows_NT)
VENV_PYTHON_DEFAULT := $(VENV_DIR)/Scripts/python.exe
else
VENV_PYTHON_DEFAULT := $(VENV_DIR)/bin/python
endif

HOST_PYTHON ?= $(shell if command -v python3 >/dev/null 2>&1; then printf '%s' python3; else printf '%s' python; fi)
VENV_PYTHON := $(shell if [ -x "$(VENV_DIR)/bin/python" ]; then printf '%s' "$(VENV_DIR)/bin/python"; elif [ -x "$(VENV_DIR)/Scripts/python.exe" ]; then printf '%s' "$(VENV_DIR)/Scripts/python.exe"; else printf '%s' $(VENV_PYTHON_DEFAULT); fi)
PYTHON ?= $(shell if [ -x "$(VENV_DIR)/bin/python" ]; then printf '%s' "$(VENV_DIR)/bin/python"; elif [ -x "$(VENV_DIR)/Scripts/python.exe" ]; then printf '%s' "$(VENV_DIR)/Scripts/python.exe"; else printf '%s' $(HOST_PYTHON); fi)
DEA_BUILD_DIR ?= build/dea
DOCKER_IMAGE ?= l0-test
VENV_UV_FLAGS := --quiet
VENV_PIP_FLAGS := --quiet --disable-pip-version-check
VENV_QUIET_LABEL := (quiet)

# On Windows (MinGW), statically link GCC runtime libraries in distribution and
# install builds so the resulting l0c binary does not depend on libwinpthread-1.dll.
ifeq ($(OS),Windows_NT)
DIST_L0_CFLAGS_DEFAULT := -O2 -static
else
DIST_L0_CFLAGS_DEFAULT := -O2
endif

# Extract dev + docs dependencies from pyproject.toml (requires Python 3.14+ for tomllib).
PIP_DEPS_CMD = import tomllib,pathlib;\
	g=tomllib.loads(pathlib.Path('pyproject.toml').read_text()).get('dependency-groups',{});\
	print(' '.join(d for d in g.get('dev',[])+g.get('docs',[]) if isinstance(d,str)))

.PHONY: \
	help \
	_check-python \
	venv \
	install-dev-stage1 \
	install-dev-stage2 \
	install-dev-stages \
	install \
	dist \
	use-dev-stage1 \
	use-dev-stage2 \
	test-stage1 \
	test-stage2 \
	test-stage2-trace \
	check-examples \
	test-dist \
	triple-test \
	test-dea-build \
	test-dist-fallback \
	test-release-tags \
	test-workflows \
	refresh-goldens \
	list-installed \
	test-all \
	print-dea-build-dir \
	docs \
	docs-pdf \
	clean \
	clean-all \
	clean-dea-build

help:
	@printf '%s\n' \
		'Dea/L0 installation and development workflow' \
		'' \
		'Targets:' \
		'  install            Install the self-hosted Stage 2 compiler under PREFIX.' \
		'  dist               Create a relocatable Stage 2 distribution archive under `build/`.' \
		'' \
		'Development targets:' \
		'  venv               Create or reuse the shared monorepo `../.venv` (prefer `uv`, fall back to `python -m venv`).' \
		'  use-dev-stage1     Install and switch the repo-local `l0c` alias to Stage 1.' \
		'  use-dev-stage2     Build and switch the repo-local `l0c` alias to Stage 2.' \
		'  install-dev-stages Prepare both Stage 1 and Stage 2 launchers under DEA_BUILD_DIR.' \
		'  test-all           Run the full Stage 1, Stage 2, example, workflow, and distribution validation suite.' \
		'  test-stage1        Validate the Stage 1 Python compiler test suite.' \
		'  test-stage2        Validate the Stage 2 compiler test suite; pass TESTS="name1 name2" to run selected cases.' \
		'  test-stage2-trace  Validate Stage 2 ARC and memory tracing behavior; pass TESTS="name1 name2" to run selected cases.' \
		'  triple-test        Run the Stage 2 triple-bootstrap check on its own.' \
		'  check-examples     Validate all `examples/*.l0` sources with the repo-local Stage 2 compiler; fail on warnings or errors.' \
		'' \
		'Workflow testing:' \
		'  test-dist          Validate the `make dist` packaging workflow end to end.' \
		'  test-dea-build     Validate the Dea build and install-prefix workflows.' \
		'  test-dist-fallback Validate Stage 2 provenance fallback without Git.' \
		'  test-release-tags  Validate the monorepo release-tag policy wiring.' \
		'  test-workflows     Run all workflow and distribution tests.' \
		'' \
		'Docker:' \
		'  docker             Explicitly run a target in the repo-owned Linux Docker container (CMD=<target>).' \
		'' \
		'Documentation targets:' \
		'  docs               Generate the project documentation.' \
		'  docs-pdf           Generate the project documentation, including the PDF manual.' \
		'' \
		'Other targets:' \
		'  refresh-goldens    Regenerate Stage 2 backend golden C fixtures from Stage 1.' \
		'  list-installed     List files installed by `make install` under PREFIX.' \
		'  help               Show this help text.' \
		'  clean              Remove all repo-local build artifacts under `build/*` (including temporary `dist` trees and archives), temporary test files, and default executables.' \
		'  clean-dea-build    Remove the repo-local Dea build tree (override with `DEA_BUILD_DIR`, see below).' \
		'  clean-all          Remove both repo-local build artifacts and the Dea build tree.' \
		'' \
		'Variables:' \
		'  PREFIX=<required>  Install prefix for `install`.' \
		'                     Example: make PREFIX=/opt/dea install' \
		'  DEA_BUILD_DIR=build/dea' \
		'                     Repo-local build root. Must stay inside the repository.' \
		'                     Example: make DEA_BUILD_DIR=build/dev-dea install-dev-stages' \
		'  TESTS=""' \
		'                     Optional Stage 2 test names for `test-stage2` or `test-stage2-trace`; blank runs the full suite.' \
		'                     Example: make test-stage2 TESTS="driver_test l0c_build_run_test"' \
		'                     Example: make test-stage2-trace TESTS="l0c_lib_test type_resolve_test"' \
		'  DOCKER_IMAGE=l0-test' \
		'                     Docker image tag used by `make docker`.' \
		'  DOCKER_L0_CC=<compiler>' \
		'                     Optional C compiler passed into the Docker run as `L0_CC` (`gcc` or `clang`).'

_check-python:
	@$(PYTHON) -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" 2>/dev/null \
		|| { printf 'error: Python 3.14+ is required (found: %s)\n' \
			"$$($(PYTHON) -c 'import sys; print(".".join(map(str,sys.version_info[:3])))' 2>/dev/null || echo 'none')" >&2; exit 1; }

venv: _check-python
	@if command -v uv >/dev/null 2>&1; then \
		if [ -x "$(VENV_PYTHON)" ]; then \
			printf '%s\n' 'make venv: syncing existing ../.venv with uv $(VENV_QUIET_LABEL)'; \
		fi; \
		UV_PROJECT_ENVIRONMENT="$(VENV_DIR)" uv sync $(VENV_UV_FLAGS) --group dev --group docs; \
	elif [ -x "$(VENV_PYTHON)" ]; then \
		printf '%s\n' 'make venv: refreshing existing ../.venv with pip $(VENV_QUIET_LABEL)'; \
		"$(VENV_PYTHON)" -m pip install $(VENV_PIP_FLAGS) $$("$(VENV_PYTHON)" -c "$(PIP_DEPS_CMD)"); \
	else \
		$(PYTHON) -m venv "$(VENV_DIR)"; \
		_vp="$$(if [ -x "$(VENV_DIR)/bin/python" ]; then printf '%s' "$(VENV_DIR)/bin/python"; else printf '%s' "$(VENV_DIR)/Scripts/python.exe"; fi)"; \
		"$$_vp" -m pip install $(VENV_PIP_FLAGS) $$("$$_vp" -c "$(PIP_DEPS_CMD)"); \
	fi

install-dev-stage1:
	$(PYTHON) ./scripts/gen_dist_tools.py write-stage1-wrapper --dea-build-dir "$(DEA_BUILD_DIR)"
	$(PYTHON) ./scripts/gen_dist_tools.py write-env-script --dea-build-dir "$(DEA_BUILD_DIR)"
	@printf 'Repo-local Stage 1 compiler version:\n'
	@"$(DEA_BUILD_DIR)/bin/l0c-stage1" --version

install-dev-stage2:
	DEA_BUILD_DIR="$(DEA_BUILD_DIR)" $(PYTHON) ./scripts/build_stage2_l0c.py
	$(PYTHON) ./scripts/gen_dist_tools.py write-env-script --dea-build-dir "$(DEA_BUILD_DIR)"
	@printf 'Repo-local Stage 2 compiler version:\n'
	@"$(DEA_BUILD_DIR)/bin/l0c-stage2" --version

install-dev-stages: install-dev-stage1 install-dev-stage2

install:
	@if [ -z "$(strip $(PREFIX))" ]; then \
		printf '%s\n' 'make install: PREFIX is required; example: make PREFIX=/tmp/l0-install L0_CC=gcc install' >&2; \
		exit 2; \
	fi
	L0_CFLAGS="$${L0_CFLAGS:-$(DIST_L0_CFLAGS_DEFAULT)}" $(PYTHON) ./scripts/gen_dist_tools.py install-prefix --prefix "$(PREFIX)"
	@printf 'Installed Stage 2 compiler version:\n'
	@"$(PREFIX)/bin/l0c-stage2" --version
	@printf '\n------------------------------------------------------------------------------\n'
ifeq ($(OS),Windows_NT)
	@cmd_env_path="$$(cygpath -w "$$(realpath "$(PREFIX)/bin/l0-env.cmd")")"; \
		printf 'Dea/L0 compiler installed at %s/bin/l0c.\nTo activate the installed compiler:\n\nIn an MSYS2 bash shell:\n\n    source %s/bin/l0-env.sh\n\nIn CMD:\n\n    call "%s"\n\nSee ../README-WINDOWS.md for PowerShell and direct-launcher guidance.' "$(PREFIX)" "$(PREFIX)" "$$cmd_env_path"
else
	@printf 'Dea/L0 compiler installed at %s/bin/l0c.\nTo add the installed compiler to your current PATH in this shell, run:\n\n    source %s/bin/l0-env.sh\n\nSee README.md for more information.' "$(PREFIX)" "$(PREFIX)"
endif
	@printf '\n------------------------------------------------------------------------------\n'

list-installed:
	@if [ -z "$(strip $(PREFIX))" ]; then \
		printf '%s\n' 'make list-installed: PREFIX is required; example: make PREFIX=/usr/local list-installed' >&2; \
		exit 2; \
	fi
	@$(PYTHON) ./scripts/gen_dist_tools.py list-installed --prefix "$(PREFIX)"

dist: venv
	L0_CFLAGS="$${L0_CFLAGS:-$(DIST_L0_CFLAGS_DEFAULT)}" $(PYTHON) ./scripts/gen_dist_tools.py make-dist

use-dev-stage1: install-dev-stage1
	$(PYTHON) ./scripts/gen_dist_tools.py set-alias --dea-build-dir "$(DEA_BUILD_DIR)" --stage stage1
	@printf '\n------------------------------------------------------------------------------\n'
ifeq ($(OS),Windows_NT)
	@cmd_env_path="$$(cygpath -w "$$(realpath "$(DEA_BUILD_DIR)/bin/l0-env.cmd")")"; \
		printf 'To activate the selected l0c stage in this shell:\n\nIn an MSYS2 bash shell:\n\n    source %s/bin/l0-env.sh\n\nIn CMD:\n\n    call "%s"\n\nThen run:\n\n    l0c --help\n\nSee ../README-WINDOWS.md for PowerShell and direct-launcher guidance.' "$(DEA_BUILD_DIR)" "$$cmd_env_path"
else
	@printf 'To activate the selected l0c stage in this shell, run:\n\n    source %s/bin/l0-env.sh\n\nThis adds %s/bin to your current PATH, so `l0c` invokes the selected compiler. See README.md for more information.' "$(DEA_BUILD_DIR)" "$(DEA_BUILD_DIR)"
endif
	@printf '\n------------------------------------------------------------------------------\n'

use-dev-stage2: install-dev-stage2
	$(PYTHON) ./scripts/gen_dist_tools.py set-alias --dea-build-dir "$(DEA_BUILD_DIR)" --stage stage2
	@printf '\n------------------------------------------------------------------------------\n'
ifeq ($(OS),Windows_NT)
	@cmd_env_path="$$(cygpath -w "$$(realpath "$(DEA_BUILD_DIR)/bin/l0-env.cmd")")"; \
		printf 'To activate the selected l0c stage in this shell:\n\nIn an MSYS2 bash shell:\n\n    source %s/bin/l0-env.sh\n\nIn CMD:\n\n    call "%s"\n\nThen run:\n\n    l0c --help\n\nSee ../README-WINDOWS.md for PowerShell and direct-launcher guidance.' "$(DEA_BUILD_DIR)" "$$cmd_env_path"
else
	@printf 'To activate the selected l0c stage in this shell, run:\n\n    source %s/bin/l0-env.sh\n\nThis adds %s/bin to your current PATH, so `l0c` invokes the selected compiler. See README.md for more information.' "$(DEA_BUILD_DIR)" "$(DEA_BUILD_DIR)"
endif
	@printf '\n------------------------------------------------------------------------------\n'

test-stage1: | venv
	"$(VENV_PYTHON)" -m pytest -n auto -q --quiet-progress

test-stage2: install-dev-stage2 | venv
	DEA_BUILD_DIR="$(DEA_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage2_l0/scripts/run_tests.py $(TESTS)

test-stage2-trace: install-dev-stage2 | venv
	DEA_BUILD_DIR="$(DEA_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage2_l0/scripts/run_trace_tests.py $(TESTS)

check-examples: install-dev-stage2
	"$(PYTHON)" ../scripts/check_examples.py --compiler "$(DEA_BUILD_DIR)/bin/l0c-stage2" --examples-dir examples --extension .l0 --label "L0 Stage 2"

test-dist: | venv
	"$(VENV_PYTHON)" ./tests/test_make_dist_workflow.py

triple-test: install-dev-stage2 | venv
	DEA_BUILD_DIR="$(DEA_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py

test-dea-build: | venv
	"$(VENV_PYTHON)" ./tests/test_make_dea_build_workflow.py

test-dist-fallback: | venv
	"$(VENV_PYTHON)" ./tests/test_dist_tools_lib_fallback.py

test-release-tags: | venv
	"$(VENV_PYTHON)" ./tests/test_release_tag_policy.py

test-workflows: test-dist test-dea-build test-dist-fallback test-release-tags
	@printf 'All workflow tests passed!\n'

test-all: test-stage1 test-stage2 test-stage2-trace check-examples test-workflows

refresh-goldens: venv
	"$(VENV_PYTHON)" ./scripts/refresh_stage2_backend_goldens.py

print-dea-build-dir:
	@printf '%s\n' "$(DEA_BUILD_DIR)"

docs:
	$(PYTHON) ./scripts/gen_docs.py --strict

docs-pdf:
	$(PYTHON) ./scripts/gen_docs.py --strict --pdf

clean:
	rm -rf ./build/*
	rm -f ./a.out ./a.exe
	rm -f ./compiler/stage2_l0/a.out ./compiler/stage2_l0/a.exe
	rm -f ./compiler/stage2_l0/tests/.tmp*

clean-dea-build:
	$(PYTHON) ./scripts/gen_dist_tools.py clean-dea-build --dea-build-dir "$(DEA_BUILD_DIR)"

clean-all: clean clean-dea-build

docker:
	@if [ -z "$(CMD)" ]; then \
		echo "Usage: make docker CMD=<target>"; \
		echo "Example: make docker CMD=test-all"; \
		exit 2; \
	else \
		docker build -t "$(DOCKER_IMAGE)" . && docker run --rm $(if $(strip $(DOCKER_L0_CC)),-e L0_CC=$(DOCKER_L0_CC)) "$(DOCKER_IMAGE)" make $(CMD); \
	fi
