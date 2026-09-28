# Stage 2 native-source review ledger

- Review date: 2026-09-28
- Status: Phase 1 complete; Phases 2 through 5 pending
- Source inventory: 120 original committed production modules; 119 current after removing unused `util.path`
- Phase assignment: 1 = shared utilities/models; 2 = frontend/analysis; 3 = backend/build; 4 = remaining CLI/entrypoints
- Parent plan: [l1/work/plans/refactors/2026-09-28-stage2-native-source-review-noref.md][plan]

## Method and scope

Every Phase 1 function body and its data representation is reviewed with relevant callers, callees, failure paths,
ownership and cleanup. The function lists below make coverage explicit; boundary notes identify the important
cross-module contracts. Reading a later-phase caller does not complete that module's own review. Review findings are
recorded before edits; final dispositions require validation of the source-changing tranche.

Subsystem-specific state and models stay with their owning later phases. No Stage 1 production changes, diagnostic code
assignments, public language/CLI/ABI changes, or interface format/fingerprint rule changes are intended.

## Toolchain and baseline

- Host: macOS x86_64; Apple Clang 17.0.0 (clang-1700.6.4.2).
- Explicit compiler: `/usr/bin/clang` for `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`.
- L0 bootstrap: repo-local `l0/build/dea/bin/l0c-stage2`, development build from 2026-09-28 17:14:12 UTC on Darwin
  24.6.0 x86_64, built with the selected Apple Clang. The binary is preserved as `l0c-stage2-baseline.native`.
- Configuration probe: `/usr/bin/clang --no-default-config --version` passed.
- Bootstrap: root `make venv`; from `l0/`, `make use-dev-stage2` with the three explicit compiler variables.
- Dependency setup required network access for locked Python packages; no dependency declarations were changed.
- Baseline command from `l1/`: `make test-all test-stage-parity triple-test` with `KEEP_ARTIFACTS=1` and the three
  explicit compiler variables.
- Compiler/runtime flags retain repository defaults: generated compiler C uses
  `-O1 -std=c99 -Wall -Wextra -Wno-unused -Wno-unused-parameter -pedantic-errors`, basic checks are enabled, and
  `_RT_QUARANTINE_MAX_COUNT=256`. Stage 1 selects `L0_RT_CHECK_BASIC`; Stage 2 selects `--check-basic`. No explicit
  `L0_CFLAGS`/`L1_CFLAGS` override is supplied. Runtime construction uses `-O2 -std=c99`.
- Evidence root: `/tmp/dea-phase1-review/`; baseline validation complete before compiler source edits.
- The first aggregate stopped after 83 Stage 1 passes and one environment failure: the sandbox denied
  `/usr/sbin/sysctl -n kern.osversion` in `preparation_identity_test.py`. An isolated sandbox rerun reproduced that
  restriction; the unrestricted rerun passed native identity, runtime policy, compiler adapters, and memo invalidation.
  Retained logs: `baseline.log`, `preparation-identity-recheck.log`, and `preparation-identity-unrestricted.log`.
- The remaining aggregate prerequisites, both stages' child traces, parity, and triple bootstrap run with the same
  compiler settings outside that sandbox restriction. `baseline-remaining.log` retains their output; unchanged Stage 1
  passing cases are reused.
- Stage 2 normal baseline: 68 passed, zero failed. Environment stacking passed; all four examples passed without
  warnings/errors; Docker/Wine runner tests passed (6), and Stage 2/bootstrap tooling tests passed (14). Stage 1 default
  traces passed (46), with zero leaked object or string pointers. Stage 2 default traces also passed (46); both stages'
  two child fixtures passed with zero leaked pointers. Explicit `make test-stage-parity` passed. Triple bootstrap
  passed.
- Trace evidence: `baseline-traces/` and its Stage 2 subdirectory retain per-case reports and output. Completed large
  logs are retained as gzip files after decompression/digest verification; `trace-compression*.log` records this
  lossless retention. Active logs are not compressed.
- Setup logs: `setup-network.log` and `l0-bootstrap.log`. Saved native binaries: `l1c-stage1-baseline.native` and
  `l1c-stage2-baseline.native`, with sizes/digests in `baseline-binaries.json`; original source snapshot:
  `baseline-src/`.
- Triple-bootstrap controls add `-frandom-seed=l1c-stage2 -Wl,-no_uuid -Wl,-no_adhoc_codesign` and a private shared
  preparation cache across generations. Baseline artifacts are retained at `l1/build/dea/triple-bootstrap-pbsx397z/`,
  including `native-controls.json`, `inputs.json`, and `steps.jsonl`.
- Actual managed stdlib/runtime preparation with `/usr/bin/clang` succeeded for `x86_64-apple-darwin24.6.0`; support is
  established by this run, not just the version probe.

The baseline triple-bootstrap B/C comparison passed for 137 retained C translation units and identical normalized native
artifacts (3,212,496 bytes each). Its final self-built suite passed all 68 tests, all four examples, and the hello smoke
run.

The remaining baseline invocation, from `l1/`, is:

