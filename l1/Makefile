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
L1_BUILD_DIR ?= build/dea
DOCKER_IMAGE ?= l1-test
VENV_UV_FLAGS := --quiet
VENV_PIP_FLAGS := --quiet --disable-pip-version-check
VENV_QUIET_LABEL := (quiet)
AR ?= ar
L1_RUNTIME_CC ?= $(if $(strip $(L1_CC)),$(L1_CC),$(or $(shell if command -v clang >/dev/null 2>&1; then printf '%s' clang; elif command -v gcc >/dev/null 2>&1; then printf '%s' gcc; elif command -v cc >/dev/null 2>&1; then printf '%s' cc; fi),$(if $(filter-out undefined default,$(origin CC)),$(CC))))
L1_TCC_OBJ_CC ?= $(or $(shell if command -v tcc >/dev/null 2>&1; then printf '%s' tcc; fi),$(if $(filter-out undefined default,$(origin TCC)),$(TCC)))
L1_TCC_OBJ_CC_IS_EXPLICIT := $(if $(filter file,$(origin L1_TCC_OBJ_CC)),,yes)
RUNTIME_ROOT := compiler/shared/runtime
RUNTIME_BUILD_DIR := $(L1_BUILD_DIR)/runtime
RUNTIME_TCC_BUILD_DIR := $(RUNTIME_BUILD_DIR)/tcc
RUNTIME_INCLUDE_DIR := $(L1_BUILD_DIR)/include
RUNTIME_LIB_DIR := $(L1_BUILD_DIR)/lib
RUNTIME_SOURCE_NAMES := dea_rt_panic.c dea_rt_sys.c dea_rt_math.c dea_rt_rand.c dea_rt_string.c dea_rt_alloc.c dea_rt_io.c dea_rt_hash.c dea_rt_time.c
RUNTIME_SOURCES := $(addprefix $(RUNTIME_ROOT)/src/,$(RUNTIME_SOURCE_NAMES))
RUNTIME_DEFAULT_OBJS := $(patsubst %.c,$(RUNTIME_BUILD_DIR)/default/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TRACED_OBJS := $(patsubst %.c,$(RUNTIME_BUILD_DIR)/traced/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TCC_DEFAULT_OBJS := $(patsubst %.c,$(RUNTIME_TCC_BUILD_DIR)/default/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TCC_TRACED_OBJS := $(patsubst %.c,$(RUNTIME_TCC_BUILD_DIR)/traced/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_DEFAULT_LIB := $(RUNTIME_LIB_DIR)/libdea_rt.a
RUNTIME_TRACED_LIB := $(RUNTIME_LIB_DIR)/libdea_rt_traced.a
RUNTIME_PUBLIC_HEADERS := $(RUNTIME_INCLUDE_DIR)/dea_rt.h $(RUNTIME_INCLUDE_DIR)/l1_real.h
RUNTIME_CFLAGS ?= -O2 -std=c99
RUNTIME_INCLUDE_FLAGS := -I$(RUNTIME_ROOT)/include -I$(RUNTIME_ROOT)/internal

PIP_DEPS_CMD = import tomllib,pathlib;\
	g=tomllib.loads(pathlib.Path('pyproject.toml').read_text()).get('dependency-groups',{});\
	print(' '.join(d for d in g.get('dev',[])+g.get('docs',[]) if isinstance(d,str)))

.PHONY: help _check-python venv runtime clean-runtime clean-all runtime-tcc-objects _ensure-bootstrap-l0-stage2 build-stage1 use-dev-stage1 test-stage1 test-stage1-trace test-stage1-trace-all check-examples test-all test-docker print-l1-build-dir clean docker

help:
	@printf '%s\n' \
		'Dea/L1 bootstrap workflow' \
		'' \
		'Targets:' \
		'  venv               Create or reuse the shared monorepo `../.venv`.' \
		'  runtime            Build the repo-local L1 runtime archives and public headers under `$(L1_BUILD_DIR)`.' \
		'  use-dev-stage1     Build and switch the repo-local `l1c` alias to Stage 1.' \
		'  test-all           Run the default L1 validation suite (`test-stage1`, default trace checks, and examples).' \
		'  test-docker        Run the full L1 validation suite under the repo-owned Linux container (POSIX reference path).' \
		'  test-stage1        Run the L1 Stage 1 `.l0` implementation tests with the built repo-local compiler.' \
		'  test-stage1-trace  Run default L1 Stage 1 ARC/memory trace checks; skips intentionally slow trace tests.' \
		'  test-stage1-trace-all' \
		'                     Run L1 Stage 1 ARC/memory trace checks including intentionally slow trace tests.' \
		'  check-examples     Validate all `examples/*.l1` sources with the repo-local Stage 1 compiler; fail on warnings or errors.' \
		'  clean              Remove repo-local build artifacts under `build/*`.' \
		'  clean-runtime      Remove only repo-local runtime build products under `$(L1_BUILD_DIR)`.' \
		'  clean-all          Run both `clean` and `clean-runtime`.' \
		'' \
		'Docker:' \
		'  docker             Explicitly run a target in the repo-owned Linux Docker container (CMD=<target>).' \
		'' \
		'Variables:' \
		'  L1_BUILD_DIR=build/dea' \
		'                     Repo-local L1 build root.' \
		'  L1_BOOTSTRAP_L0C=<path>' \
		'                     Explicit upstream L0 Stage 2 compiler wrapper or native binary.' \
		'  TESTS=""' \
		'                     Optional Stage 1 test names for `test-stage1` and trace targets; forwarded by `make docker` when set.' \
		'  L1_RUNTIME_CC=<compiler>' \
		'                     Runtime archive C compiler (defaults to `L1_CC`, then clang/gcc/cc, then `CC`). Example: `make clean-runtime runtime L1_RUNTIME_CC=gcc-15`.' \
		'  L1_TRACE_TEST_JOBS=<n>' \
		'                     Override parallelism for `test-stage1-trace*`; when unset, trace runs follow the normal default job policy.' \
		'  L1_TRACE_ARTIFACT_DIR=<dir>' \
		'                     Optional trace artifact directory. Local trace runs write artifacts there; `make docker` bind-mounts the host directory and preserves artifacts across `docker run --rm`.' \
		'  L1_TCC_OBJ_CC=<compiler>' \
		'                     TinyCC compiler for repo-local tcc runtime objects (defaults to `tcc`, then `TCC`). When absent without an explicit override, `make runtime` prints a notice and skips the specialized tcc object build.' \
		'  DOCKER_IMAGE=l1-test' \
		'                     Docker image tag used by `make docker`.' \
		'  DOCKER_L0_CC=<compiler>' \
		'                     Optional upstream L0 C compiler passed into the Docker run as `L0_CC` (`gcc` or `clang`).' \
		'  L1_TEST_JOBS=<n>' \
		'                     Optional normal-test parallelism override; forwarded by `make docker` when set.' \
		'  L1_TRACE_TEST_JOBS=<n>' \
		'                     Optional trace-test parallelism override; forwarded by `make docker` when set.' \
		'  L1_TRACE_ARTIFACT_DIR=<dir>' \
		'                     Optional host trace-artifact directory; `make docker` mounts it at `/trace-artifacts` and forwards that path into the container.' \
		'' \
		'Default local bootstrap flow:' \
		'  1. `make use-dev-stage1`  # auto-prepares ../l0 Stage 2 if needed' \
		'  2. `source build/dea/bin/l1-env.sh`' \
		'  3. `l1c --help`'

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

_ensure-bootstrap-l0-stage2:
	@if [ -n "$${L1_BOOTSTRAP_L0C:-}" ]; then \
		printf '%s\n' 'make build-stage1: using explicit L1_BOOTSTRAP_L0C override'; \
	elif [ -x ../l0/build/dea/bin/l0c-stage2 ] || [ -x ../l0/build/dea/bin/l0c-stage2.cmd ]; then \
		:; \
	else \
		printf '%s\n' 'make build-stage1: preparing repo-local upstream L0 Stage 2 compiler'; \
		$(MAKE) -C ../l0 use-dev-stage2; \
	fi
	@if [ -z "$${L1_BOOTSTRAP_L0C:-}" ] && [ ! -x ../l0/build/dea/bin/l0c-stage2 ] && [ ! -x ../l0/build/dea/bin/l0c-stage2.cmd ]; then \
		printf '%s\n' 'make build-stage1: missing repo-local upstream compiler at ../l0/build/dea/bin/l0c-stage2 after bootstrap preparation' >&2; \
		exit 1; \
	fi

$(RUNTIME_BUILD_DIR)/default:
	@mkdir -p "$@"

$(RUNTIME_BUILD_DIR)/traced:
	@mkdir -p "$@"

$(RUNTIME_TCC_BUILD_DIR)/default:
	@mkdir -p "$@"

$(RUNTIME_TCC_BUILD_DIR)/traced:
	@mkdir -p "$@"

$(RUNTIME_LIB_DIR):
	@mkdir -p "$@"

$(RUNTIME_INCLUDE_DIR):
	@mkdir -p "$@"

$(RUNTIME_BUILD_DIR)/default/%.o: $(RUNTIME_ROOT)/src/%.c | $(RUNTIME_BUILD_DIR)/default
	$(L1_RUNTIME_CC) $(RUNTIME_CFLAGS) $(RUNTIME_INCLUDE_FLAGS) -c "$<" -o "$@"

$(RUNTIME_BUILD_DIR)/traced/%.o: $(RUNTIME_ROOT)/src/%.c | $(RUNTIME_BUILD_DIR)/traced
	$(L1_RUNTIME_CC) $(RUNTIME_CFLAGS) -DDEA_TRACE_ARC -DDEA_TRACE_MEMORY $(RUNTIME_INCLUDE_FLAGS) -c "$<" -o "$@"

$(RUNTIME_TCC_BUILD_DIR)/default/%.o: $(RUNTIME_ROOT)/src/%.c | $(RUNTIME_TCC_BUILD_DIR)/default
	"$(L1_TCC_OBJ_CC)" $(RUNTIME_CFLAGS) $(RUNTIME_INCLUDE_FLAGS) -c "$<" -o "$@"

$(RUNTIME_TCC_BUILD_DIR)/traced/%.o: $(RUNTIME_ROOT)/src/%.c | $(RUNTIME_TCC_BUILD_DIR)/traced
	"$(L1_TCC_OBJ_CC)" $(RUNTIME_CFLAGS) -DDEA_TRACE_ARC -DDEA_TRACE_MEMORY $(RUNTIME_INCLUDE_FLAGS) -c "$<" -o "$@"

$(RUNTIME_DEFAULT_LIB): $(RUNTIME_DEFAULT_OBJS) | $(RUNTIME_LIB_DIR)
	$(AR) rcs "$@" $(RUNTIME_DEFAULT_OBJS)

$(RUNTIME_TRACED_LIB): $(RUNTIME_TRACED_OBJS) | $(RUNTIME_LIB_DIR)
	$(AR) rcs "$@" $(RUNTIME_TRACED_OBJS)

$(RUNTIME_INCLUDE_DIR)/dea_rt.h: $(RUNTIME_ROOT)/include/dea_rt.h | $(RUNTIME_INCLUDE_DIR)
	cp "$<" "$@"

$(RUNTIME_INCLUDE_DIR)/l1_real.h: $(RUNTIME_ROOT)/include/l1_real.h | $(RUNTIME_INCLUDE_DIR)
	cp "$<" "$@"

ifeq ($(strip $(L1_TCC_OBJ_CC)),)
runtime-tcc-objects:
ifeq ($(strip $(L1_TCC_OBJ_CC_IS_EXPLICIT)),)
	@printf '%s\n' 'make runtime: no tcc: skipping specialized runtime build'
endif
else
runtime-tcc-objects: $(RUNTIME_TCC_DEFAULT_OBJS) $(RUNTIME_TCC_TRACED_OBJS)
endif

runtime: $(RUNTIME_DEFAULT_LIB) $(RUNTIME_TRACED_LIB) $(RUNTIME_PUBLIC_HEADERS) runtime-tcc-objects

clean-runtime:
	rm -rf "$(RUNTIME_BUILD_DIR)" "$(RUNTIME_LIB_DIR)"

clean-all:
	@$(MAKE) clean
	@$(MAKE) clean-runtime

build-stage1: venv runtime _ensure-bootstrap-l0-stage2
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(PYTHON)" ./scripts/build_stage1_l1c.py
	@printf 'Repo-local L1 Stage 1 compiler version:\n'
	@"$(L1_BUILD_DIR)/bin/l1c-stage1" --version

use-dev-stage1: build-stage1
	@printf '\n------------------------------------------------------------------------------\n'
ifeq ($(OS),Windows_NT)
	@cmd_env_path="$$(cygpath -w "$$(realpath "$(L1_BUILD_DIR)/bin/l1-env.cmd")")"; \
		printf 'To activate the selected l1c stage in this shell:\n\nIn an MSYS2 bash shell:\n\n    source %s/bin/l1-env.sh\n\nIn CMD:\n\n    call "%s"\n\nThen run:\n\n    l1c --help\n\nSee ../README-WINDOWS.md for PowerShell and direct-launcher guidance.' "$(L1_BUILD_DIR)" "$$cmd_env_path"
else
	@printf 'To activate the selected l1c stage in this shell, run:\n\n    source %s/bin/l1-env.sh\n\nThis adds %s/bin to your current PATH, so `l1c` invokes the selected compiler. See README.md for more information.' "$(L1_BUILD_DIR)" "$(L1_BUILD_DIR)"
endif
	@printf '\n------------------------------------------------------------------------------\n'

test-stage1: venv build-stage1
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_tests.py $(TESTS)

test-stage1-trace: venv build-stage1
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py $(TESTS)

test-stage1-trace-all: venv build-stage1
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py --include-slow $(TESTS)

check-examples: build-stage1
	"$(PYTHON)" ../scripts/check_examples.py --compiler "$(L1_BUILD_DIR)/bin/l1c-stage1" --examples-dir examples --extension .l1 --label "L1 Stage 1"

test-all: test-stage1 test-stage1-trace check-examples

test-docker:
	$(MAKE) docker CMD=test-all

print-l1-build-dir:
	@printf '%s\n' "$(L1_BUILD_DIR)"

clean:
	rm -rf ./build/*
	rm -f ./a.out ./a.exe
	rm -f ./compiler/stage1_l0/a.out ./compiler/stage1_l0/a.exe
	rm -f ./compiler/stage1_l0/tests/.tmp*

docker:
	@if [ -z "$(CMD)" ]; then \
		echo "Usage: make docker CMD=<target>"; \
		echo "Example: make docker CMD=test-all"; \
		exit 2; \
	else \
		$(if $(strip $(L1_TRACE_ARTIFACT_DIR)),mkdir -p "$(L1_TRACE_ARTIFACT_DIR)" &&) \
		docker build -f Dockerfile -t "$(DOCKER_IMAGE)" .. && docker run --rm \
			$(if $(strip $(DOCKER_L0_CC)),-e "L0_CC=$(DOCKER_L0_CC)") \
			$(if $(strip $(L1_TEST_JOBS)),-e "L1_TEST_JOBS=$(L1_TEST_JOBS)") \
			$(if $(strip $(L1_TRACE_TEST_JOBS)),-e "L1_TRACE_TEST_JOBS=$(L1_TRACE_TEST_JOBS)") \
			$(if $(strip $(TESTS)),-e "TESTS=$(TESTS)") \
			$(if $(strip $(L1_TRACE_ARTIFACT_DIR)),-v "$(abspath $(L1_TRACE_ARTIFACT_DIR)):/trace-artifacts" -e "L1_TRACE_ARTIFACT_DIR=/trace-artifacts") \
			"$(DOCKER_IMAGE)" make $(CMD); \
	fi
