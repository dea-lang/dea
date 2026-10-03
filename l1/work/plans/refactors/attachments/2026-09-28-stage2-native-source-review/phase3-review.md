# Phase 3 backend and build orchestration review

- Review date: 2026-10-03
- Status: Complete (four modules changed, 36 unchanged)
- Parent ledger: [l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md][ledger]

## Scope and method

All 40 Phase 3 production modules (631 original function bodies) were read with their data representations,
callers/callees, failure paths and ownership contracts. The C emission, backend, graph/lifecycle and orchestration
reviews are recorded below. Stage 1 remains unchanged. Both source-changing tranches passed their gates and
measurements; final dispositions are recorded in the parent inventory.

## Toolchain and evidence

Linux x86_64; `/usr/bin/gcc`, Debian GCC 14.2.0-19, explicitly selected for `L0_CC`, `L1_CC` and `L1_RUNTIME_CC`. The
repo-local L0 Stage 2 bootstrap, shared Python environment, default compiler/runtime flags and quarantine settings are
preserved. Commands run from `l1/`, with `XDG_CACHE_HOME=/workspace/dea-cache`, `UV_CACHE_DIR=/workspace/.cache/uv`,
`L1_TEST_JOBS=4`, and `L1_TRACE_TEST_JOBS=2`. Compiler invocations run outside the filesystem sandbox because its UID
mapping fails the existing trusted-parent check for `/tmp`; no trust checks were changed.

Evidence root: `/tmp/dea-phase3-review/`. Original sources and the rebuilt original native Stage 2 compiler are retained
as `baseline-src/` and `l1c-stage2-baseline.native`.

The focused baseline passed `c_emitter_test wrapper_emitter_test backend_test`. Expanded byte-escape and long-minimum
regressions passed against unchanged production sources. Phase 3 does not run `make test-ci`; exhaustive consolidated
validation remains in Phase 5.

## Validation procedure

Each source-changing tranche uses the environment above and:

```sh
KEEP_ARTIFACTS=1 L1_TRACE_ARTIFACT_DIR=/tmp/dea-phase3-review/<tranche>-traces \
  make test-stage2 test-stage-parity test-stage2-trace triple-test TESTS="<focused tests>"
```

The emitter selectors are `c_emitter_test wrapper_emitter_test backend_test`; orchestration selectors are
`build_driver_test compile_driver_test link_driver_test preparation_test`. Triple bootstrap ignores the focused selector
and runs its complete final-compiler normal suite and examples. Additional Python integrations use the Stage 2 normal
runner directly against the already built subject. Broad local validation uses `make test-extended`.

Measurements use `measure_phase3.py`, one warmup followed by seven alternating baseline/candidate pairs with identical
stdout required. Both versions of each harness are compiled with the same preserved compiler against their respective
source snapshots. The emitter workload exercises all 256 byte spellings and all supported long-minimum bases; the link
workload exercises a 100-node dependency chain and launch-failure status cleanup. One-iteration harness traces must pass
the existing analyzer and produce identical stdout. Saved normal compilers also generate C for the same compiler source
snapshot. No validation jobs run concurrently with timed samples.

```sh
../.venv/bin/python work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/measure_phase3.py \
  --l1-root "$PWD" --cc /usr/bin/gcc \
  --baseline-sources /tmp/dea-phase3-review/<before>-src \
  --candidate-sources /tmp/dea-phase3-review/<after>-src \
  --baseline-compiler /tmp/dea-phase3-review/l1c-stage2-<before>.native \
  --candidate-compiler /tmp/dea-phase3-review/l1c-stage2-<after>.native \
  --output-dir /tmp/dea-phase3-review/<after>-perf --harness <harness> --iterations <iterations>
```

| Before   | After    | Harness | Iterations |
| -------- | -------- | ------- | ---------- |
| baseline | tranche1 | emitter | 10000      |
| tranche1 | tranche4 | link    | 1000       |

Replace the angle-bracket placeholders with table values. The orchestration comparison adds `--workloads link`;
whole-compiler C generation does not exercise its changed runtime paths. Confirmation series use `--reverse-pairs` and
select the workload under investigation with `--workloads`.

## Results

Emitter gate: three focused normal tests, stage parity and three traces passed with zero leaked object/string pointers.
Strict triple bootstrap passed with 137 identical retained C translation units and byte-identical normalized B/C native
binaries (4,373,400 bytes). The final compiler passed all 65 normal tests, four examples and the hello smoke run.
Evidence: `tranche1-gate.log`, `tranche1-traces/`, and `l1/build/dea/triple-bootstrap-0finv1g0/`.