```sh
L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang \
  UV_CACHE_DIR=/tmp/dea-phase1-review/uv-cache KEEP_ARTIFACTS=1 \
  L1_TRACE_ARTIFACT_DIR=/tmp/dea-phase1-review/baseline-traces \
  make test-stage2 test-env check-examples test-docker-wine-runner test-stage2-tooling \
    test-stage1-trace test-stage2-trace test-stage1-trace-children test-stage2-trace-children \
    test-stage-parity triple-test
```

## Module inventory

Paths are relative to `l1/compiler/stage2_l1/src/`. Every original committed module has exactly one row. Removed modules
retain their original row and an explicit removal note; new modules must receive new rows. There are no renames or
splits.

| Module path                        | Phase | Disposition         |
| ---------------------------------- | ----- | ------------------- |
| `analysis.l1`                      | 2     | Pending             |
| `ast.l1`                           | 1     | Reviewed, changed   |
| `ast_printer.l1`                   | 2     | Pending             |
| `backend.l1`                       | 3     | Pending             |
| `backend/coerce.l1`                | 3     | Pending             |
| `backend/expr.l1`                  | 3     | Pending             |
| `backend/lifetime.l1`              | 3     | Pending             |
| `backend/lower.l1`                 | 3     | Pending             |
| `backend/output.l1`                | 3     | Pending             |
| `backend/state.l1`                 | 3     | Pending             |
| `backend/stmt.l1`                  | 3     | Pending             |
| `backend/types.l1`                 | 3     | Pending             |
| `build_driver.l1`                  | 3     | Pending             |
| `build_info.l1`                    | 4     | Pending             |
| `builtin_types.l1`                 | 1     | Reviewed, unchanged |
| `c_emitter/abi.l1`                 | 3     | Pending             |
| `c_emitter/declarations.l1`        | 3     | Pending             |
| `c_emitter/expr.l1`                | 3     | Pending             |
| `c_emitter/lifetime.l1`            | 3     | Pending             |
| `c_emitter/state.l1`               | 3     | Pending             |
| `c_emitter/stmt.l1`                | 3     | Pending             |
| `c_emitter/type_names.l1`          | 3     | Pending             |
| `c_emitter/types.l1`               | 3     | Pending             |
| `c_emitter/wrappers.l1`            | 3     | Pending             |
| `cli_args.l1`                      | 4     | Pending             |
| `cli_args/help.l1`                 | 4     | Pending             |
| `cli_args/link.l1`                 | 4     | Pending             |
| `cli_args/model.l1`                | 4     | Pending             |
| `cli_args/parse.l1`                | 4     | Pending             |
| `codegen_options.l1`               | 3     | Pending             |
| `compile_driver.l1`                | 3     | Pending             |
| `compile_driver/compile.l1`        | 3     | Pending             |
| `compile_driver/toolchain.l1`      | 3     | Pending             |
| `compile_driver/transaction.l1`    | 3     | Pending             |
| `compiler_filesystem.l1`           | 1     | Reviewed, changed   |
| `dea_prelude.l1`                   | 2     | Pending             |
| `diag_print.l1`                    | 1     | Reviewed, unchanged |
| `driver.l1`                        | 2     | Pending             |
| `driver/resolve.l1`                | 2     | Pending             |
| `driver/state.l1`                  | 2     | Pending             |
| `expr_types.l1`                    | 2     | Pending             |
| `expr_types/convert.l1`            | 2     | Pending             |
| `expr_types/expr.l1`               | 2     | Pending             |
| `expr_types/liveness.l1`           | 2     | Pending             |
| `expr_types/lookup.l1`             | 2     | Pending             |
| `expr_types/patterns.l1`           | 2     | Pending             |
| `expr_types/state.l1`              | 2     | Pending             |
| `expr_types/stmt.l1`               | 2     | Pending             |
| `interface_emitter.l1`             | 2     | Pending             |
| `interface_fingerprint.l1`         | 2     | Pending             |
| `interface_literal.l1`             | 2     | Pending             |
| `interface_order.l1`               | 2     | Pending             |
| `interface_projection.l1`          | 2     | Pending             |
| `l1c.l1`                           | 4     | Pending             |
| `l1c_lib.l1`                       | 4     | Pending             |
| `lexer.l1`                         | 2     | Pending             |
| `link_driver.l1`                   | 3     | Pending             |
| `link_driver/build.l1`             | 3     | Pending             |
| `link_driver/inputs.l1`            | 3     | Pending             |
| `link_driver/model.l1`             | 3     | Pending             |
| `link_driver/plan.l1`              | 3     | Pending             |
| `link_driver/provenance.l1`        | 3     | Pending             |
| `link_driver/toolchain.l1`         | 3     | Pending             |
| `link_driver/transaction.l1`       | 3     | Pending             |
| `link_driver/workspace.l1`         | 3     | Pending             |
| `locals.l1`                        | 2     | Pending             |
| `mi_utils.l1`                      | 2     | Pending             |
| `module_graph.l1`                  | 3     | Pending             |
| `module_graph/order.l1`            | 3     | Pending             |
| `module_interface.l1`              | 2     | Pending             |
| `module_lifecycle.l1`              | 3     | Pending             |
| `name_resolver.l1`                 | 2     | Pending             |
| `name_resolver/collect.l1`         | 2     | Pending             |
| `name_resolver/imports.l1`         | 2     | Pending             |
| `name_resolver/interface.l1`       | 2     | Pending             |
| `name_resolver/query.l1`           | 2     | Pending             |
| `name_resolver/state.l1`           | 2     | Pending             |
| `parser.l1`                        | 2     | Pending             |
| `parser/cursor.l1`                 | 2     | Pending             |
| `parser/decl.l1`                   | 2     | Pending             |
| `parser/expr.l1`                   | 2     | Pending             |
| `parser/interface.l1`              | 2     | Pending             |
| `parser/interface/declarations.l1` | 2     | Pending             |
| `parser/interface/header.l1`       | 2     | Pending             |
| `parser/interface/normalize.l1`    | 2     | Pending             |
| `parser/interface/types.l1`        | 2     | Pending             |
| `parser/state.l1`                  | 2     | Pending             |
| `parser/stmt.l1`                   | 2     | Pending             |
| `parser/token_value.l1`            | 2     | Pending             |
| `parser/type_ref.l1`               | 2     | Pending             |
| `preparation.l1`                   | 3     | Pending             |
| `preparation/consumer.l1`          | 3     | Pending             |
| `preparation/frontend.l1`          | 3     | Pending             |
| `scope_context.l1`                 | 2     | Pending             |
| `sem_context.l1`                   | 2     | Pending             |
| `signatures.l1`                    | 2     | Pending             |
| `signatures/const_init.l1`         | 2     | Pending             |
| `signatures/cycles.l1`             | 2     | Pending             |
| `signatures/declarations.l1`       | 2     | Pending             |
| `signatures/interface.l1`          | 2     | Pending             |
| `signatures/tables.l1`             | 2     | Pending             |
| `signatures/visibility.l1`         | 2     | Pending             |
| `source_paths.l1`                  | 1     | Reviewed, unchanged |
| `string_escape.l1`                 | 1     | Reviewed, unchanged |
| `symbols.l1`                       | 1     | Reviewed, unchanged |
| `tokens.l1`                        | 1     | Reviewed, unchanged |
| `type_resolve/const_eval.l1`       | 2     | Pending             |
| `type_resolve/const_value.l1`      | 2     | Pending             |
| `type_resolve/lookup.l1`           | 2     | Pending             |
| `type_resolve/materialize.l1`      | 2     | Pending             |
| `type_resolve/ref.l1`              | 2     | Pending             |
| `types.l1`                         | 1     | Reviewed, unchanged |
| `util/demangler.l1`                | 1     | Reviewed, unchanged |
| `util/diag.l1`                     | 1     | Reviewed, unchanged |
| `util/intset.l1`                   | 1     | Reviewed, changed   |
| `util/log.l1`                      | 1     | Reviewed, unchanged |
| `util/numbers.l1`                  | 1     | Reviewed, changed   |
| `util/path.l1`                     | 1     | Reviewed, changed   |
| `util/strings.l1`                  | 1     | Reviewed, unchanged |
| `wrapper_emitter.l1`               | 3     | Pending             |

