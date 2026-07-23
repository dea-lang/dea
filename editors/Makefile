PYTHON ?= python3
NPM ?= npm
TREE_SITTER_NPM_CACHE ?= tree-sitter-dea/.cache/npm

.PHONY: install-node-deps package package-tree-sitter package-vscode test test-fallbacks test-textmate test-tree-sitter

install-node-deps:
	$(NPM) --prefix vscode-dea ci
	$(NPM) --prefix tree-sitter-dea ci

test: test-textmate test-tree-sitter test-fallbacks

test-textmate:
	$(NPM) --prefix vscode-dea test

test-tree-sitter:
	$(NPM) --prefix tree-sitter-dea test

test-fallbacks:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

package: package-vscode package-tree-sitter

package-vscode:
	$(NPM) --prefix vscode-dea run package

package-tree-sitter:
	npm_config_cache=$(TREE_SITTER_NPM_CACHE) $(NPM) pack ./tree-sitter-dea --dry-run
