.DEFAULT_GOAL := help

DEA_LEVEL_DIRS ?= l0 l1
ROOT_CLEAN_PATHS := build .pytest_cache __pycache__ pytest-of-*

.PHONY: help venv clean clean-all test-all _check-level-dirs _clean-root-paths

help:
	@printf '%s\n' \
		'Dea monorepo maintenance workflow' \
		'' \
		'Targets:' \
		'  help               Show this help text.' \
		'  venv               Create or sync the shared monorepo `.venv` by delegating to each registered level.' \
		'  test-all           Run `make test-all` in each registered level.' \
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

venv: _check-level-dirs
	@for level in $(DEA_LEVEL_DIRS); do \
		printf '==> %s: make venv\n' "$$level"; \
		$(MAKE) -C "$$level" venv || exit $$?; \
	done

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

test-all: _check-level-dirs
	@for level in $(DEA_LEVEL_DIRS); do \
		printf '==> %s: make test-all\n' "$$level"; \
		$(MAKE) -C "$$level" test-all || exit $$?; \
	done