The unchanged backend/graph review also passed explicit `array_test`, `slice_trace_test`, `module_graph_test`,
`module_lifecycle_test`, and `l1c_stage1_generated_c_identity_test.py` selections. The new link-driver launch-failure
regression passed against the preserved baseline compiler before orchestration edits. Evidence:
`unchanged-subsystems.log` and `orchestration-regression-control.log`.

Emitter measurements: byte-emission median +0.07%; whole-compiler C-generation median +0.22%, with overlapping ranges
and identical output. Allocation/ARC event counts are unchanged. Both harness traces have zero errors, warnings and
leaked pointers. Normal compiler size changes from 5,032,720 to 5,032,744 bytes. No timing speedup is claimed. Raw
samples, command vectors, trace counts and sizes are retained in
[l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/phase3-measurements.json][measurements].

Orchestration gate: four focused normal tests, stage parity and four traces passed with zero leaked object/string
pointers. Strict triple bootstrap passed with 137 identical retained C translation units and byte-identical normalized
B/C binaries (4,373,400 bytes). The final compiler passed 65 normal tests, four examples and hello. This includes the
10,000-module iterative graph case, diamond/disconnected-root ordering, cycle and entry diagnostic precedence,
transaction rollback, exact argv forwarding, status 127, and launch failure. Evidence: `tranche4-gate.log`,
`tranche4-traces/`, and `l1/build/dea/triple-bootstrap-k7hl3ybu/`.

The seven explicit Stage 2 integrations passed: `l1c_stage1_build_run_multi_cu_test.py`,
`l1c_stage1_compile_only_test.py`, `l1c_stage1_link_set_test.py`, `l1c_stage1_build_run_workspace_test.py`,
`l1c_stage1_managed_preparation_test.py`, `preparation_construction_test.py`, and
`l1c_stage1_arc_trace_regression_test.py`. The historical Stage 1 names are shared fixtures executed against the Stage 2
subject. Evidence: `orchestration-integrations.log`.

Broad local `make test-extended` passed: Stage 1 normal 79, Stage 2 normal 65, stage parity, four examples, six
Docker/Wine runner checks, and 18 Stage 2/bootstrap tooling checks. This aggregate excludes CI-only normal cases; the
relevant ARC regression and slice cases were selected explicitly above. Evidence: `extended.log`.

Orchestration measurements: traversal median +0.42%, with overlapping ranges and identical output. The one-iteration
trace has one fewer managed allocation/drop and one fewer raw allocation/free, with unchanged ARC counts. The original
status vector owned a VectorBase, an ArrayBase and a raw buffer; the replacement owns one int, removing two allocations
per process-status call. Both traces have zero errors, warnings and leaked pointers. Normal compiler size changes from
5,032,744 to 5,032,768 bytes. No timing speedup is claimed. Setup build durations in the measurements attachment are
single-run records, not comparative timing results.

Documentation verification passed: active-plan ADR Impact, repository reference links, Markdown formatting, copyright
headers and diff whitespace. The inventory audit matches all 40 Phase 3 rows to their module reviews. Phases 4 and 5
remain pending; this phase does not close the overall refactor plan.

## Module review

### `backend.l1`

Retain the public backend forwarding boundary and result ownership.

Functions: `backend_generate_module`.

### `backend/coerce.l1`

Retain integer compatibility helpers and signed/unsigned widening and comparison joins. The checked integer domain is
intentional; native wider types do not authorize changing accepted conversions.

Functions: `be_finalize_lowered_call_arg`, `be_finalize_lowered_constructor_arg`, `be_is_int_assignable`,
`be_is_signed_int`, `be_is_legacy_checked_cast_source`, `be_int_type_size`, `be_int_type_min`, `be_int_type_max`,
`be_int_range_contains`, `be_can_widen_int`, `be_common_int_type`, `be_convert_expr_with_expected_type`,
`be_convert_owned_c_expr_with_expected_type`, `be_needs_array_to_slice`.

### `backend/expr.l1`

Retain expression dispatch, aggregate construction and ARC handling. Array/slice backing and temporary lifetimes must
survive their consumers.

Functions: `be_unwrap_paren_expr_id`, `be_bigint_expr_text`, `be_bigint_expr_base`, `be_emit_typed_bigint_expr`,
`be_is_place_expr`, `be_has_side_effects`, `be_pointer_type_or_null`, `be_sizeof_expr_for_type`,
`be_alignof_expr_for_type`, `be_emit_checked_pointer_expr`, `be_is_borrowed_extraction`, `be_emit_checked_index_lvalue`,
`be_emit_direct_function_call`, `be_emit_array_literal_static_initializer`,
`be_try_emit_bare_variant_static_initializer`, `be_eval_const_value`, `be_emit_const_scalar_numeric`,
`be_try_emit_evaluated_const_initializer`, `be_try_emit_let_initializer`, `be_emit_let_initializer`,
`be_try_emit_const_constructor`, `be_emit_const_constructor`, `be_emit_pattern_bindings`, `be_emit_case_literal`,
`be_case_int_literal_value`, `be_case_literal_is_bigint`, `be_case_literal_is_always_false`, `be_case_needs_if_else`.