## Phase 1 function review

### `ast`

- Finding: Named fields for expression and statement defaults; retain arenas and typed ID wrappers.

- Boundary and ownership review: All constructors, accessors, variadic-suffix inspection, and destructors were read.
  Parser constructors transfer pointer-owned metadata into arenas; node-to-node IDs are borrowed references, so arena
  teardown frees each node once rather than recursively following IDs. `parser::parse_result_free` and
  `driver.state::dr_unit_free` own the final teardown. `std.vector` growth may move slots but not separately allocated
  nodes. Retain signed `int` IDs and -1 sentinels, optional teardown helpers, and growable pointer/ID storage. Named
  fields retain constructor argument order and values. A Stage 1 `--gen` check confirms both changed constructor C
  function bodies are byte-identical to their baseline counterparts; evidence is in `ast-candidate.c` and
  `ast-codegen-result.txt` under the evidence root.

- Function coverage (52): `invalid_expr_id`, `invalid_stmt_id`, `invalid_pattern_id`, `ptr_vec_create`, `ptr_vec_push`,
  `ptr_vec_get`, `id_vec_create`, `id_vec_push`, `id_vec_get`, `span_here`, `pattern_node_create`,
  `pattern_arena_create`, `pattern_arena_add`, `pattern_arena_get`, `sv_free_opt`, `pattern_node_free`,
  `pattern_arena_free`, `expr_node_create`, `type_ref_is_variadic`, `expr_arena_create`, `expr_arena_add`,
  `expr_arena_get`, `stmt_node_create`, `stmt_arena_create`, `stmt_arena_add`, `stmt_arena_get`, `type_ref_free`,
  `param_free`, `field_decl_free`, `enum_variant_free`, `func_decl_free`, `struct_decl_free`, `enum_decl_free`,
  `type_alias_decl_free`, `let_decl_free`, `top_level_decl_free`, `export_manifest_free`, `import_free`, `module_free`,
  `id_vec_free`, `import_vec_free`, `top_level_decl_vec_free`, `param_vec_free`, `field_decl_vec_free`,
  `enum_variant_vec_free`, `match_arm_vec_free`, `case_arm_vec_free`, `with_item_vec_free`, `expr_node_free`,
  `stmt_node_free`, `expr_arena_free`, `stmt_arena_free`.

