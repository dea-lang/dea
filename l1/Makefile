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
L1_COMPILER_RT_CHECK_BASIC ?= 1
L1_COMPILER_RT_UNCHECKED ?=
L1_COMPILER_RT_QUARANTINE_MAX_BYTES ?=
L1_COMPILER_RT_QUARANTINE_MAX_COUNT ?= 256
TRACE_SMOKE_TESTS := analysis_trace_test array_test io_errno_test lexer_error_cleanup_test slice_trace_test string_vector_test
# Keep the local gate representative and cheap: Stage 1 covers core parsing,
# analysis, typing, interfaces, backend/C emission, and driver behavior; Stage 2
# checks array execution and parsing, with test-stage-parity covering stage identity.
L1_TEST_STAGE1_SMOKE_TESTS := array_test parser_test analysis_test expr_types_test interface_test backend_test c_emitter_test driver_test
L1_TEST_STAGE2_SMOKE_TESTS := array_test parser_test
DOCKER_IMAGE ?= l1-test
DOCKER_CC ?= $(if $(strip $(DOCKER_L0_CC)),$(DOCKER_L0_CC),gcc)
AR ?= ar
L1_RUNTIME_CC ?= $(if $(strip $(L1_CC)),$(L1_CC),$(or $(shell if command -v clang >/dev/null 2>&1; then printf '%s' clang; elif command -v gcc >/dev/null 2>&1; then printf '%s' gcc; elif command -v cc >/dev/null 2>&1; then printf '%s' cc; fi),$(if $(filter-out undefined default,$(origin CC)),$(CC))))
L1_TCC_OBJ_CC ?= $(or $(shell if command -v tcc >/dev/null 2>&1; then printf '%s' tcc; fi),$(if $(filter-out undefined default,$(origin TCC)),$(TCC)))
L1_TCC_OBJ_CC_IS_EXPLICIT := $(if $(filter file,$(origin L1_TCC_OBJ_CC)),,yes)
empty :=
space := $(empty) $(empty)
# Escape paths only in Make targets and prerequisites; recipes use quoted raw paths.
make-path = $(subst $(space),\$(space),$(1))
RUNTIME_ROOT := compiler/shared/runtime
RUNTIME_BUILD_DIR := $(L1_BUILD_DIR)/runtime
RUNTIME_TCC_BUILD_DIR := $(RUNTIME_BUILD_DIR)/tcc
RUNTIME_INCLUDE_DIR := $(L1_BUILD_DIR)/include
RUNTIME_LIB_DIR := $(L1_BUILD_DIR)/lib
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
RUNTIME_TUNING_CFLAGS := $(if $(strip $(L1_RT_QUARANTINE_MAX_BYTES)),-D_RT_QUARANTINE_MAX_BYTES=$(L1_RT_QUARANTINE_MAX_BYTES)) $(if $(strip $(L1_RT_QUARANTINE_MAX_COUNT)),-D_RT_QUARANTINE_MAX_COUNT=$(L1_RT_QUARANTINE_MAX_COUNT))
RUNTIME_INCLUDE_FLAGS := -I$(RUNTIME_ROOT)/include -I$(RUNTIME_ROOT)/internal

.PHONY: help venv runtime clean-runtime clean-all runtime-tcc-objects _ensure-bootstrap-l0-stage2 _print-test-compiler-env build-stage1 use-dev-stage1 test test-ci test-stage1 test-stage1-smoke test-stage2 test-stage2-smoke test-stage1-trace test-stage1-trace-smoke test-stage1-trace-all test-stage1-trace-children test-env test-productization check-examples bench-runtime bench-link-provenance test-extended test-docker print-l1-build-dir clean docker docker-wine docker-wine-toolchain docker-wine-image test-docker-wine-runner FORCE