### `backend/lifetime.l1`

Retain reverse cleanup, branch snapshots, copied-value retains and nullable release guards. These helpers encode
ownership rather than obsolete syntax.

Functions: `be_emit_with_cleanup_header_let_predecl`, `be_needs_arc_temp`, `be_should_materialize_arc_temp`,
`be_materialize_arc_temp`, `be_materialize_slice_array_temp`, `be_scope_chain_has_cleanup`,
`be_emit_retain_for_copied_value`, `be_emit_retain_for_copied_raw_array`, `be_emit_copy_expr_with_retains`,
`be_emit_array_copy_to_raw_storage`, `be_emit_value_cleanup`, `be_emit_struct_cleanup`, `be_emit_enum_cleanup`,
`be_emit_cleanup_at_scope_exit`, `be_emit_drop_stmt`.

### `backend/lower.l1`

Retain named-argument source evaluation before reordered delivery, temporary ownership, array-to-slice and variadic
backing, and cleanup before control exits. Raw accesses are internal representation boundaries; blanket unsafe
annotations would cascade without improving those contracts.

Functions: `be_emit_with_cleanup_header_let_assign`, `be_emit_array_literal_value`,
`be_emit_array_literal_data_initializer`, `be_emit_array_fill_value`, `be_emit_array_to_slice`,
`be_emit_expr_with_expected_type`, `be_emit_owned_expr_with_expected_type`, `be_emit_lvalue`,
`be_emit_comparison_operand`, `be_emit_binary_op`, `be_emit_condition_expr`, `be_emit_constructor_call`,
`be_emit_is_intrinsic`, `be_emit_slice_descriptor`, `be_emit_variadic_call_args`, `be_emit_call`, `be_emit_new_expr`,
`be_emit_expr`, `be_emit_with_cleanup_from_scope`, `be_emit_cleanup_for_return`, `be_emit_cleanup_for_loop_exit`,
`be_emit_return_stmt_with_inline_cleanup`, `be_emit_match_stmt`, `be_emit_case_stmt`, `be_emit_inline_with_header_item`,
`be_emit_with_stmt`, `be_emit_block_sequence`, `be_emit_block_stmt`, `be_emit_scoped_stmt_body`,
`be_emit_condition_branch`, `be_emit_condition_value`, `be_emit_if_branch`, `be_emit_stmt`.

### `backend/output.l1`

Retain source/module output assembly, dependencies and failure cleanup. Owned emitted results remain distinct from
borrowed analysis state.

Functions: `be_emit_let_declarations`, `be_emit_deferred_top_level_let_assignment`,
`be_emit_module_lifecycle_functions`, `be_emit_function_declarations`, `be_emit_module_entry_bridge_if_needed`,
`be_generate_output`.

### `backend/state.l1`

Retain scoped names, temporary counters, context stacks and result ownership. Growing heterogeneous tables still need
typed wrappers over erased storage.

Functions: `be_ice`, `be_ice_string`, `be_create_module`, `be_free`, `be_type_key`, `be_type_key_module`,
`be_type_key_name`, `be_push_type_key`, `be_current_env`, `be_current_unit`, `be_current_expr_arena`,
`be_current_stmt_arena`, `be_find_unit`, `be_target_root`, `be_emits_module_definitions`, `be_target_consumes_symbol`,
`be_target_includes_value_key`, `be_find_env`, `be_resolve_type_ref`, `be_lookup_symbol`, `be_function_c_name`,
`be_clone_function_param_names`, `be_is_symbol_exported`, `be_expr_type`, `be_type_ptr_vec_temp_free`,
`be_type_ptr_map_temp_free`, `be_resolve_let_type`, `be_fresh_label`, `be_push_scope`, `be_pop_scope`,
`be_push_loop_labels`, `be_pop_loop_labels`, `be_push_loop_cleanup_scopes`, `be_pop_loop_cleanup_scopes`,
`be_lookup_local_var_type`, `be_lookup_owned_local_name`, `type_free_opt`, `be_emit_line_directive`,
`be_register_inline_with_cleanup`.

### `backend/stmt.l1`

Retain statement dispatch and structured cleanup lowering; loop and return boundaries must preserve analysis metadata.

Functions: `be_body_reassigns_param`, `be_emit_function_definitions`.

### `backend/types.l1`

Retain stable dependency ordering, visibility closure and opaque external types. The graph grows during discovery, so
fixed collections are unsuitable.