- Validation references: `parser_test`, `type_resolve_test`, `expr_types_test`, and self-hosting construction;
  normal/trace and aggregate results are recorded under
  [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `builtin_types`

- Finding: Retain the allocation-free builtin-name predicate.

- Boundary and ownership review: The one predicate is shared by token reservation and `types` construction. Its 13 names
  match current builtin domains. A table would introduce iteration/storage without removing a representation problem; no
  numeric widening or dispatch abstraction is justified.

- Function coverage (1): `builtin_type_name_is_known`.

- Validation references: `builtin_types_test`, `lexer_test`, and `type_resolve_test`; normal/trace and aggregate results
  are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `compiler_filesystem`

- Finding: Use typed compile-time path-kind constants; retain native transport.

- Boundary and ownership review: Reviewed every native declaration and wrapper, length negotiation, bounded
  trusted-parent retry, temporary-parent precedence, reservation, registration, cleanup, and process invocation.
  Compiler support uses int32 lengths/statuses and actual-host path semantics. `cfs_join_child` must preserve POSIX
  literal-backslash behavior; `std.path::join` is not an equivalent replacement. Workspace cleanup only visits
  registered children and reverses directory order, preserving failures and program exit status. `cfs_run_process` keeps
  `words` alive while passing borrowed byte pointers and separate lengths to the synchronous support ABI. No-follow
  classification, exclusive creation, rename-absent, and process status remain compiler-private contracts. The five
  scalar markers are never assigned after declaration.

- Function coverage (27): `cfs_error`, `cfs_path_kind`, `cfs_path_kind_follow`, `cfs_same_file`, `cfs_mkdir`,
  `cfs_rename_absent`, `cfs_remove_regular_file`, `cfs_remove_empty_dir`, `cfs_host_is_darwin`, `cfs_join_child`,
  `cfs_resolve_trusted_temp_parent`, `cfs_absolute_path`, `cfs_canonical_existing_path`, `cfs_resolve_executable`,
  `cfs_temp_env_value`, `cfs_temp_candidate_kind`, `cfs_select_temp_parent_from_values`, `cfs_select_temp_parent`,
  `cfs_workspace_free`, `cfs_workspace_child`, `cfs_workspace_register_file`, `cfs_workspace_register_directory`,
  `cfs_workspace_create_for_identity`, `cfs_workspace_create`, `cfs_workspace_cleanup`, `cfs_apply_cleanup_status`,
  `cfs_run_process`.

- Validation references: `compiler_filesystem_test`, shared filesystem-support integration tests, and build/driver
  integration; normal/trace and aggregate results are recorded under
  [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `diag_print`

- Finding: Retain byte-exact rendering and aligned source caches.

- Boundary and ownership review: Reviewed severity/header/snippet rendering, loading, caching, and collector
  entrypoints. Tabs map to one logical column; absent coordinates and unreadable/empty sources preserve their existing
  fallback. Caller-provided filename/text vectors remain aligned and own ARC values. Returned snippets and cached
  strings remain managed values after temporary builders are freed. Output bytes, gutter widths, diagnostic order, and
  cache lifetime must remain stable.

- Function coverage (11): `dp_severity_name`, `dp_format_header`, `dp_print_header`, `dp_normalize_line_for_display`,
  `dp_format_snippet`, `dp_render_snippet`, `dp_print_snippet`, `dp_source_cached`, `dp_print_diag`,
  `dp_print_collector_with_sources`, `dp_print_collector`.

- Validation references: `diag_print_test` and frontend diagnostic parity; normal/trace and aggregate results are
  recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `source_paths`

- Finding: Retain ordered resolution and distinct source/interface presence rules.

- Boundary and ownership review: Reviewed construction, root access, formatting, module-name validation, path
  derivation, resolution, environment defaults, managed eligibility, and entry normalization. Source lookup selects
  first `std.fs::exists` match; interface lookup uses no-follow classification so dangling or inaccessible selected
  providers cannot fall through. `driver.resolve` and `link_driver.inputs` perform subsequent read/UTF-8/interface
  validation. System roots precede project roots; managed eligibility observes root identity and shadows. String vectors
  are owned, ordered, and growable; environment splitting and path wrappers preserve current behavior.

- Function coverage (25): `sp_create`, `sp_free`, `sp_add_system_root`, `sp_add_project_root`, `sp_system_root_count`,
  `sp_project_root_count`, `sp_system_root_get`, `sp_project_root_get`, `sp_format_root_list`,
  `_sp_module_relstem_unchecked`, `_sp_resolve_roots`, `sp_resolve`, `sp_is_valid_ident_component`,
  `sp_is_valid_module_name`, `sp_module_relstem`, `sp_module_source_relpath`, `sp_module_interface_relpath`,
  `sp_resolve_interface`, `sp_managed_eligible`, `sp_apply_default_project_roots`, `sp_append_env_sys_roots`,
  `sp_apply_default_sys_roots_env`, `sp_apply_default_sys_roots`, `sp_build_from_roots`, `sp_normalize_entry_target`.

- Validation references: `source_paths_test` and shared driver/interface-resolution integration; normal/trace and
  aggregate results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate
  validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `string_escape`

- Finding: Retain fixed-width octal escaping and trigraph prevention.

- Boundary and ownership review: Reviewed all five helpers and their callers in C emission and interface literal
  formatting. The digit helper receives only 0..7 from a byte split. Three octal digits avoid consuming a following
  source digit; trigraph suffix checks preserve portable C text. Character builders own their buffers and return managed
  strings. Generic string escaping would not preserve these C and interface byte contracts.

- Function coverage (5): `se_append_octal_digit`, `se_append_octal_escape`, `se_is_direct_c_byte`,
  `se_is_trigraph_suffix`, `se_encode_c_string_bytes`.

- Validation references: `util_text_test`, interface emission, and C-emission integration; normal/trace and aggregate
  results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation
  passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `symbols`

- Finding: Retain borrowed declarations and owned cloned resolved types.

- Boundary and ownership review: Reviewed creation, replacement, kind rendering, and destruction.
  `name_resolver.interface`, signature declaration/constant initialization, `dea_prelude`, and type-alias resolution
  supply independent type values to `symbol_set_type_clone`; the cached alias path clones before replacement. `decl_ptr`
  borrows AST or synthesized metadata and must not be freed by `symbol_free`. String fields follow generated ARC;
  resolved types require explicit recursive ownership cleanup.

- Function coverage (4): `symbol_create`, `symbol_set_type_clone`, `symbol_kind_name`, `symbol_free`.

- Validation references: `type_resolve_test`, `expr_types_test`, and semantic-analysis integration; normal/trace and
  aggregate results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate
  validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `tokens`

- Finding: Retain token/recovery variants and raw-vector payload cleanup.

- Boundary and ownership review: Reviewed all token rendering, keyword conversion/reservation, expression-ending
  recovery, vector operations, and release helpers. Lexer queued-token extraction copies a token then replaces its
  source slot with EOF; parser-owned token entrypoints release the vector after transferring parsed data. Raw vector
  storage does not recursively destroy ARC-bearing enum payloads, so both token and recovery payload release switches
  remain necessary. Recovered tokens preserve physical positions and predecessor rules. Fixed arrays or slices cannot
  replace this growable owning stream.

- Function coverage (16): `token_to_string`, `token_recovery_to_string`, `token_recovery_is_some`, `token_recovered`,
  `token_logical_predecessor_ends_expression`, `is_reserved_ident_word`, `is_reserved_keyword`, `ident_to_token`,
  `is_expr_ending_token_type`, `tv_create`, `tv_push`, `tv_get`, `tv_len`, `token_release_payload`,
  `token_recovery_release_payload`, `tv_free`.

- Validation references: `lexer_test`, `lexer_error_cleanup_test`, and `parser_test`; normal/trace and aggregate results
  are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `types`

- Finding: Retain independently owned type trees and structural equality.

- Boundary and ownership review: Reviewed every constructor, array-dimension transfer, query, clone, formatter, and
  destructor. `type_append_array_dimension` consumes its input and detaches the inner pointer before dropping the outer
  shell; type-reference and expression-analysis callers pass owned trees. `type_slice_element` returns a borrowed inner
  descriptor. Function parameter/result types are owned; unsafe and variadic flags participate in equality. `type_free`
  deliberately uses a growable pending stack rather than native recursive teardown. `sem_context`, signature tables,
  interface clones, and symbols retain distinct owned copies. Pointer identity cannot replace structural equality;
  source-language slices cannot represent persistent owning children.

- Function coverage (43): `type_param_vec_free`, `type_new`, `type_new_builtin`, `type_builtin_bool`,
  `type_builtin_tiny`, `type_builtin_byte`, `type_builtin_short`, `type_builtin_int`, `type_builtin_ushort`,
  `type_builtin_uint`, `type_builtin_long`, `type_builtin_ulong`, `type_builtin_float`, `type_builtin_double`,
  `type_builtin_string`, `type_builtin_void`, `type_new_null`, `type_new_struct`, `type_new_enum`, `type_new_pointer`,
  `type_new_nullable`, `type_new_array`, `type_append_array_dimension`, `type_new_slice`, `type_is_slice`,
  `type_slice_element`, `type_array_to_slice_compatible`, `type_new_func`, `type_new_variadic_func`, `type_is_builtin`,
  `type_is_pointer_type`, `type_is_optional_type`, `type_is_nullable_pointer_type`, `type_contains_builtin_real`,
  `type_is_builtin_name`, `type_builtin_from_name`, `type_clone`, `type_equals`, `type_format`, `type_free`,
  `struct_info_free`, `enum_info_free`, `sig_tables_free`.

- Validation references: `type_resolve_test`, `expr_types_test`, and parser/semantic ownership traces; normal/trace and
  aggregate results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate
  validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.demangler`

- Finding: Retain the small LBI inspection parser and bounded cursor ownership.

- Boundary and ownership review: Reviewed all six functions, recursive type/signature/module parsing, cursor
  advancement, null returns, and buffer teardown. The current caller is `util_demangler_test`, exercising compiler LBI
  spellings. This is a diagnostic/testing helper, not L0 numeric or container scaffolding. The cursor is shared through
  nested parsing; the outer `with` frees it and the output buffer on success and failure. No public symbol grammar
  change is in scope.

- Function coverage (6): `demangle_lbi`, `demangle_module_section`, `demangle_name_with_length`,
  `demangle_function_signature`, `demangle_type_component`, `parse_int_prefix`.

- Validation references: `util_demangler_test`; normal/trace and aggregate results are recorded under
  [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.diag`

- Finding: Retain owned diagnostic records and explicit raw-slot cleanup.

- Boundary and ownership review: Reviewed vector operations, collector construction, severity emission, queries, copy
  dispatch, and teardown. `dgv_push` grows before obtaining its destination and managed assignment retains the input
  string fields. Lexer pending-error reset and `dgv_free` clear all owned strings before raw backing storage is freed.
  Driver/parser/analysis/preparation copy diagnostics into separate collectors and preserve severity and error counts. A
  generic byte-copy replacement would lose the ARC contract.

- Function coverage (14): `dgv_create`, `dgv_push`, `dgv_get`, `dgv_length`, `dgv_free`, `diag_create`, `diag_error`,
  `diag_warn`, `diag_note`, `diag_has_errors`, `diag_count`, `diag_get`, `diag_copy`, `diag_free`.

- Validation references: `diag_print_test`, `lexer_error_cleanup_test`, and `parser_test`; normal/trace and aggregate
  results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation
  passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.intset`

- Finding: Use typed compile-time slot states and default capacity.

- Boundary and ownership review: Reviewed allocation, capacity rounding, signed-key normalization, slot access, probing,
  tombstones, rehash, public operations, and cleanup. Parser state owns the set of already-emitted lexer diagnostic
  indices. Backtracking needs membership semantics; the stdlib has no equivalent typed integer set. Keep power-of-two
  growth, normalized negative remainder, -1 miss sentinel, load threshold, raw int/byte storage, and clearing of both
  arrays. The four scalar markers are never assigned after declaration. Fixed arrays and persistent slices cannot
  replace variable capacity.

- Function coverage (19): `_iset_slot`, `iset_create`, `iset_create_with_capacity`, `_iset_alloc`, `_iset_get_state`,
  `_iset_set_state`, `_iset_get_key`, `_iset_set_key`, `_iset_find`, `_iset_find_insert`, `_iset_needs_grow`,
  `_iset_rehash`, `iset_add`, `iset_has`, `iset_remove`, `iset_size`, `iset_capacity`, `iset_clear`, `iset_free`.

- Validation references: `intset_test` and `parser_test`; normal/trace and aggregate results are recorded under
  [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.log`

- Finding: Retain the explicit verbosity projection and logging helpers.

- Boundary and ownership review: Reviewed every function and CLI/build/driver callers. The enum order supplies
  filtering; verbosity 0 selects error, 1/2 info, and 3+ debug. Rich output and stage labels are observable CLI text.
  `LogConfig` remains caller-owned and is dropped by command entrypoints. Function-pointer dispatch or variadic
  formatting would add machinery without simplifying the small interface.

- Function coverage (10): `log_config_create`, `log_level_from_verbosity`, `log_level_name`, `log_msg`, `log_error`,
  `log_warning`, `log_info`, `log_debug`, `log_format_stage`, `log_stage`.

- Validation references: `log_test`, `cli_args_test`, and shared CLI/driver integration; normal/trace and aggregate
  results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation
  passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.numbers`

- Finding: Replace bounded nondecimal string arithmetic with existing ulong conversion APIs.

- Boundary and ownership review: Reviewed all formatting, range predicates, sign/zero normalization, magnitude
  comparison, limit tables, digit validation, and canonicalization. Range tables retain exact signed minima and unsigned
  maxima in bases 2/8/10/16. Canonical validation rejects uppercase, signs other than leading minus, invalid
  bases/digits, and overlong magnitudes before conversion. `interface_literal` returns null on invalid payloads;
  `interface_projection::mi_format_checked_bigint` treats an impossible out-of-domain semantic value as ICE-1400.
  `std.text::string_to_ulong_base` checks overflow and returns an optional scalar; `ulong_to_string` owns its temporary
  builder. Retain the decimal fast path, sign handling including negative zero, and range validation; never cast the
  minimum-long magnitude to signed long.

- Function coverage (16): `realnum_to_string`, `bigint_to_string`, `fits_in_short`, `fits_in_ushort`, `fits_in_tiny`,
  `fits_in_byte`, `int_value_fits_builtin`, `bigint_is_negative`, `bigint_significant_digits`, `bigint_compare_digits`,
  `bigint_limit_text_for_name`, `bigint_limit_text`, `bigint_fits_builtin`, `bigint_digits_valid_for_base`,
  `bigint_fits_implemented_domain`, `bigint_to_canonical_decimal`.

- Validation references: `type_resolve_test`, interface-emission parity, and the paired numeric workload; normal/trace
  and aggregate results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence).
  Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.path`

- Finding: Remove the unused inherited wrapper module.

- Boundary and ownership review: All nine functions were read and compared with `std.path`. Repository searches found no
  import or call from Stage 2 production, tests, or tooling. Eight wrappers forward stdlib operations and the remaining
  scan duplicates its implementation; current `fs_path_test` already imports `std.path` directly. Remove this Stage
  2-only orphan while preserving its original inventory row. This is not a native host-path bridge;
  `compiler_filesystem` retains the distinct bridge contracts.

- Function coverage (9): `up_is_sep`, `up_is_absolute`, `up_find_last_sep`, `up_has_parent`, `up_basename`, `up_parent`,
  `up_is_l1_file`, `up_stem`, `up_join`.

- Validation references: `fs_path_test`, production import inventory, and the self-hosting gate; normal/trace and
  aggregate results are recorded under [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate
  validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

### `util.strings`

- Finding: Retain owned splits/clones and strict UTF-8 validation.

- Boundary and ownership review: Reviewed all seven functions and build/driver/interface-parser callers. StringVector
  clones retain each element; split helpers preserve their different empty-field and separator rules. BOM stripping
  returns a managed value. UTF-8 validation bounds-checks continuation access and rejects overlong forms, surrogates,
  truncation, and values above U+10FFFF. Driver validation precedes BOM removal and source caching. The existing stdlib
  does not combine these exact contracts, and borrowed slices cannot replace owned strings that escape into caches.

- Function coverage (7): `us_sv_clone`, `us_split_char`, `us_split_chars2_non_empty`, `us_split_is_space_non_empty`,
  `us_strip_utf8_bom`, `us_is_utf8_continuation`, `us_is_valid_utf8`.

- Validation references: `util_text_test`, `source_paths_test`, and shared source/interface UTF-8 integration;
  normal/trace and aggregate results are recorded under
  [Tranche and validation evidence](#tranche-and-validation-evidence). Candidate validation passed.

- Follow-ups: No separately scoped defect found in this review; retained language/library limitations are observations
  below.

## Retained constraints and L2 observations

- Typed growable owning collections: AST pointer/ID vectors, token vectors, and diagnostic vectors use erased storage
  with explicit casts and destructors. L1 fixed arrays have compile-time extent; slices cannot be stored as persistent
  owning fields. The implementation cost is repeated typed access/cleanup helpers; generic owning collections are an
  observation, not an accepted proposal.
- Recursive ownership: type descriptors and AST metadata require explicit child teardown, and `type_free` uses an
  explicit pending stack. Generated `drop` cleans managed fields but does not recursively own arbitrary pointer
  children. Any stronger ownership abstraction is outside this refactor.
- Owned string subsequences: split helpers and source caching require managed strings that escape their call. Existing
  slice lifetime rules do not provide an owned substring replacement. Copy/allocation cost remains a
  future-language/library observation.
- Native OS operations: no-follow classification, exclusive workspace reservation, absent-destination rename,
  actual-host separators, and direct process status require the existing compiler support ABI. These bridges are
  retained portability contracts rather than obsolete L0 limitations.

## Tranche and validation evidence

Baseline completed successfully before source edits. The preserved Stage 2 native binary and all 120 source files were
compared byte-for-byte with the validated tree immediately before applying the tranche.

One source-changing tranche changes `ast`, `compiler_filesystem`, `util.intset`, and `util.numbers`, and removes the
unused `util.path` module. Numeric boundary tests reuse the existing signed/unsigned limit and overflow cases while
adding negative zero in all supported bases, leading zeros, canonical-payload rejection, and significant-digit
normalization. Interface parity uses one module path for equivalent decimal/binary/octal/hex spellings and compares
complete output bytes and exit status, including malformed and out-of-domain failure cases.

Candidate validation passed from `l1/`, with the same explicit compiler variables and defaults as the baseline:

```sh
L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang \
  UV_CACHE_DIR=/tmp/dea-phase1-review/uv-cache KEEP_ARTIFACTS=1 \
  L1_TRACE_ARTIFACT_DIR=/tmp/dea-phase1-review/candidate-traces \
  make test-stage2 test-stage2-trace test-stage-parity test-all triple-test
```

The single Make invocation reuses shared prerequisites and completed Stage 2 targets when reaching `test-all`.
`candidate.log`, `candidate-traces/`, and the retained triple-bootstrap directory record the results. No later-phase
production sources, Stage 1 production sources, stdlib APIs, diagnostic codes, or public contracts are changed.

Completed candidate gates: Stage 2 normal suite (68 passed), Stage 2 default trace sweep (46 passed, zero leaked
object/string pointers), explicit stage parity, Stage 1 normal suite (84 passed), environment stacking, all four
examples, Docker/Wine runner tests (6), and Stage 2/bootstrap tooling tests (14). Stage 1 default traces also passed
(46, zero leaked object/string pointers), as did both child fixtures for each stage. This completes `make test-all`.
Candidate triple bootstrap retains artifacts at `l1/build/dea/triple-bootstrap-sagdlmz4/`; B/C have identical 137
retained C translation units and identical normalized native artifacts (3,212,496 bytes each). Its final suite passed
all 68 tests, all four examples, and the hello smoke run. The complete invocation exited successfully. Candidate large
trace logs were gzip-compressed with decompression/digest verification; `candidate-trace-compression.log` records 46
files and 9,123,543,114 bytes recovered.

## Performance evidence

Measurements ran after the validation and trace-compression processes finished, on the same host with the same explicit
Clang selection. Each workload used one excluded warm-up pair and seven measured pairs, alternating baseline/candidate
order. All pairs returned identical successful output. These are local wall-clock observations, not a cross-platform
performance guarantee.

The retained [l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/measure.py][measurement-runner]
builds
[l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/numeric_benchmark.l1][numeric-benchmark]
against the preserved original sources and current sources using the same baseline Stage 2 compiler. Numeric runs
perform 10,000 iterations of eight conversions, including unsigned maximum, signed minimum, leading zeros, negative
zero, and the decimal fast path. The compiler-check workload checks the same current Stage 2 source tree with each
native compiler. Interface emission uses the same 100-export hexadecimal-bigint module path. Harness builds are warmed
before their measured pairs.

Generated harnesses retain default full runtime checks and the compiled quarantine defaults (16 MiB and 4,096 entries);
compiler binaries retain basic checks and their 256-entry limit. Runtime quarantine environment overrides are cleared
for both variants. The benchmark selects a shared private stdlib preparation cache. Initial cold build/preparation times
are retained in the raw log but excluded from paired conclusions.

| Workload              | Baseline median (min-max), seconds | Candidate median (min-max), seconds | Median change | Median paired change |
| --------------------- | ---------------------------------- | ----------------------------------- | ------------- | -------------------- |
| Numeric conversions   | 12.6531 (12.5644-12.8356)          | 1.0175 (1.0139-1.1224)              | -91.96%       | -91.99%              |
| Numeric harness build | 6.2155 (6.1565-6.5372)             | 6.1596 (6.0329-6.2791)              | -0.90%        | -2.21%               |
| Compiler check        | 36.3391 (34.2637-36.6104)          | 36.5483 (34.7876-38.5908)           | +0.58%        | +1.53%               |
| Interface emission    | 0.06744 (0.06491-0.07150)          | 0.05491 (0.05418-0.05794)           | -18.58%       | -18.04%              |

The numeric improvement appears in all seven pairs (91.07%-92.10% less time), and interface emission improves in all
seven pairs. Compiler-check ranges overlap; its +0.58% median difference and +1.53% paired median are smaller than the
observed run variation (paired changes range from -1.55% to +6.75%). The measurements do not establish a material
compiler-check regression beyond that noise. Harness-build ranges also overlap. No regression requiring a source
follow-up was found.

A separate one-iteration numeric trace records string allocations falling from 159 to 22 (86.16% fewer), raw `alloc`
events from 143 to 6, and `realloc` events from 25 to 5. Event categories are reported separately because
allocation-layer events overlap. Both traces pass with zero errors, warnings, leaked object pointers, or leaked string
pointers. Main native compiler sizes are unchanged at 4,620,192 bytes; both untraced numeric harnesses are 309,152
bytes, and both traced harnesses are 318,376 bytes.

All seven samples, paired changes, allocation-event counts, configuration, and sizes are retained in
[l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/measurements.json][measurements]. Full
commands/stdout/stderr and trace reports remain under `/tmp/dea-phase1-review/performance/`; its `results.json` includes
the raw setup/build times. Reproduce from the repository root after preserving baseline inputs:

```sh
L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang \
  .venv/bin/python l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/measure.py \
    --l1-root l1 \
    --baseline-sources /tmp/dea-phase1-review/baseline-src \
    --baseline-compiler /tmp/dea-phase1-review/l1c-stage2-baseline.native \
    --candidate-compiler l1/build/dea/bin/l1c-stage2.native \
    --output-dir /tmp/dea-phase1-review/performance --iterations 10000
```

## Phase 1 completion

All 16 assigned modules have completed reviews: five changed (including removal of `util.path`) and eleven unchanged.
All 265 original function bodies are accounted for; the current Phase 1 sources contain 256 after the nine-function
removal. The other 104 original modules retain Pending dispositions in their assigned later phases. No separately scoped
compiler defect was discovered. The overall plan stays active with its existing ADR disposition.

The completed `make test-stage2 test-stage2-trace test-stage-parity test-all triple-test` result is reused after
documentation-only finalization. Production/test input digests and the final diff confirm no intervening relevant
changes. Final Markdown/link, inventory, ADR-impact, staged-whitespace, and pre-commit checks accompany the local
commit.

[measurement-runner]: measure.py
[measurements]: measurements.json
[numeric-benchmark]: numeric_benchmark.l1
[plan]: ../../2026-09-28-stage2-native-source-review-noref.md