help:
	@printf '%s\n' \
		'Dea/L1 development workflow' \
		'' \
		'Targets:' \
		'  venv               Delegate to the root `make venv` to create or sync the shared monorepo `../.venv`.' \
		'  runtime            Build the repo-local L1 runtime archives (`libdea_rt.a`, traced, unchecked, and check-basic) and public headers under `$(L1_BUILD_DIR)`.' \
		'  build-stage1       Build the bootstrap Stage 1 compiler, public headers, and verified bundled semantic interfaces.' \
		'  build-stage2       Build the self-hosted Stage 2 compiler through the repo-local Stage 1 compiler.' \
		'  use-dev-stage1     Build and switch the repo-local `l1c` alias to Stage 1.' \
		'  use-dev-stage2     Build and switch the repo-local `l1c` alias to Stage 2.' \
		'  test               Run Stage 1/2 smoke checks, parity, examples, Stage 2 tooling, and Docker/Wine runner regressions.' \
		'  test-ci            Run test-extended with CI-only normal cases, environment/bootstrap, traces, child fixtures, and triple bootstrap.' \
		'  test-extended      Run normal suites without CI-only cases, examples, parity, and tooling checks.' \
		'  test-docker        Run the broad local-normal gate under the repo-owned Linux container (POSIX reference path).' \
		'  test-stage1        Run the L1 Stage 1 `.l0` implementation tests with the built repo-local compiler.' \
		'  test-stage2        Run the L1 Stage 2 `.l1` implementation tests and shared compiler integration tests.' \
		'  test-stage1-smoke  Run array, parser, analysis, expression typing, interface, backend, C emitter, and driver tests.' \
		'  test-stage2-smoke  Run the Stage 2 array and parser smoke tests.' \
		'  test-stage-parity   Compare Stage 1 and Stage 2 observable behavior.' \
		'  triple-test        Strict retained-C/native fixed point and final compiler tests.' \
		'  test-stage1-trace  Run default L1 Stage 1 ARC/memory trace checks; skips intentionally slow trace tests.' \
		'  test-stage1-trace-smoke' \
		'                     Run the focused ARC/memory trace smoke set for developer diagnostics.' \
		'  test-stage1-trace-all' \
		'                     Run L1 Stage 1 ARC/memory trace checks including intentionally slow trace tests.' \
		'  test-stage1-trace-children' \
		'                     Build, run, and analyze L1 child runtime fixtures independently; TESTS selects fixture names.' \
		'  test-stage2-trace  Run default L1 Stage 2 ARC/memory trace checks; skips intentionally slow trace tests.' \
		'  test-stage2-trace-smoke' \
		'                     Run the focused Stage 2 ARC/memory trace smoke set for developer diagnostics.' \
		'  test-stage2-trace-all' \
		'                     Run L1 Stage 2 ARC/memory trace checks including intentionally slow trace tests.' \
		'  test-stage2-trace-children' \
		'                     Build, run, and analyze Stage 2 child runtime fixtures independently; TESTS selects fixture names.' \
		'  test-env           Validate stackable L0/L1 repo-local env script activation.' \
		'  test-productization  Run fixture-based prefix inventory, recovery, and installed launcher regressions.' \
		'  test-productization-build  Self-build Stage 2 with private build-info and verify source/artifact preservation.' \
		'  check-examples     Validate all `examples/*.l1` sources with the repo-local Stage 2 compiler; fail on warnings or errors.' \
		'  bench-runtime      Benchmark the checked runtime allocation tracker across C compilers and quarantine settings (informational; not part of `test-extended`). Variables: `BENCH_CC="tcc clang gcc-16"`, `BENCH_SCALE=<n>`, `BENCH_RUNS=<n>`.' \
		'  bench-link-provenance' \
		'                     Benchmark standalone-link provenance validation across chain and DAG shapes (informational; not part of `test-extended`). Variables: `BENCH_PROVENANCE_SHAPES=<csv>`, `BENCH_PROVENANCE_SIZES=<csv>`, `BENCH_PROVENANCE_WARMUPS=<n>`, `BENCH_PROVENANCE_RUNS=<n>`, `BENCH_PROVENANCE_JSON=<path>`, `BENCH_PROVENANCE_COMPARE=<path>`.' \
		'  clean              Remove repo-local build artifacts under `build/*`.' \
		'  clean-runtime      Remove only repo-local runtime build products under `$(L1_BUILD_DIR)`.' \
		'  clean-all          Run both `clean` and `clean-runtime`.' \
		'' \
		'Docker:' \
		'  docker             Explicitly run a target in the repo-owned Linux Docker container (CMD=<target>).' \
		'  docker-wine        Run CMD=<targets> in experimental Wine/MSYS2; reuse cached images.' \
		'  docker-wine-toolchain  Prepare only the cached Windows toolchain image.' \
		'  docker-wine-image   Prepare the cached toolchain and Windows Python environment.' \
		'  test-docker-wine-runner  Run fast runner regressions without Docker.' \
		'' \
		'Compiler construction variables:' \
		'  L1_BUILD_DIR=build/dea' \
		'                     Repo-local L1 build root.' \
		'  L1_BOOTSTRAP_L0C=<path>' \
		'                     Explicit upstream L0 Stage 2 compiler wrapper or native binary.' \
		'  L0_CC=<compiler>' \
		'                     Upstream L0 C compiler used by `l0c-stage2` when building Stage 1 and running `.l0` implementation tests.' \
		'  L0_CFLAGS=<flags>' \
		'                     Raw C flags used to build the native L1 Stage 1 compiler, which is an L0 program. Explicit runtime mode and quarantine defines take precedence over compiler-build defaults.' \
		'  L1_COMPILER_RT_CHECK_BASIC=1' \
		'                     Build the native L1 compiler with basic checked-runtime pointer validation by default; set explicitly empty for the full checked runtime.' \
		'  L1_COMPILER_RT_UNCHECKED=1' \
		'                     Build the native L1 compiler with the unchecked runtime; this suppresses the compiler basic-mode default.' \
		'  L1_COMPILER_RT_QUARANTINE_MAX_BYTES=<n>' \
		'                     Bake a quarantine byte limit into the native L1 compiler only; empty preserves the checked runtime default.' \
		'  L1_COMPILER_RT_QUARANTINE_MAX_COUNT=256' \
		'                     Bake a quarantine record limit into the native L1 compiler only; empty preserves the checked runtime default.' \
		'' \
		'Generated L1 program variables:' \
		'  L1_CC=<compiler>' \
		'                     C compiler for Stage 2 construction and `l1c --build/--run`; also defaults `L1_RUNTIME_CC` when set.' \
		'  L1_CFLAGS=<flags>' \
		'                     C flags used for generated L1 programs, including Stage 2 construction; Stage 1 uses the upstream construction flags above.' \
		'' \
		'Runtime archive variables:' \
		'  L1_RUNTIME_CC=<compiler>' \
		'                     Runtime archive C compiler (defaults to `L1_CC`, then clang/gcc/cc, then `CC`). Example: `make clean-runtime runtime L1_RUNTIME_CC=gcc-15`.' \
		'  L1_RT_QUARANTINE_MAX_BYTES=<n>' \
		'                     Bake a quarantine byte limit into the checked runtime archives (default 16 MiB). Deployments can also retune at process start with the `DEA_RT_QUARANTINE_MAX_BYTES` environment variable.' \
		'  L1_RT_QUARANTINE_MAX_COUNT=<n>' \
		'                     Bake a quarantine record limit into the checked runtime archives (default 4096; `0` disables retention; `256` is the suggested setting for performance-sensitive checked deployments). Runtime counterpart: `DEA_RT_QUARANTINE_MAX_COUNT`.' \
		'  L1_TCC_OBJ_CC=<compiler>' \
		'                     TinyCC compiler for repo-local tcc runtime objects (defaults to `tcc`, then `TCC`). When absent without an explicit override, `make runtime` prints a notice and skips the specialized tcc object build.' \
		'' \
		'Test variables:' \
		'  TESTS=""' \
		'                     Optional test names for the selected stage and trace targets; forwarded by `make docker` when set.' \
		'  L1_TEST_JOBS=<n>' \
		'                     Optional normal-test parallelism override; forwarded by `make docker` when set.' \
		'  L1_TRACE_TEST_JOBS=<n>' \
		'                     Override parallelism for either stage trace suite; when unset, trace runs follow the normal default job policy.' \
		'  L1_TRACE_ARTIFACT_DIR=<dir>' \
		'                     Optional trace artifact directory. Local trace runs write artifacts there; `make docker` bind-mounts the host directory and preserves artifacts across `docker run --rm`.' \
		'' \
		'Docker variables:' \
		'  DOCKER_WINE_IMAGE_PREFIX=dea-l1-wine' \
		'                     Local namespace for content-addressed Wine toolchain and environment images.' \
		'  DOCKER_IMAGE=l1-test' \
		'                     Docker image tag used by `make docker`.' \
		'  DOCKER_CC=gcc' \
		'                     C compiler passed to all three L1 compiler roles in Linux Docker (`gcc` or `clang`).' \
		'  DOCKER_L0_CC=<compiler>' \
		'                     Legacy compatibility selector used when the canonical Docker compiler selector is unset.' \
		'' \
		'Default local development flow:' \
		'  1. `make use-dev-stage2`  # auto-prepares ../l0 Stage 2 if needed' \
		'  2. `source build/dea/bin/l1-env.sh`' \
		'  3. `l1c --help`'