Functions: `be_collect_referenced_type_keys`, `be_collect_type_ref_keys`, `be_collect_target_ast_type_keys`,
`be_collect_required_type_keys`, `be_requires_type`, `be_collect_value_type_dependencies`,
`be_collect_type_dependencies`, `be_dependency_sets_free`, `be_type_keys_contains`, `be_collect_type_keys`,
`be_emit_type_definitions`, `be_prepare_variadic_pack_wrappers`.

### `build_driver.l1`

Retain compiler discovery precedence, platform-specific command transport, prepared input ownership and artifact
plumbing. Shell display strings are not interchangeable with argv transport.

Functions: `bd_prepared_input_free`, `bd_prepared_input_free_opt`, `bd_log_effective_roots`, `bd_prepare_input`,
`bd_append_c_option_words`, `bd_merge_c_option_words`, `bd_format_word_list`, `bd_collect_c_option_words`, `bd_is_dir`,
`bd_is_windows`, `bd_exe_suffix`, `bd_default_exe_name`, `bd_null_device`, `bd_shell_quote_posix`,
`bd_shell_quote_windows`, `bd_shell_quote`, `bd_windows_token_is_plain`, `bd_windows_shell_word_safe`,
`bd_diagnostic_hex_digit`, `bd_diagnostic_word`, `bd_validate_windows_shell_words`, `bd_windows_exec_token`,
`bd_join_shell_words`, `bd_join_display_words`, `bd_is_compiler_version_suffix`, `bd_compiler_driver_name_matches`,
`bd_compiler_flag_family`, `bd_compiler_debug_family`, `bd_has_explicit_opt_flag`, `bd_has_debug_flag`,
`bd_get_optimize_flag`, `bd_float_contract_forbidden_option_reason`, `bd_validate_float_c_options`,
`bd_find_c_compiler`, `bd_take_c_compiler`, `bd_runtime_include_dir`, `bd_runtime_lib_dir`,
`bd_runtime_archive_filename`, `bd_runtime_object_paths_for_build_dir`, `bd_runtime_object_paths`,
`bd_runtime_object_paths_free`, `bd_runtime_object_paths_exist`, `bd_push_standard_flags`, `bd_push_output_flags`,
`bd_replay_compile_output`.

### `c_emitter/abi.l1`

Retain byte-length mangling, reserved C names, exported symbol prefixes and lifecycle names. These spellings are ABI
contracts, including legacy L0 prefixes.

Functions: `cem_upper_ascii`, `cem_has_reserved_prefix`, `cem_mangle_source_leaf_name`, `cem_is_c_keyword`,
`cem_mangle_lbi_section`, `cem_mangle_type_component_to_cb`, `cem_mangle_type_component`, `cem_mangle_lbi_value`,
`cem_mangle_lbi_struct`, `cem_mangle_lbi_enum`, `cem_mangle_module_path_components`, `cem_mangle_struct_name`,
`cem_mangle_enum_name`, `cem_mangle_function_name`, `cem_mangle_let_name`, `cem_mangle_module_init_name`,
`cem_mangle_module_fini_name`, `cem_mangle_module_entry_name`, `cem_mangle_identifier`.

### `c_emitter/declarations.l1`

Retain declaration ordering, source/interface forward declarations, metadata guards, static/exported prototypes and
normalized line-directive paths. These boundaries preserve separate compilation and diagnostics.

Functions: `cem_emit_section_comment`, `cem_emit_module_comment`, `cem_emit_module_separator`,
`cem_emit_unreachable_comment`, `cem_emit_unreachable_marker`, `cem_emit_float_contract_guard`, `cem_emit_header`,
`cem_module_filename`, `cem_emit_line_directive`, `cem_restore_active_line_directive`, `cem_emit_forward_decls`,
`cem_find_enum_variant_info`, `cem_emit_struct_info`, `cem_emit_enum_info`, `cem_emit_let_declaration`,
`cem_emit_zero_initialized_let_declaration`, `cem_function_params`, `cem_function_params_from_names`,
`cem_emit_function_declaration`, `cem_emit_interface_function_declaration`, `cem_emit_external_let_declaration`,
`cem_emit_interface_let_declaration`, `cem_emit_function_definition_header`, `cem_emit_external_void_function_header`,
`cem_emit_function_definition_footer`, `cem_emit_module_entry_bridge`.

### `c_emitter/expr.l1`

Replace equality chains with native case dispatch for the closed byte-escape and integer-base domains. Preserve
printable-byte fallback, hexadecimal padding, exact long-minimum recognition, suffixes and expression spelling. Retain
dynamic argument assembly and destination-aware casts.

