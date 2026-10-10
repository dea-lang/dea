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
L2_BUILD_DIR ?= build/dea
L2_COMPILER_RT_CHECK_BASIC ?= 1
L2_COMPILER_RT_UNCHECKED ?=
L2_COMPILER_RT_QUARANTINE_MAX_BYTES ?=
L2_COMPILER_RT_QUARANTINE_MAX_COUNT ?= 256
TRACE_SMOKE_TESTS := analysis_trace_test array_test io_errno_test lexer_error_cleanup_test slice_trace_test string_vector_test
L2_TEST_SMOKE_TESTS := array_test parser_test analysis_test expr_types_test interface_test backend_test c_emitter_test driver_test l2_language_identity_test.py
AR ?= ar
L2_RUNTIME_CC ?= $(if $(strip $(L2_CC)),$(L2_CC),$(or $(shell if command -v clang >/dev/null 2>&1; then printf '%s' clang; elif command -v gcc >/dev/null 2>&1; then printf '%s' gcc; elif command -v cc >/dev/null 2>&1; then printf '%s' cc; fi),$(if $(filter-out undefined default,$(origin CC)),$(CC))))
L2_TCC_OBJ_CC ?= $(or $(shell if command -v tcc >/dev/null 2>&1; then printf '%s' tcc; fi),$(if $(filter-out undefined default,$(origin TCC)),$(TCC)))
L2_TCC_OBJ_CC_IS_EXPLICIT := $(if $(filter file,$(origin L2_TCC_OBJ_CC)),,yes)
empty :=
space := $(empty) $(empty)
# Escape paths only in Make targets and prerequisites; recipes use quoted raw paths.
make-path = $(subst $(space),\$(space),$(1))
RUNTIME_ROOT := compiler/shared/runtime
RUNTIME_BUILD_DIR := $(L2_BUILD_DIR)/runtime
RUNTIME_TCC_BUILD_DIR := $(RUNTIME_BUILD_DIR)/tcc
RUNTIME_INCLUDE_DIR := $(L2_BUILD_DIR)/include
RUNTIME_LIB_DIR := $(L2_BUILD_DIR)/lib
RUNTIME_SOURCE_NAMES := dea_rt_panic.c dea_rt_sys.c dea_rt_math.c dea_rt_rand.c dea_rt_string.c dea_rt_alloc.c dea_rt_io.c dea_rt_hash.c dea_rt_time.c
RUNTIME_TRACED_SOURCE_NAMES := dea_rt_trace.c $(RUNTIME_SOURCE_NAMES)
RUNTIME_SOURCES := $(addprefix $(RUNTIME_ROOT)/src/,$(RUNTIME_SOURCE_NAMES))
RUNTIME_HEADERS := $(wildcard $(RUNTIME_ROOT)/include/*.h $(RUNTIME_ROOT)/internal/*.h)
RUNTIME_DEFAULT_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_BUILD_DIR))/default/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TRACED_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_BUILD_DIR))/traced/%.o,$(RUNTIME_TRACED_SOURCE_NAMES))
RUNTIME_UNCHECKED_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_BUILD_DIR))/unchecked/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_CHECK_BASIC_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_BUILD_DIR))/check_basic/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TCC_DEFAULT_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/default/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TCC_TRACED_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/traced/%.o,$(RUNTIME_TRACED_SOURCE_NAMES))
RUNTIME_TCC_UNCHECKED_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/unchecked/%.o,$(RUNTIME_SOURCE_NAMES))
RUNTIME_TCC_CHECK_BASIC_OBJS := $(patsubst %.c,$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/check_basic/%.o,$(RUNTIME_SOURCE_NAMES))
# Each object variant depends on a content-sensitive configuration stamp. The
# stamp recipe runs on every make invocation but preserves its mtime when the
# compiler/flags/mode content is identical, keeping incremental builds cheap.
RUNTIME_DEFAULT_CONFIG := $(RUNTIME_BUILD_DIR)/default/.build-config
RUNTIME_TRACED_CONFIG := $(RUNTIME_BUILD_DIR)/traced/.build-config
RUNTIME_UNCHECKED_CONFIG := $(RUNTIME_BUILD_DIR)/unchecked/.build-config
RUNTIME_CHECK_BASIC_CONFIG := $(RUNTIME_BUILD_DIR)/check_basic/.build-config
RUNTIME_TCC_DEFAULT_CONFIG := $(RUNTIME_TCC_BUILD_DIR)/default/.build-config
RUNTIME_TCC_TRACED_CONFIG := $(RUNTIME_TCC_BUILD_DIR)/traced/.build-config
RUNTIME_TCC_UNCHECKED_CONFIG := $(RUNTIME_TCC_BUILD_DIR)/unchecked/.build-config
RUNTIME_TCC_CHECK_BASIC_CONFIG := $(RUNTIME_TCC_BUILD_DIR)/check_basic/.build-config
RUNTIME_DEFAULT_LIB := $(RUNTIME_LIB_DIR)/libdea_rt.a
RUNTIME_TRACED_LIB := $(RUNTIME_LIB_DIR)/libdea_rt_traced.a
RUNTIME_UNCHECKED_LIB := $(RUNTIME_LIB_DIR)/libdea_rt_unchecked.a
RUNTIME_CHECK_BASIC_LIB := $(RUNTIME_LIB_DIR)/libdea_rt_check_basic.a
RUNTIME_PUBLIC_HEADERS := $(call make-path,$(RUNTIME_INCLUDE_DIR))/dea_rt.h $(call make-path,$(RUNTIME_INCLUDE_DIR))/l1_real.h
RUNTIME_CFLAGS ?= -O2 -std=c99
RUNTIME_TUNING_CFLAGS := $(if $(strip $(L2_RT_QUARANTINE_MAX_BYTES)),-D_RT_QUARANTINE_MAX_BYTES=$(L2_RT_QUARANTINE_MAX_BYTES)) $(if $(strip $(L2_RT_QUARANTINE_MAX_COUNT)),-D_RT_QUARANTINE_MAX_COUNT=$(L2_RT_QUARANTINE_MAX_COUNT))
RUNTIME_INCLUDE_FLAGS := -I$(RUNTIME_ROOT)/include -I$(RUNTIME_ROOT)/internal

$(call make-path,$(RUNTIME_BUILD_DIR))/default:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_BUILD_DIR))/traced:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_BUILD_DIR))/unchecked:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_BUILD_DIR))/check_basic:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/default:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/traced:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/unchecked:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_TCC_BUILD_DIR))/check_basic:
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_LIB_DIR)):
	@mkdir -p "$@"

$(call make-path,$(RUNTIME_INCLUDE_DIR)):
	@mkdir -p "$@"

FORCE:

define write-runtime-build-config
	@tmp="$@.tmp"; \
	{ \
		printf '%s\n' "compiler=$(strip $(1))"; \
		printf '%s\n' "cflags=$(strip $(RUNTIME_CFLAGS))"; \
		printf '%s\n' "tuning=$(strip $(2))"; \
		printf '%s\n' "mode=$(strip $(3))"; \
		printf '%s\n' "includes=$(strip $(RUNTIME_INCLUDE_FLAGS))"; \
	} > "$$tmp"; \
	if test -r "$@" && cmp -s "$$tmp" "$@"; then \
		rm -f "$$tmp"; \
	else \
		mv -f "$$tmp" "$@"; \
	fi
endef

$(call make-path,$(RUNTIME_DEFAULT_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/default
	$(call write-runtime-build-config,$(L2_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),default)

$(call make-path,$(RUNTIME_TRACED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/traced
	$(call write-runtime-build-config,$(L2_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),DEA_TRACE_ARC DEA_TRACE_MEMORY)

$(call make-path,$(RUNTIME_UNCHECKED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/unchecked
	$(call write-runtime-build-config,$(L2_RUNTIME_CC),,DEA_RT_UNCHECKED)

$(call make-path,$(RUNTIME_CHECK_BASIC_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/check_basic
	$(call write-runtime-build-config,$(L2_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),DEA_RT_CHECK_BASIC)

$(call make-path,$(RUNTIME_TCC_DEFAULT_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/default
	$(call write-runtime-build-config,$(L2_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),default)

$(call make-path,$(RUNTIME_TCC_TRACED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/traced
	$(call write-runtime-build-config,$(L2_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),DEA_TRACE_ARC DEA_TRACE_MEMORY)

$(call make-path,$(RUNTIME_TCC_UNCHECKED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/unchecked
	$(call write-runtime-build-config,$(L2_TCC_OBJ_CC),,DEA_RT_UNCHECKED)

$(call make-path,$(RUNTIME_TCC_CHECK_BASIC_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/check_basic
	$(call write-runtime-build-config,$(L2_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),DEA_RT_CHECK_BASIC)

# Explicit object rules preserve space-bearing roots on supported Make versions.
define runtime-object-rule
$(call make-path,$(1)/$(2)/$(3:.c=.o)): $(RUNTIME_ROOT)/src/$(3) $(RUNTIME_HEADERS) $(call make-path,$(6)) | $(call make-path,$(1)/$(2))
	"$(4)" $(RUNTIME_CFLAGS) $(5) $(RUNTIME_INCLUDE_FLAGS) -c "$$<" -o "$$@"
endef

$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),default,$(source),$(L2_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),$(RUNTIME_DEFAULT_CONFIG))))
$(foreach source,$(RUNTIME_TRACED_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),traced,$(source),$(L2_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_TRACE_ARC -DDEA_TRACE_MEMORY,$(RUNTIME_TRACED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),unchecked,$(source),$(L2_RUNTIME_CC),-DDEA_RT_UNCHECKED,$(RUNTIME_UNCHECKED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),check_basic,$(source),$(L2_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_RT_CHECK_BASIC,$(RUNTIME_CHECK_BASIC_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),default,$(source),$(L2_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),$(RUNTIME_TCC_DEFAULT_CONFIG))))
$(foreach source,$(RUNTIME_TRACED_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),traced,$(source),$(L2_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_TRACE_ARC -DDEA_TRACE_MEMORY,$(RUNTIME_TCC_TRACED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),unchecked,$(source),$(L2_TCC_OBJ_CC),-DDEA_RT_UNCHECKED,$(RUNTIME_TCC_UNCHECKED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),check_basic,$(source),$(L2_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_RT_CHECK_BASIC,$(RUNTIME_TCC_CHECK_BASIC_CONFIG))))

$(call make-path,$(RUNTIME_DEFAULT_LIB)): $(RUNTIME_DEFAULT_OBJS) | $(call make-path,$(RUNTIME_LIB_DIR))
	$(AR) rcs "$@" $(foreach source,$(RUNTIME_SOURCE_NAMES),"$(RUNTIME_BUILD_DIR)/default/$(source:.c=.o)")

$(call make-path,$(RUNTIME_TRACED_LIB)): $(RUNTIME_TRACED_OBJS) | $(call make-path,$(RUNTIME_LIB_DIR))
	$(AR) rcs "$@" $(foreach source,$(RUNTIME_TRACED_SOURCE_NAMES),"$(RUNTIME_BUILD_DIR)/traced/$(source:.c=.o)")

$(call make-path,$(RUNTIME_UNCHECKED_LIB)): $(RUNTIME_UNCHECKED_OBJS) | $(call make-path,$(RUNTIME_LIB_DIR))
	$(AR) rcs "$@" $(foreach source,$(RUNTIME_SOURCE_NAMES),"$(RUNTIME_BUILD_DIR)/unchecked/$(source:.c=.o)")

$(call make-path,$(RUNTIME_CHECK_BASIC_LIB)): $(RUNTIME_CHECK_BASIC_OBJS) | $(call make-path,$(RUNTIME_LIB_DIR))
	$(AR) rcs "$@" $(foreach source,$(RUNTIME_SOURCE_NAMES),"$(RUNTIME_BUILD_DIR)/check_basic/$(source:.c=.o)")

$(call make-path,$(RUNTIME_INCLUDE_DIR))/dea_rt.h: $(RUNTIME_ROOT)/include/dea_rt.h | $(call make-path,$(RUNTIME_INCLUDE_DIR))
	cp "$<" "$@"

$(call make-path,$(RUNTIME_INCLUDE_DIR))/l1_real.h: $(RUNTIME_ROOT)/include/l1_real.h | $(call make-path,$(RUNTIME_INCLUDE_DIR))
	cp "$<" "$@"

ifeq ($(strip $(L2_TCC_OBJ_CC)),)
runtime-tcc-objects:
ifeq ($(strip $(L2_TCC_OBJ_CC_IS_EXPLICIT)),)
	@printf '%s\n' 'make runtime: no tcc: skipping specialized runtime build'
endif
else
runtime-tcc-objects: $(RUNTIME_TCC_DEFAULT_OBJS) $(RUNTIME_TCC_TRACED_OBJS) $(RUNTIME_TCC_UNCHECKED_OBJS) $(RUNTIME_TCC_CHECK_BASIC_OBJS)
endif

runtime: $(call make-path,$(RUNTIME_DEFAULT_LIB)) $(call make-path,$(RUNTIME_TRACED_LIB)) $(call make-path,$(RUNTIME_UNCHECKED_LIB)) $(call make-path,$(RUNTIME_CHECK_BASIC_LIB)) $(RUNTIME_PUBLIC_HEADERS) runtime-tcc-objects


.PHONY: help venv build use-dev runtime runtime-tcc-objects test test-extended test-ci test-compiler test-compiler-smoke test-compiler-trace test-compiler-trace-smoke test-compiler-trace-all test-compiler-trace-children test-tooling check-examples test-isolation clean clean-runtime clean-all FORCE

help:
	@printf '%s\n' \
		'Dea/L2 canonical compiler workflow' \
		'' \
		'Targets:' \
		'  venv               Delegate to the root `make venv` to create or sync the shared monorepo `../.venv`.' \
		'  runtime            Build the repo-local L2 runtime archives (`libdea_rt.a`, traced, unchecked, and check-basic) and public headers under `$(L2_BUILD_DIR)`.' \
		'  build              Build the L1-implemented canonical compiler, public headers, and verified bundled semantic interfaces.' \
		'  use-dev            Build the canonical compiler and print environment activation instructions.' \
		'  test               Run compiler smoke checks, examples, and tooling.' \
		'  test-ci            Run test-extended with CI-only normal cases, traces and child fixtures.' \
		'  test-extended      Run normal suites without CI-only cases, examples and tooling.' \
		'  test-compiler      Run the complete normal compiler suite; TESTS selects focused cases.' \
		'  test-compiler-smoke' \
		'                     Run array, parser, analysis, expression typing, interface, backend, C emitter, driver, and language identity tests.' \
		'  test-compiler-trace' \
		'                     Run default L2 compiler ARC/memory trace checks; skips intentionally slow trace tests.' \
		'  test-compiler-trace-smoke' \
		'                     Run the focused ARC/memory trace smoke set for developer diagnostics.' \
		'  test-compiler-trace-all' \
		'                     Run L2 compiler ARC/memory trace checks including intentionally slow trace tests.' \
		'  test-compiler-trace-children' \
		'                     Build, run, and analyze L2 child runtime fixtures independently; TESTS selects fixture names.' \
		'  test-tooling       Run L2 tooling and bootstrap regressions.' \
		'  check-examples     Validate all `examples/*.l2` sources with the repo-local canonical compiler; fail on warnings or errors.' \
		'  clean              Remove repo-local build artifacts under `build/*`.' \
		'  clean-runtime      Remove only repo-local runtime build products under `$(L2_BUILD_DIR)`.' \
		'  clean-all          Run both `clean` and `clean-runtime`.' \
		'  test-isolation     Build and run in Docker with sibling checkouts and artifacts inaccessible.' \
		'' \
		'Compiler construction variables:' \
		'  L2_BUILD_DIR=build/dea' \
		'                     Repo-local L2 build root.' \
		'  L2_BOOTSTRAP_L1C=<path>' \
		'                     Required installed L1 compiler; no sibling-checkout or PATH fallback.' \
		'  L1_CC=<compiler>' \
		'                     C compiler used by the installed L1 toolchain to build the `.l1` implementation.' \
		'  L1_CFLAGS=<flags>' \
		'                     C flags for compiler construction and `.l1` implementation tests.' \
		'  L2_COMPILER_RT_CHECK_BASIC=1' \
		'                     Build the native L2 compiler with basic checked-runtime pointer validation by default; set explicitly empty for the full checked runtime.' \
		'  L2_COMPILER_RT_UNCHECKED=1' \
		'                     Build the native L2 compiler with the unchecked runtime; this suppresses the compiler basic-mode default.' \
		'  L2_COMPILER_RT_QUARANTINE_MAX_BYTES=<n>' \
		'                     Bake a quarantine byte limit into the native L2 compiler only; empty preserves the checked runtime default.' \
		'  L2_COMPILER_RT_QUARANTINE_MAX_COUNT=256' \
		'                     Bake a quarantine record limit into the native L2 compiler only; empty preserves the checked runtime default.' \
		'' \
		'Generated L2 program variables:' \
		'  L2_CC=<compiler>' \
		'                     C compiler for `l2c --build/--run`; also defaults `L2_RUNTIME_CC` when set.' \
		'  L2_CFLAGS=<flags>' \
		'                     C flags for generated L2 programs.' \
		'' \
		'Runtime archive variables:' \
		'  L2_RUNTIME_CC=<compiler>' \
		'                     Runtime archive C compiler (defaults to `L2_CC`, then clang/gcc/cc, then `CC`).' \
		'  L2_RT_QUARANTINE_MAX_BYTES=<n>' \
		'                     Bake a quarantine byte limit into the checked runtime archives (default 16 MiB). Deployments can also retune at process start with the `DEA_RT_QUARANTINE_MAX_BYTES` environment variable.' \
		'  L2_RT_QUARANTINE_MAX_COUNT=<n>' \
		'                     Bake a quarantine record limit into the checked runtime archives (default 4096; `0` disables retention; `256` is the suggested setting for performance-sensitive checked deployments). Runtime counterpart: `DEA_RT_QUARANTINE_MAX_COUNT`.' \
		'  L2_TCC_OBJ_CC=<compiler>' \
		'                     TinyCC compiler for repo-local tcc runtime objects (defaults to `tcc`, then `TCC`). When absent without an explicit override, `make runtime` prints a notice and skips the specialized tcc object build.' \
		'' \
		'Test variables:' \
		'  TESTS=""' \
		'                     Optional names for compiler and trace tests; trace smoke uses its fixed selection.' \
		'  L2_TEST_JOBS=<n>' \
		'                     Override normal-test parallelism.' \
		'  L2_TRACE_TEST_JOBS=<n>' \
		'                     Override trace parallelism; otherwise follows the normal job policy.' \
		'  L2_TRACE_ARTIFACT_DIR=<dir>' \
		'                     Optional directory for trace artifacts.' \
		'  L2_ISOLATION_BOOTSTRAP_PREFIX=<path>' \
		'                     Installed Linux/Bookworm-compatible L1 prefix for the Docker isolation gate.' \
		'' \
		'Default local development flow:' \
		'  1. `export L2_BOOTSTRAP_L1C=/absolute/installed-l1/bin/l1c`' \
		'  2. `make use-dev`' \
		'  3. `source build/dea/bin/l2-env.sh`' \
		'  4. `l2c --help`'

venv:
	@$(MAKE) -C .. venv

build: export L2_BUILD_DIR := $(L2_BUILD_DIR)
build: export L2_COMPILER_RT_CHECK_BASIC := $(L2_COMPILER_RT_CHECK_BASIC)
build: export L2_COMPILER_RT_UNCHECKED := $(L2_COMPILER_RT_UNCHECKED)
build: export L2_COMPILER_RT_QUARANTINE_MAX_BYTES := $(L2_COMPILER_RT_QUARANTINE_MAX_BYTES)
build: export L2_COMPILER_RT_QUARANTINE_MAX_COUNT := $(L2_COMPILER_RT_QUARANTINE_MAX_COUNT)
build:
	"$(PYTHON)" scripts/build_l2c.py
	@"$(L2_BUILD_DIR)/bin/l2c" --version

use-dev: build
	@printf '%s\n' 'Activate with: source $(abspath $(L2_BUILD_DIR))/bin/l2-env.sh'

test-compiler test-compiler-smoke test-compiler-trace test-compiler-trace-smoke test-compiler-trace-all test-compiler-trace-children: export L2_BUILD_DIR := $(L2_BUILD_DIR)
test-compiler test-compiler-smoke test-compiler-trace test-compiler-trace-smoke test-compiler-trace-all test-compiler-trace-children: venv build runtime

test-compiler:
	"$(VENV_PYTHON)" compiler/scripts/run_tests.py $(L2_NORMAL_TEST_RUNNER_ARGS) $(TESTS)

test-compiler-smoke:
	"$(VENV_PYTHON)" compiler/scripts/run_tests.py $(L2_NORMAL_TEST_RUNNER_ARGS) $(if $(strip $(TESTS)),$(TESTS),$(L2_TEST_SMOKE_TESTS))

test-compiler-trace:
	"$(VENV_PYTHON)" compiler/scripts/run_trace_tests.py $(TESTS)

test-compiler-trace-smoke:
	"$(VENV_PYTHON)" compiler/scripts/run_trace_tests.py $(TRACE_SMOKE_TESTS)

test-compiler-trace-all:
	"$(VENV_PYTHON)" compiler/scripts/run_trace_tests.py --include-slow $(TESTS)

test-compiler-trace-children:
	"$(VENV_PYTHON)" compiler/scripts/run_trace_tests.py --children $(TESTS)

test-tooling: venv
	"$(VENV_PYTHON)" -m pytest -q -n 0 tests

check-examples: build
	"$(PYTHON)" ../scripts/check_examples.py --compiler "$(L2_BUILD_DIR)/bin/l2c" --examples-dir examples --extension .l2 --label L2

test: test-tooling test-compiler-smoke check-examples

test-extended: test-tooling test-compiler check-examples

test-ci: L2_NORMAL_TEST_RUNNER_ARGS = --include-ci-only
test-ci: test-extended test-compiler-trace
	L2_BUILD_DIR="$(L2_BUILD_DIR)" "$(VENV_PYTHON)" compiler/scripts/run_trace_tests.py --children

test-isolation: export L2_ISOLATION_BOOTSTRAP_PREFIX := $(L2_ISOLATION_BOOTSTRAP_PREFIX)
test-isolation:
	"$(PYTHON)" scripts/test_isolation.py

clean:
	rm -rf ./build/*
	rm -f ./a.out ./a.exe

clean-runtime:
	rm -rf "$(RUNTIME_BUILD_DIR)" "$(RUNTIME_LIB_DIR)"

clean-all: clean clean-runtime