venv:
	@$(MAKE) -C .. venv

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
	$(call write-runtime-build-config,$(L1_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),default)

$(call make-path,$(RUNTIME_TRACED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/traced
	$(call write-runtime-build-config,$(L1_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),DEA_TRACE_ARC DEA_TRACE_MEMORY)

$(call make-path,$(RUNTIME_UNCHECKED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/unchecked
	$(call write-runtime-build-config,$(L1_RUNTIME_CC),,DEA_RT_UNCHECKED)

$(call make-path,$(RUNTIME_CHECK_BASIC_CONFIG)): FORCE | $(call make-path,$(RUNTIME_BUILD_DIR))/check_basic
	$(call write-runtime-build-config,$(L1_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),DEA_RT_CHECK_BASIC)

$(call make-path,$(RUNTIME_TCC_DEFAULT_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/default
	$(call write-runtime-build-config,$(L1_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),default)

$(call make-path,$(RUNTIME_TCC_TRACED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/traced
	$(call write-runtime-build-config,$(L1_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),DEA_TRACE_ARC DEA_TRACE_MEMORY)

$(call make-path,$(RUNTIME_TCC_UNCHECKED_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/unchecked
	$(call write-runtime-build-config,$(L1_TCC_OBJ_CC),,DEA_RT_UNCHECKED)

$(call make-path,$(RUNTIME_TCC_CHECK_BASIC_CONFIG)): FORCE | $(call make-path,$(RUNTIME_TCC_BUILD_DIR))/check_basic
	$(call write-runtime-build-config,$(L1_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),DEA_RT_CHECK_BASIC)

# Explicit object rules preserve space-bearing roots on supported Make versions.
define runtime-object-rule
$(call make-path,$(1)/$(2)/$(3:.c=.o)): $(RUNTIME_ROOT)/src/$(3) $(RUNTIME_HEADERS) $(call make-path,$(6)) | $(call make-path,$(1)/$(2))
	"$(4)" $(RUNTIME_CFLAGS) $(5) $(RUNTIME_INCLUDE_FLAGS) -c "$$<" -o "$$@"
endef

$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),default,$(source),$(L1_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS),$(RUNTIME_DEFAULT_CONFIG))))
$(foreach source,$(RUNTIME_TRACED_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),traced,$(source),$(L1_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_TRACE_ARC -DDEA_TRACE_MEMORY,$(RUNTIME_TRACED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),unchecked,$(source),$(L1_RUNTIME_CC),-DDEA_RT_UNCHECKED,$(RUNTIME_UNCHECKED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_BUILD_DIR),check_basic,$(source),$(L1_RUNTIME_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_RT_CHECK_BASIC,$(RUNTIME_CHECK_BASIC_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),default,$(source),$(L1_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS),$(RUNTIME_TCC_DEFAULT_CONFIG))))
$(foreach source,$(RUNTIME_TRACED_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),traced,$(source),$(L1_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_TRACE_ARC -DDEA_TRACE_MEMORY,$(RUNTIME_TCC_TRACED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),unchecked,$(source),$(L1_TCC_OBJ_CC),-DDEA_RT_UNCHECKED,$(RUNTIME_TCC_UNCHECKED_CONFIG))))
$(foreach source,$(RUNTIME_SOURCE_NAMES),$(eval $(call runtime-object-rule,$(RUNTIME_TCC_BUILD_DIR),check_basic,$(source),$(L1_TCC_OBJ_CC),$(RUNTIME_TUNING_CFLAGS) -DDEA_RT_CHECK_BASIC,$(RUNTIME_TCC_CHECK_BASIC_CONFIG))))

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

ifeq ($(strip $(L1_TCC_OBJ_CC)),)
runtime-tcc-objects:
ifeq ($(strip $(L1_TCC_OBJ_CC_IS_EXPLICIT)),)
	@printf '%s\n' 'make runtime: no tcc: skipping specialized runtime build'
endif
else
runtime-tcc-objects: $(RUNTIME_TCC_DEFAULT_OBJS) $(RUNTIME_TCC_TRACED_OBJS) $(RUNTIME_TCC_UNCHECKED_OBJS) $(RUNTIME_TCC_CHECK_BASIC_OBJS)
endif

runtime: $(call make-path,$(RUNTIME_DEFAULT_LIB)) $(call make-path,$(RUNTIME_TRACED_LIB)) $(call make-path,$(RUNTIME_UNCHECKED_LIB)) $(call make-path,$(RUNTIME_CHECK_BASIC_LIB)) $(RUNTIME_PUBLIC_HEADERS) runtime-tcc-objects

bench-runtime:
	$(PYTHON) ./scripts/bench_runtime.py $(if $(strip $(BENCH_CC)),--cc "$(BENCH_CC)") $(if $(strip $(BENCH_SCALE)),--scale "$(BENCH_SCALE)") $(if $(strip $(BENCH_RUNS)),--runs "$(BENCH_RUNS)")

bench-link-provenance: _ensure-bootstrap-l0-stage2
	$(PYTHON) ./scripts/bench_link_provenance.py $(if $(strip $(BENCH_PROVENANCE_SHAPES)),--shapes "$(BENCH_PROVENANCE_SHAPES)") $(if $(strip $(BENCH_PROVENANCE_SIZES)),--sizes "$(BENCH_PROVENANCE_SIZES)") $(if $(strip $(BENCH_PROVENANCE_WARMUPS)),--warmups "$(BENCH_PROVENANCE_WARMUPS)") $(if $(strip $(BENCH_PROVENANCE_RUNS)),--runs "$(BENCH_PROVENANCE_RUNS)") $(if $(strip $(BENCH_PROVENANCE_JSON)),--json "$(BENCH_PROVENANCE_JSON)") $(if $(strip $(BENCH_PROVENANCE_COMPARE)),--compare "$(BENCH_PROVENANCE_COMPARE)")

clean-runtime:
	rm -rf "$(RUNTIME_BUILD_DIR)" "$(RUNTIME_LIB_DIR)"

clean-all:
	@$(MAKE) clean
	@$(MAKE) clean-runtime

build-stage1: venv $(RUNTIME_PUBLIC_HEADERS) _ensure-bootstrap-l0-stage2
	L1_BUILD_DIR="$(L1_BUILD_DIR)" \
	L1_COMPILER_RT_CHECK_BASIC="$(L1_COMPILER_RT_CHECK_BASIC)" \
	L1_COMPILER_RT_UNCHECKED="$(L1_COMPILER_RT_UNCHECKED)" \
	L1_COMPILER_RT_QUARANTINE_MAX_BYTES="$(L1_COMPILER_RT_QUARANTINE_MAX_BYTES)" \
	L1_COMPILER_RT_QUARANTINE_MAX_COUNT="$(L1_COMPILER_RT_QUARANTINE_MAX_COUNT)" \
	"$(PYTHON)" ./scripts/build_stage1_l1c.py
	@printf 'Repo-local L1 Stage 1 compiler version:\n'
	@"$(L1_BUILD_DIR)/bin/l1c-stage1" --version

use-dev-stage1: build-stage1

use-dev-stage2: build-stage2

use-dev-stage1 use-dev-stage2:
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(PYTHON)" scripts/select_stage.py $(if $(filter use-dev-stage2,$@),2,1)
	@printf '\n------------------------------------------------------------------------------\n'
ifeq ($(OS),Windows_NT)
	@cmd_env_path="$$(cygpath -w "$$(realpath "$(L1_BUILD_DIR)/bin/l1-env.cmd")")"; \
		printf 'To activate the selected l1c stage in this shell:\n\nIn an MSYS2 bash shell, run:\n\n    source %s/bin/l1-env.sh\n\nIn CMD:\n\n    call "%s"\n\nThen run:\n\n    l1c --help\n\nSee ../l0/README-WINDOWS.md for direct-launcher guidance.' "$$(cygpath -u "$$(realpath "$(L1_BUILD_DIR)")")" "$$cmd_env_path"
else
	@printf 'To activate the selected l1c stage in this shell, run:\n\n    source %s/bin/l1-env.sh\n\nThis adds Dea to your current PATH, so `l1c` invokes the selected compiler.\nSee README.md for more information.' "$(abspath $(L1_BUILD_DIR))"
endif
	@printf '\n------------------------------------------------------------------------------\n'

_print-test-compiler-env:
	@resolve_cc() { \
		env_name="$$1"; shift; \
		env_value="$$(printenv "$$env_name" 2>/dev/null || true)"; \
		if [ -n "$$env_value" ]; then printf '%s' "$$env_value"; return 0; fi; \
		for candidate in "$$@"; do \
			if command -v "$$candidate" >/dev/null 2>&1; then printf '%s' "$$candidate"; return 0; fi; \
		done; \
		if [ -n "$${CC:-}" ]; then printf '%s' "$$CC"; return 0; fi; \
		printf '%s' '<none>'; \
	}; \
	configured_cc() { \
		env_value="$$(printenv "$$1" 2>/dev/null || true)"; \
		if [ -n "$$env_value" ]; then printf '%s' "$$env_value"; else printf '%s' '<auto>'; fi; \
	}; \
	print_cc_role() { \
		role="$$1"; configured="$$2"; effective="$$3"; purpose="$$4"; \
		resolved='<unresolved>'; \
		version='<unavailable>'; \
		if [ -n "$$effective" ] && [ "$$effective" != '<none>' ]; then \
			resolved_path="$$(command -v "$$effective" 2>/dev/null || true)"; \
			if [ -n "$$resolved_path" ]; then \
				resolved="$$resolved_path"; \
				if version_output="$$("$$resolved" --version 2>&1)" && [ -n "$$version_output" ]; then \
					:; \
				elif version_output="$$("$$resolved" -v 2>&1)" && [ -n "$$version_output" ]; then \
					:; \
				else \
					version_output=''; \
				fi; \
				version="$$(printf '%s\n' "$$version_output" | sed -n '1p')"; \
				if [ -z "$$version" ]; then version='<unavailable>'; fi; \
			fi; \
		fi; \
		if [ -z "$$effective" ]; then effective='<none>'; fi; \
		printf '  %s: configured=%s; effective=%s; resolved=%s; version=%s\n' \
			"$$role" "$$configured" "$$effective" "$$resolved" "$$version"; \
		printf '    %s\n' "$$purpose"; \
	}; \
	l0_cc="$$(resolve_cc L0_CC tcc gcc clang cc)"; \
	l1_cc="$$(resolve_cc L1_CC tcc gcc clang cc)"; \
	printf '%s\n' 'L1 test compiler environment:'; \
	print_cc_role L0_CC "$$(configured_cc L0_CC)" "$$l0_cc" \
		'L0 compiler used by the upstream l0c-stage2 for .l0 test harnesses'; \
	print_cc_role L1_CC "$$(configured_cc L1_CC)" "$$l1_cc" \
		'C compiler for Stage 2 construction, .l1 implementation tests, and L1 fixture snippets'; \
	print_cc_role L1_RUNTIME_CC "$$(configured_cc L1_RUNTIME_CC)" "$(L1_RUNTIME_CC)" \
		'C compiler used for repo-local L1 runtime archives'

test-stage1: venv build-stage1 runtime _print-test-compiler-env
	@printf '%s\n' 'L1 Stage 1 complete normal suite:'
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_tests.py $(L1_NORMAL_TEST_RUNNER_ARGS) $(TESTS)

test-stage1-smoke: venv build-stage1 runtime _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_tests.py $(L1_NORMAL_TEST_RUNNER_ARGS) $(if $(strip $(TESTS)),$(TESTS),$(L1_TEST_STAGE1_SMOKE_TESTS))

test-stage1-trace: venv build-stage1 runtime _print-test-compiler-env
	@printf '%s\n' 'L1 Stage 1 dedicated trace sweep:'
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py $(TESTS)

test-stage1-trace-smoke: venv build-stage1 runtime _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py $(TRACE_SMOKE_TESTS)

test-stage1-trace-all: venv build-stage1 runtime _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py --include-slow $(TESTS)

test-stage1-trace-children: venv build-stage1 runtime _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py --children $(TESTS)

test-env: venv
	@printf '%s\n' 'L1 environment/bootstrap integration:'
	"$(VENV_PYTHON)" ./tests/test_env_stackability.py

build-stage2: build-stage1 runtime
	L1_BUILD_DIR="$(L1_BUILD_DIR)" \
	L1_COMPILER_RT_CHECK_BASIC="$(L1_COMPILER_RT_CHECK_BASIC)" \
	L1_COMPILER_RT_UNCHECKED="$(L1_COMPILER_RT_UNCHECKED)" \
	L1_COMPILER_RT_QUARANTINE_MAX_BYTES="$(L1_COMPILER_RT_QUARANTINE_MAX_BYTES)" \
	L1_COMPILER_RT_QUARANTINE_MAX_COUNT="$(L1_COMPILER_RT_QUARANTINE_MAX_COUNT)" \
	"$(PYTHON)" scripts/build_stage2_l1c.py
	@"$(L1_BUILD_DIR)/bin/l1c-stage2" --version

test-stage2: venv build-stage2 _print-test-compiler-env
	@printf '%s\n' 'L1 Stage 2 complete normal suite:'
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_tests.py $(L1_NORMAL_TEST_RUNNER_ARGS) $(TESTS)

test-stage2-smoke: venv build-stage2 _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_tests.py $(L1_NORMAL_TEST_RUNNER_ARGS) $(if $(strip $(TESTS)),$(TESTS),$(L1_TEST_STAGE2_SMOKE_TESTS))

test-stage2-trace: venv build-stage2 _print-test-compiler-env
	@printf '%s\n' 'L1 Stage 2 dedicated trace sweep:'
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_trace_tests.py $(TESTS)

test-stage2-trace-smoke: venv build-stage2 _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_trace_tests.py $(TRACE_SMOKE_TESTS)

test-stage2-trace-all: venv build-stage2 _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_trace_tests.py --include-slow $(TESTS)

test-stage2-trace-children: venv build-stage2 _print-test-compiler-env
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_trace_tests.py --children $(TESTS)

test-stage-parity: build-stage2
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/tests/stage_parity_test.py

test-stage2-tooling: venv
	"$(VENV_PYTHON)" -m pytest -q -n 0 tests/test_stage2_tooling.py tests/test_bootstrap_identity.py

test-productization: venv
	"$(VENV_PYTHON)" -m pytest -q -n 0 tests/test_bootstrap_productization.py

test-productization-build: build-stage2
	L1_BUILD_DIR="$(L1_BUILD_DIR)" L1_PRODUCTIZATION_SEED="$(L1_BUILD_DIR)/bin/l1c-stage2" \
	"$(VENV_PYTHON)" -m pytest -q -n 0 tests/test_stage2_build_overlay.py

triple-test: build-stage1 runtime
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" scripts/triple_bootstrap.py

check-examples: build-stage2
	"$(PYTHON)" ../scripts/check_examples.py --compiler "$(L1_BUILD_DIR)/bin/l1c-stage2" --examples-dir examples --extension .l1 --label "L1 Stage 2"

test: test-stage1-smoke test-stage2-smoke test-stage-parity check-examples test-docker-wine-runner test-stage2-tooling test-productization

test-extended: test-stage1 test-stage2 test-stage-parity check-examples test-docker-wine-runner test-stage2-tooling test-productization

# Hosted CI is the exhaustive union: full local-normal suites with CI-only cases, environment/bootstrap integration,
# dedicated Stage 1/2 trace sweeps, child trace fixtures, and triple bootstrap. The normal runners list their
# included CI-only cases; trace checks are separate execution modes and are intentionally retained.
test-ci: L1_NORMAL_TEST_RUNNER_ARGS = --include-ci-only
test-ci: test-extended test-env test-stage1-trace test-stage2-trace
	@printf '%s\n' 'L1 child trace fixtures (Stage 1 and Stage 2):'
	# Parent TESTS selectors do not filter the independently declared child fixtures.
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" ./compiler/stage1_l0/scripts/run_trace_tests.py --children
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" compiler/stage2_l1/scripts/run_trace_tests.py --children
	@printf '%s\n' 'L1 strict triple bootstrap:'
	L1_BUILD_DIR="$(L1_BUILD_DIR)" "$(VENV_PYTHON)" scripts/triple_bootstrap.py

test-docker:
	$(MAKE) docker CMD=test-extended

print-l1-build-dir:
	@printf '%s\n' "$(L1_BUILD_DIR)"

clean:
	rm -rf ./build/*
	rm -f ./a.out ./a.exe
	rm -f ./compiler/stage1_l0/a.out ./compiler/stage1_l0/a.exe
	rm -f ./compiler/stage1_l0/tests/.tmp*
	rm -f ./compiler/stage2_l1/tests/.tmp*

docker:
	@if [ -z "$(CMD)" ]; then \
		echo "Usage: make docker CMD=<target>"; \
		echo "Example: make docker CMD=test-extended"; \
		exit 2; \
	else \
		$(if $(strip $(L1_TRACE_ARTIFACT_DIR)),mkdir -p "$(L1_TRACE_ARTIFACT_DIR)" &&) \
		docker build -f Dockerfile -t "$(DOCKER_IMAGE)" .. && docker run --rm \
			-e "L0_CC=$(DOCKER_CC)" \
			-e "L1_CC=$(DOCKER_CC)" \
			-e "L1_RUNTIME_CC=$(DOCKER_CC)" \
			$(if $(strip $(L1_TEST_JOBS)),-e "L1_TEST_JOBS=$(L1_TEST_JOBS)") \
			$(if $(strip $(L1_TRACE_TEST_JOBS)),-e "L1_TRACE_TEST_JOBS=$(L1_TRACE_TEST_JOBS)") \
			$(if $(strip $(TESTS)),-e "TESTS=$(TESTS)") \
			$(if $(strip $(L1_TRACE_ARTIFACT_DIR)),-v "$(abspath $(L1_TRACE_ARTIFACT_DIR)):/trace-artifacts" -e "L1_TRACE_ARTIFACT_DIR=/trace-artifacts") \
			"$(DOCKER_IMAGE)" make $(CMD); \
	fi

# Export values rather than interpolating CMD into another shell command.
docker-wine docker-wine-toolchain docker-wine-image: export CMD := $(CMD)
docker-wine docker-wine-toolchain docker-wine-image: export DOCKER_WINE_IMAGE_PREFIX := $(DOCKER_WINE_IMAGE_PREFIX)
docker-wine: export TESTS := $(TESTS)
docker-wine: export L1_TEST_JOBS := $(L1_TEST_JOBS)
docker-wine: export L1_TRACE_TEST_JOBS := $(L1_TRACE_TEST_JOBS)
docker-wine: export L1_TRACE_ARTIFACT_DIR := $(L1_TRACE_ARTIFACT_DIR)

docker-wine:
	$(HOST_PYTHON) scripts/docker_wine.py run

docker-wine-toolchain:
	$(HOST_PYTHON) scripts/docker_wine.py toolchain

docker-wine-image:
	$(HOST_PYTHON) scripts/docker_wine.py image

test-docker-wine-runner:
	$(HOST_PYTHON) tests/test_docker_wine.py

.PHONY: build-stage2 use-dev-stage2 test-stage2 test-stage2-trace test-stage2-trace-smoke test-stage2-trace-all test-stage2-trace-children test-stage-parity test-stage2-tooling test-productization-build triple-test