Functions: `cem_emit_sizeof_type`, `cem_emit_ord`, `cem_emit_is`, `cem_emit_enum_tag`, `cem_emit_widen_int`,
`cem_emit_int_literal`, `cem_emit_binary_bigint_literal`, `cem_emit_bigint_literal`, `cem_is_long_min_bigint`,
`cem_emit_typed_bigint_literal`, `cem_emit_real_literal`, `cem_emit_bool_literal`, `cem_emit_const_bool_literal`,
`cem_encode_c_byte_literal`, `cem_emit_byte_literal`, `cem_emit_string_literal`, `cem_emit_const_string_literal`,
`cem_emit_var_ref`, `cem_emit_unary_op`, `cem_emit_negated_condition`, `cem_emit_binary_op`,
`cem_emit_condition_binary_op`, `cem_emit_checked_int_div`, `cem_emit_checked_int_mod`, `cem_emit_checked_int_mul`,
`cem_emit_checked_int_add`, `cem_emit_checked_int_sub`, `cem_emit_checked_int_div_for_type`,
`cem_emit_checked_int_mod_for_type`, `cem_emit_checked_int_mul_for_type`, `cem_emit_checked_int_add_for_type`,
`cem_emit_checked_int_sub_for_type`, `cem_emit_function_call`, `cem_emit_field_access`, `cem_emit_paren_expr`,
`cem_emit_cast`, `cem_emit_checked_ptr_access`, `cem_emit_checked_ptr_index_access`,
`cem_emit_checked_ptr_access_for_base`, `cem_emit_drop_begin_expr`, `cem_emit_drop_finish_call`,
`cem_emit_checked_narrow_cast`, `cem_emit_checked_signed_cast`, `cem_emit_checked_unsigned_cast`, `cem_emit_unwrap_ptr`,
`cem_emit_unwrap_opt`, `cem_emit_null_check_eq`, `cem_emit_null_check_ne`, `cem_emit_pointer_null_check`,
`cem_emit_condition_pointer_null_check`, `cem_emit_optional_has_value`, `cem_emit_optional_value`,
`cem_emit_enum_tag_access`, `cem_emit_enum_payload_field_access`, `cem_emit_string_equals_call`,
`cem_emit_string_concat_call`, `cem_emit_opt_equals_call`, `cem_emit_string_compare_call`,
`cem_emit_condition_string_compare_call`, `cem_emit_discard_expr`, `cem_emit_deref_lvalue`, `cem_emit_field_lvalue`,
`cem_emit_index_lvalue`, `cem_emit_struct_constructor`, `cem_emit_struct_static_initializer`,
`cem_emit_struct_constructor_for_type`, `cem_emit_struct_static_initializer_for_type`, `cem_emit_variant_constructor`,
`cem_emit_variant_static_initializer`, `cem_emit_variant_constructor_for_type`,
`cem_emit_variant_static_initializer_for_type`.

### `c_emitter/lifetime.l1`

Retain type-directed retain/release and destruction emission, including nullable guards and recursive aggregate
ownership. Generated cleanup order is observable.

Functions: `cem_emit_module_top_level_let_cleanup`, `cem_emit_string_retain`, `cem_emit_string_release`,
`cem_enum_info_has_arc_data`, `cem_emit_value_cleanup`, `cem_emit_raw_array_cleanup`, `cem_emit_struct_cleanup`,
`cem_emit_enum_cleanup`.

### `c_emitter/state.l1`

Retain emitter ownership of maps, cloned types and cached prefixes. Dynamic wrapper inventories grow during lowering;
fixed arrays would not fit. The teardown helpers retain their separate semantic roles.

Functions: `cem_ice`, `cem_ice_string`, `cem_opt_wrapper_map_free`, `cem_func_ptr_map_free`, `ccb_create`, `ccb_free`,
`ccb_indent`, `ccb_dedent`, `ccb_prefix`, `ccb_emit`, `ccb_emit_raw`, `ccb_to_string`, `cem_create`,
`cem_reset_optional_wrappers`, `cem_reset_func_ptr_typedefs`, `cem_reset_array_wrappers`, `cem_reset_slice_wrappers`,
`cem_free`, `cem_set_analysis`, `cem_set_module_target`, `cem_set_module_type_keys`, `cem_analysis`,
`cem_module_target_includes_value_key`, `cem_module_target_includes_analysis_key`, `cem_module_target_matches`,
`cem_module_target_includes_type`, `cem_get_output`, `cem_fresh_tmp`, `cem_type_free_opt`.

### `c_emitter/stmt.l1`

Retain structured statement spelling, labels, source directives and indentation. Existing builders preserve evaluation
and cleanup boundaries without introducing artificial variadic interfaces.

Functions: `cem_emit_expr_stmt`, `cem_emit_return_stmt`, `cem_emit_return_void_stmt`, `cem_emit_label`, `cem_emit_goto`,
`cem_emit_block_start`, `cem_emit_block_end`, `cem_emit_while_header`, `cem_emit_if_header`, `cem_emit_else`,
`cem_emit_for_loop_start`, `cem_emit_for_loop_end`, `cem_emit_let_decl`, `cem_emit_assignment`, `cem_emit_temp_decl`,
`cem_emit_comment`, `cem_emit_exit_switch`, `cem_emit_pointer_assignment`, `cem_emit_checked_pointer_assignment`,
`cem_emit_match_scrutinee_decl`, `cem_emit_switch_start`, `cem_emit_match_switch_start`, `cem_emit_switch_end`,
`cem_emit_case_label`, `cem_emit_default_label`, `cem_emit_null_assignment`, `cem_emit_alloc_obj`,
`cem_emit_struct_init`, `cem_emit_struct_init_from_fields`, `cem_emit_enum_variant_init`, `cem_emit_zero_init`,
`cem_emit_try_check_niche`, `cem_emit_try_check_value`, `cem_emit_try_extract_value`, `cem_emit_pattern_binding_init`.

### `c_emitter/type_names.l1`

Retain canonical primitive and nominal C names, pointer/nullable wrappers and function-signature keys. Names participate
in ABI and wrapper deduplication.

Functions: `cem_is_niche_nullable`, `cem_opt_key_for_type`, `cem_func_ptr_name_for_type`, `cem_type_component`,
`cem_array_wrapper_name_for_type`, `cem_slice_wrapper_name_for_type`, `cem_opt_wrapper_name_for_inner`.

### `c_emitter/types.l1`

Retain aggregate definitions, enum payload layout and forwarded type dependencies. Native L1 enum adoption inside the
compiler does not justify changing generated program layouts.

Functions: `cem_emit_pointer_type`, `cem_emit_type`, `cem_emit_none_value_for_nullable`,
`cem_emit_some_value_for_nullable`, `cem_emit_null_literal`, `cem_emit_zero_initializer`.

### `c_emitter/wrappers.l1`

Retain recursive wrapper collection, cloned-type ownership, stable emission and per-kind generated lifecycle helpers.
Borrowed type views would not replace owned inventories safely.

Functions: `cem_note_opt_wrapper`, `cem_note_func_ptr_typedef`, `cem_collect_func_ptrs_from_type`,
`cem_note_array_wrapper`, `cem_note_slice_wrapper`, `cem_collect_array_wrappers_from_type`,
`cem_collect_opt_wrappers_from_type`, `cem_array_base_element_type`, `cem_emit_array_wrapper`,
`cem_emit_array_wrappers`, `cem_emit_slice_wrapper`, `cem_emit_slice_wrappers`,
`cem_emit_array_wrappers_for_defined_type`, `cem_collect_wrappers_from_type_ref`,
`cem_collect_wrappers_from_ast_type_refs`, `cem_is_early_inner`, `cem_emit_type_typedef_deps`,
`cem_emit_optional_wrapper`, `cem_emit_optional_wrapper_for_defined_type`, `cem_prepare_optional_wrappers`,
`cem_emit_optional_wrappers`, `cem_emit_func_ptr_type_deps`, `cem_emit_func_ptr_typedef`, `cem_emit_func_ptr_typedefs`.

### `codegen_options.l1`

Retain the typed option record and constructors. Runtime-selected flags are not compile-time constants.

Functions: `cg_options_create`, `cg_options_from_cli`, `cg_options_free`.

### `compile_driver.l1`

Retain orchestration entrypoint and owned preparation/result lifetime.

Functions: `cd_cmd_compile`.

### `compile_driver/compile.l1`

Retain frontend, projection, emission and native compilation ordering, including diagnostics and early cleanup.

Functions: `cd_staged_invalid`, `cd_validate_staged`, `cd_compile_analyzed`, `cd_register_workspace_directory_chain`,
`cd_compile_analyzed_to_workspace`.

### `compile_driver/toolchain.l1`

Retain compiler-family options and native command construction. Windows and POSIX transport preserve different quoting
rules.

Functions: `cd_is_generic_cc_name`, `cd_is_darwin_system_clang_alias`, `cd_debug_compiler_family`,
`cd_push_object_compile_words`, `cd_compiler_for_transaction`, `cd_path_for_transaction`, `cd_compile_shell_command`,
`cd_validate_windows_compile_values`.

### `compile_driver/transaction.l1`

Retain no-follow filesystem checks, interface-last publication and restoration of previous artifacts. Cleanup attempts
must not short-circuit after a failure; recovery evidence may need to survive.

Functions: `cd_transaction_free`, `cd_error`, `cd_ensure_directory`, `cd_validate_destination`,
`cd_prepare_destinations`, `cd_transaction_create`, `cd_configure_module_staging`, `cd_create_transaction_for_identity`,
`cd_create_transaction`, `cd_delete_if_present`, `cd_cleanup_transaction`, `cd_cleanup_transaction_checked`,
`cd_testable_rename`, `cd_backup_one`, `cd_publish_one`, `cd_rollback_one`, `cd_rollback_publication`,
`cd_publish_artifacts`, `cd_resolve_artifacts`.

### `link_driver.l1`

Retain public link/build/run orchestration and preparation boundaries.

Functions: `ld_cmd_link`, `ld_cmd_build_run`, `ld_cmd_build`, `ld_cmd_run`.

### `link_driver/build.l1`

Retain wrapper/native input ordering, host invocation and transactional publication.

Functions: `ld_build_order`, `ld_build_run_transaction`, `ld_stage_managed_c`, `ld_compile_source_nodes`,
`ld_build_run_operands`.

### `link_driver/inputs.l1`

Retain operand prevalidation before sibling reads, first-selected-path authority, verified interfaces and discovery
ownership. Discovery appends owned inputs without changing explicit-root ordering.

Functions: `ld_copy_interface_diags`, `ld_load_sibling_interface`, `ld_prepare_cli_inputs_managed`,
`ld_prepare_cli_inputs_with_paths`, `ld_prepare_cli_inputs`, `ld_discover_provider`, `ld_discover_providers`.

### `link_driver/model.l1`

Represent the closed traversal domain with LinkVisitState instead of integer sentinels. Retain plan-owned inputs,
borrowed module lookup, explicit frame ownership and typed container wrappers.

Functions: `ld_ptr_vec_create`, `ld_ptr_vec_push`, `ld_ptr_vec_get`, `ld_visit_frames_free`, `ld_string_vector_pop`,
`ld_error`, `ld_input_create`, `ld_foreign_input_create`, `ld_input_interface`, `ld_input_free`, `ld_inputs_free`,
`ld_plan_free`, `ld_plan_input_get`, `ld_input_is_native`, `ld_input_link_path`, `ld_join_module_names`,
`ld_format_cycle`.

### `link_driver/plan.l1`

Use named traversal states while retaining iterative DFS, selected-entry-first ordering, stored import order and exact
cycle diagnostics. Explicit frames prevent native stack overflow on deep graphs.

Functions: `ld_verify_interfaces`, `_ld_assert_verified_input_invariants`, `ld_register_modules`,
`ld_validate_provider_expectation`, `ld_validate_dependencies`, `ld_select_entry`, `ld_visit_module`,
`ld_compute_lifecycle_order`, `ld_prepare_registered_plan`, `ld_prepare_verified_plan`, `ld_prepare_inputs`.

### `link_driver/provenance.l1`

Retain reverse reachability grouped by provider and early completion after all consumers. Diagnostics remain in original
input/provider order.

Functions: `ld_collect_provenance_provider`, `ld_collect_interface_provenance_providers`, `ld_provenance_target_free`,
`ld_provenance_targets_free`, `ld_provenance_target_get_or_create`, `ld_collect_provenance_targets`,
`ld_build_reverse_imports`, `ld_reverse_imports_free`, `ld_provenance_pair_key`, `ld_collect_unreachable_target`,
`ld_emit_unreachable_provenance`, `ld_validate_transitive_provenance`.

### `link_driver/toolchain.l1`

Retain exact argv words, compiler-family flags, separate Windows CRT/shell quoting and response-file thresholds. These
compatibility paths are still required.

Functions: `ld_runtime_include_free`, `ld_runtime_include`, `ld_runtime_archive`, `ld_runtime_link_inputs`,
`ld_take_compiler`, `ld_validate_external_link_operands`, `ld_host_input_path`, `ld_validate_cli_before_preparation`,
`ld_windows_shell_word_safe`, `ld_validate_windows_shell_words`, `ld_validate_windows_shell_values`,
`ld_validate_windows_build_run_values`, `ld_push_wrapper_compile_words`, `ld_push_final_link_words`,
`ld_push_final_link_words_with_runtime_inputs`, `ld_wrap_system_command`, `ld_response_file_text`,
`ld_captured_command`, `ld_run_host_command`, `ld_validate_wrapper_object`, `ld_execute_plan`.

### `link_driver/transaction.l1`

Retain native publication, no-follow checks, rollback and cleanup/recovery behavior. Filesystem bridges are portability
contracts.

Functions: `ld_transaction_create`, `ld_transaction_free`, `ld_create_transaction_for_identity`,
`ld_create_transaction`, `ld_delete_if_present`, `ld_cleanup_transaction`, `ld_validate_output`,
`ld_validate_output_alias`, `ld_validate_output_aliases`.

### `link_driver/workspace.l1`

Replace the one-element erased status vector with a scoped new int(0), passed directly to the native int\*
process-status ABI. L1 has no address-of operation, so a stack scalar or fixed array cannot supply this pointer.
Preserve exact argv, child status, launch diagnostics and workspace cleanup.

Functions: `ld_validate_retained_c_root`, `ld_validate_retained_c_modules`, `ld_ensure_retained_c_directory`,
`ld_cleanup_retained_c_tree`, `ld_copy_retained_c_file`, `ld_retain_build_run_c`, `ld_run_built_program`,
`ld_build_run_in_workspace`.

### `module_graph.l1`

Retain graph-owned nodes, borrowed indexes, source encounter order and canonical interface ordering. Direct imports and
semantic requirements remain distinct.

Functions: `_mg_ptr_vec_create`, `_mg_ptr_vec_push`, `_mg_ptr_vec_get`, `_mg_artifact_error`,
`_mg_validate_artifact_module`, `_mg_has_regular_extension`, `_mg_artifacts_from_stem`,
`mg_interface_path_from_object_path`, `mg_artifacts_for_module`, `mg_artifacts_from_object`,
`mg_artifacts_from_interface`, `mg_artifacts_free`, `_mg_origin_create`, `_mg_node_create`, `mg_node_from_source`,
`mg_node_from_interface`, `mg_node_from_registry`, `mg_node_virtual`, `mg_dependency_free`, `mg_node_free`,
`mg_node_add_dependency`, `mg_node_dependency_count`, `mg_node_dependency_get`, `mg_node_add_direct_import`,
`mg_node_direct_import_count`, `mg_node_direct_import_get`, `mg_node_add_interface_import`,
`mg_node_interface_import_count`, `mg_node_interface_import_get`, `mg_node_set_state`, `mg_node_state`, `mg_create`,
`mg_free`, `mg_add_node`, `mg_find_node`, `_mg_add_semantic_closure`, `mg_semantic_closure`, `mg_node_count`,
`mg_node_names_sorted`, `mg_nodes_sorted`.

### `module_graph/order.l1`

Retain stable topological ordering and cycle reporting, including borrowed output and scratch ownership.

Functions: `mg_dependency_order_visit`, `mg_dependency_order`.

### `module_lifecycle.l1`

Retain dependency-first initialization and reverse finalization. Lifecycle edges must not be synthesized from
semantic-only dependencies.

Functions: `ml_mangle_symbol`, `ml_init_symbol_name`, `ml_fini_symbol_name`, `ml_entry_symbol_name`.

### `preparation.l1`

Retain the opaque native construction/cache boundary and its lifetime. Existing architecture and eligibility policy are
outside this refactor.

Functions: `pr_get`, `pr_json_string`, `pr_json_option`, `pr_bool`, `pr_compiler`, `pr_create`, `pr_report_error`,
`pr_command_guidance`, `pr_repair_command`, `pr_report_disabled`, `pr_construct`, `pr_build_selected`,
`pr_print_selection`, `pr_prepare`, `pr_log_context`, `pr_cmd_prepare`.

### `preparation/consumer.l1`

Retain native getters, exact two-pass lengths and copied UTF-8 values. The C context must outlive consumers.

Functions: `mp_create`, `mp_free`, `mp_ensure`, `mp_runtime`, `mp_source_paths`, `mp_log_provider`,
`mp_bind_native_artifacts`, `mp_analyze`, `mp_bundled_provider`.

### `preparation/frontend.l1`

Retain semantic generation and scoped private support. Error exits preserve diagnostics and release support after its
final consumer.

Functions: `pr_copy_diags`, `pr_write`, `pr_generate_module_with_options`, `pr_generate_module`, `pr_frontend_module`,
`pr_frontend_workspace_order`, `pr_frontend_order`, `pr_frontend_prepare`.

### `wrapper_emitter.l1`

Retain ordered module initialization, entry invocation and reverse finalization. The generated C entry wrapper is a
native ABI boundary.

Functions: `we_append_line`, `we_emit_wrapper`.

## Retained constraints and L2 observations

- Growable heterogeneous ownership still requires typed wrappers around `VectorBase*` and erased payloads. Native
  arrays/slices do not provide generic owned containers or replace graph-owned nodes with borrowed indexes.
- Native process status requires `int*`; without address-of, a scoped scalar allocation is the simplest typed owner.
- Compiler-family command transport, transactional filesystem operations and opaque preparation remain native bridges.
  Their portability and ABI purposes survive the removal of inherited L0 syntax constraints.
- Explicit frame stacks preserve deep dependency traversal without native recursion. Native enums clarify traversal
  state without changing the algorithm or diagnostic ordering.

These are implementation observations, not accepted language proposals. No external follow-up is required for the
reviewed modules.

[ledger]: review.md
[measurements]: phase3-measurements.json
