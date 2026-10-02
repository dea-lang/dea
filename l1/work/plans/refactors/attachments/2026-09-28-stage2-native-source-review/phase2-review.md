# Phase 2 frontend and semantic review

- Review date: 2026-10-02
- Status: Complete (seven modules changed, 49 unchanged)
- Parent ledger: [l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md][ledger]

## Scope and method

All 56 Phase 2 modules (796 original function bodies) were read function by function, including data representations,
failure paths and relevant callers/callees. The four review tranches below retain dynamic ownership and observable
diagnostic ordering. Function lists identify the original bodies reviewed, including helpers removed by the
implementation. Stage 1 remains unchanged. All four source-changing tranches passed their gates; final dispositions are
recorded in the parent inventory.

## Baseline and validation

The pre-edit baseline includes the preparation construction-boundary changes.

Host: Linux x86_64. Explicit native compiler: `/usr/bin/gcc`, Debian GCC 14.2.0-19, selected for `L0_CC`, `L1_CC` and
`L1_RUNTIME_CC`. Repository compiler/runtime flags and quarantine defaults are preserved. No CFLAGS overrides. The
repo-local L0 Stage 2 bootstrap and shared Python environment are used. Cache roots are explicitly writable; compiler
invocations run outside the filesystem sandbox because its UID mapping fails the existing trusted-parent check. No trust
checks were changed.

Evidence root: `/tmp/dea-phase2-review/`. `baseline-src/` retains original Stage 2 sources. Completed trace logs are
losslessly gzip-compressed with SHA-256 verification after both producer and analyzer close them; reports stay readable.

```sh
UV_CACHE_DIR=/tmp/dea-phase2-review/uv-cache UV_OFFLINE=1 XDG_CACHE_HOME=/workspace/dea-cache \
  L0_CC=/usr/bin/gcc L1_CC=/usr/bin/gcc L1_RUNTIME_CC=/usr/bin/gcc \
  L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=2 KEEP_ARTIFACTS=1 \
  L1_TRACE_ARTIFACT_DIR=/tmp/dea-phase2-review/baseline-traces make test-ci
```

The source-changing gates use the same environment, a distinct trace artifact directory per tranche, and
`make test-stage2 test-stage-parity test-stage2-trace triple-test TESTS="<focused tests>"` with these selectors:

| Tranche | Focused tests                                                                               | Added coverage                                                                                                                          |
| ------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 1       | `lexer_test parser_test`                                                                    | Empty/missing/duplicate variadic candidates, deferred recovery/backtracking, mixed unary/cast/index AST, operator and diagnostic parity |
| 2       | `name_resolver_test locals_test signatures_test type_resolve_test expr_types_test`          | Signed extrema, nonnegative bitwise domain, exact shift limits/overflow, constant acceptance and interface parity                       |
| 3       | `expr_types_test analysis_test`                                                             | Existing cleanup/header return checks plus both orderings of return versus break/continue in parity                                     |
| 4       | `interface_test interface_fingerprint_test interface_replay_test driver_test analysis_test` | Byte-string prefixes, embedded NUL, Unicode, existing stable duplicate ordering and pinned fingerprints, declaration permutation parity |

Performance procedure: `measure_phase2.py` runs one warmup and seven alternating baseline/candidate pairs with identical
stdout required. Parser, constant and interface harnesses are compiled with one preserved compiler against each source
tree; one-iteration ARC/memory traces compare allocation events. Whole-compiler checking and a reverse-ordered
500-export interface workload compare saved native compilers. Measurements run without concurrent validation jobs.

Source snapshots and normal native compilers are preserved before and after each tranche. The measurement command, run
from `l1/` under the environment above, is:

```sh
../.venv/bin/python work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/measure_phase2.py \
  --l1-root "$PWD" --cc /usr/bin/gcc \
  --baseline-sources /tmp/dea-phase2-review/<before>-src \
  --candidate-sources /tmp/dea-phase2-review/<after>-src \
  --baseline-compiler /tmp/dea-phase2-review/l1c-stage2-<before>.native \
  --candidate-compiler /tmp/dea-phase2-review/l1c-stage2-<after>.native \
  --output-dir /tmp/dea-phase2-review/<after>-perf --harness <harness> --iterations <iterations>
```

| Tranche | Before   | After    | Harness   | Iterations |
| ------- | -------- | -------- | --------- | ---------- |
| 1       | baseline | tranche1 | parser    | 2000       |
| 2       | tranche1 | tranche2 | const     | 100000     |
| 4       | tranche3 | tranche4 | interface | 500        |

Replace the angle-bracket placeholders with the table values before running. Confirmation series omit `--harness` and
select `--workloads compiler_check` or `--workloads interface_emit` with `--reverse-pairs`. The measurements attachment
retains raw samples, deduplicated command vectors, trace operation counts and artifact sizes.

Baseline `make test-ci`: passed before production edits. Stage 1 normal: 87; Stage 2 normal: 71 (both include CI-only
cases). Stage parity, four examples, six Docker/Wine runner checks, 18 tooling checks and environment/bootstrap
integration passed. Both default trace sweeps passed 47 cases, and both child suites passed two fixtures, with zero
leaked object/string pointers. Strict triple bootstrap passed: 137 identical retained C translation units; normalized
B/C binaries are both 4,381,608 bytes and byte-identical. Its final compiler passed 65 normal tests, four examples and
the hello smoke run. Full logs and bootstrap artifacts are retained under the evidence root and
`l1/build/dea/triple-bootstrap-rozpi7np/`.

The expanded Phase 2 parity corpus also passed against both unchanged compilers before edits (`parity-probe.log`).

Tranche 1 is complete: two focused normal tests, two traces (zero leaked pointers), expanded stage parity and strict
triple bootstrap passed. The final self-built suite passed 65 tests, four examples and hello; all 137 retained C units
match and normalized B/C binaries are identical (4,373,416 bytes). Evidence: `tranche1-gate.log`, `tranche1-traces/` and
`l1/build/dea/triple-bootstrap-avokcgkf/`.

Tranche 1 measurements: parser median -3.1%, full-compiler check +3.3%, interface emission -0.9%. Timing ranges overlap
substantially. A second seven-pair compiler-check series with reversed pair order measured -1.9%; the initial slowdown
was not repeatable. No timing speedup is claimed. Parser allocation counts are unchanged, with 51 fewer ARC retains and
51 fewer releases per sample. Both harness traces have zero errors, warnings and leaked pointers. Normal compiler size
decreased from 5,041,592 to 5,032,936 bytes. Raw samples are in
[l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/phase2-measurements.json][measurements].

Tranche 2 is complete: five focused normal tests, five traces (zero leaked pointers), expanded stage parity and strict
triple bootstrap passed. The self-built suite passed 65 tests, four examples and hello; 137 retained C units match and
normalized B/C binaries are identical (4,373,416 bytes). Evidence: `tranche2-gate.log`, `tranche2-traces/` and
`l1/build/dea/triple-bootstrap-2eddbmvm/`.

Tranche 2 measurements: the checked constant-operation workload improved from 0.3501 s to 0.01547 s median (-95.6%).
Full-compiler check changed +0.6%. Interface emission initially changed +4.0% (about 4 ms), then -3.1% in a second
seven-pair series with reversed order; this difference was not repeatable. Both constant harness traces contain no
memory events, one ARC release, and zero errors/warnings/leaked pointers. Normal compiler size decreased from 5,032,936
to 5,032,808 bytes. Raw samples are in the measurements attachment.

Tranche 3 is complete: two focused normal tests, two traces (zero leaked pointers), expanded stage parity and strict
triple bootstrap passed. The self-built suite passed 65 tests, four examples and hello; 137 retained C units match and
normalized B/C binaries are identical (4,373,416 bytes). Evidence: `tranche3-gate.log`, `tranche3-traces/` and
`l1/build/dea/triple-bootstrap-a_x5faqb/`.

The cleanup-flow change only replaces integer assignments/comparisons with an existing value enum's tag. Generated C
adds no allocation, ARC operation or traversal. The expression checker trace retains exactly 1,382,921 events; the
normal compiler and normalized bootstrap sizes are unchanged. No separate timing workload is warranted for this
representation-only change.

Tranche 4 is complete: five focused normal tests, five traces (zero leaked pointers), expanded stage parity and strict
triple bootstrap. The self-built suite passed 65 tests, four examples and hello; 137 retained C units match and
normalized B/C binaries are identical (4,373,400 bytes). Evidence: `tranche4-gate.log`, `tranche4-traces/` and
`l1/build/dea/triple-bootstrap-rljc156_/`.

Tranche 4 measurements: interface workload median -0.5%, full-compiler check -2.5%, interface emission -4.1%. Timing
ranges overlap, so no speedup is claimed. Both harness traces contain the same 70,160 events and identical allocation
and ARC counts, with zero errors, warnings or leaked pointers. Normal compiler size decreased from 5,032,808 to
5,032,720 bytes. Raw samples are in the measurements attachment.

## Review findings and function coverage

Paths below are relative to `l1/compiler/stage2_l1/src/`. Each entry includes all original function bodies in that
module; data-only modules are called out explicitly.

### Tranche 1: Lexer and source parser

#### `lexer.l1`

Retain UTF-8 codepoint columns, byte-valued escapes, checked numeric accumulation, deferred error wrappers and growable
token storage. ASCII range helpers encode language rules; they are not interchangeable with locale character APIs.

Functions: `is_ident_start`, `is_ident_part`, `is_escape_char`, `escape_char_value`, `is_binary_digit`,
`is_octal_digit`, `is_hex_digit`, `hex_char_to_int`, `ls_is_unicode_scalar`, `ls_append_utf8`, `is_printable_ascii`,
`ls_create`, `ls_has_errors`, `ls_emit_error`, `ls_queue_token`, `ls_has_queued_tokens`, `ls_take_queued_token`,
`ls_defer_recoverable_error`, `ls_clear_pending_error`, `ls_queue_pending_errors`, `ls_queue_pending_recovery`,
`ls_queue_terminal_recovery`, `ls_free`, `ls_at_end`, `ls_peek`, `ls_peek_next`, `ls_advance`, `tokenize`,
`ls_next_token`, `ls_read_byte_literal`, `ls_read_string_literal`, `ls_read_valid_char_escape`, `ls_read_number`,
`ls_skip_whitespace_and_comments`, `ls_skip_invalid_characters`.

#### `ast_printer.l1`

Retain recursive AST traversal and explicit precedence/type suffix rendering. IDs borrow arena nodes; builders own their
output. Printer bytes are observable through --ast.

Functions: `ap_bool_str`, `ap_span_suffix`, `ap_indent_str`, `ap_print_line`, `ap_print_label`, `ap_quote_string`,
`ap_module_prefix`, `ap_full_name`, `ap_print_type_ref`, `ap_print_export_manifest`, `ap_print_import`,
`ap_print_param`, `ap_print_field_decl`, `ap_print_enum_variant`, `ap_print_pattern`, `ap_print_expr`, `ap_print_stmt`,
`ap_print_func_decl`, `ap_print_struct_decl`, `ap_print_enum_decl`, `ap_print_type_alias_decl`, `ap_print_let_decl`,
`ap_print_top_level_decl`, `ap_print_module`.

#### `parser.l1`

Retain the public parse-result wrapper and arena/diagnostic ownership transfer. Token parsing and source parsing share
the implementation parser.

Functions: `parse_result_free`, `parse_has_errors`, `parse_diag_count`, `parse_diag_get`, `impl_result_to_public`,
`parse_module_tokens`, `parse_module_tokens_owned`, `parse_lex_error_result`, `parse_module_source`.

#### `parser/cursor.l1`

Replace `ps_match_any2`, `ps_match_any3` and `ps_match_any4` with the reviewed native variadic body `ps_match_any`.
Preserve candidate order, cursor movement and single-shot deferred lexer diagnostics across backtracking. Logical versus
physical token access remains deliberate.

Functions: `ps_peek`, `ps_skip_lexer_errors`, `ps_logical_token_at_cursor`, `ps_peek_logical_ahead`,
`ps_emit_remaining_lexer_errors`, `ps_last`, `ps_at_end`, `ps_advance`, `ps_check`, `ps_match`, `ps_match_any2`,
`ps_match_any3`, `ps_match_any4`, `ps_check_ident`, `ps_match_ident`, `ps_check_int`, `ps_check_bigint`, `ps_match_int`,
`ps_match_bigint`, `ps_check_real`, `ps_match_real`, `ps_check_byte`, `ps_match_byte`, `ps_check_string`,
`ps_match_string`, `ps_is_top_level_start`, `ps_sync_top_level`, `ps_at_stmt_start`, `ps_sync_stmt`, `ps_expect`,
`ps_expect_ident`, `ps_span_start`, `ps_extend_span`, `ps_expect_variable_name`, `parse_dotted_name_rest`,
`qn_result_free_all`, `ps_try_parse_qualified_name`.

#### `parser/expr.l1`

Use the variadic matcher at binary precedence layers and consolidate identical unary construction. Preserve precedence,
recursive unary association, spans, speculative type-expression rollback and postfix evaluation order.

Functions: `ps_is_builtin_type_name`, `ps_is_unambiguous_type_start`, `ps_type_ref_has_array_suffix`,
`ps_looks_like_array_constructor_start`, `ps_parse_call_argument`, `ps_parse_expr`, `ps_parse_or_expr`,
`ps_parse_and_expr`, `ps_parse_bit_or_expr`, `ps_parse_bit_xor_expr`, `ps_parse_bit_and_expr`, `ps_parse_equality_expr`,
`ps_parse_rel_expr`, `ps_parse_shift_expr`, `ps_parse_add_expr`, `ps_parse_mul_expr`, `ps_parse_unary_expr`,
`ps_parse_cast_expr`, `ps_parse_postfix_expr`, `ps_parse_primary_expr`.

#### `parser/decl.l1`

Retain declaration dispatch, export groups, parameter suffix restrictions, recovery boundaries and transfer of
arenas/diagnostics into ImplParseResult. Lex-error result construction serves both source and interface parsing.

Functions: `ps_make_empty_block_stmt`, `ps_finish_function`, `ps_parse_function`, `ps_parse_extern_func`,
`ps_parse_unsafe_func`, `ps_parse_struct`, `ps_parse_enum`, `ps_parse_type_alias`, `ps_parse_top_level_let`,
`ps_parse_top_level_const`, `ps_parse_top_level_decl`, `ps_parse_ident_list_rest`, `ps_append_export_name`,
`ps_parse_opaque_export_group`, `ps_parse_export_item`, `ps_parse_export_manifest`, `ps_parse_import_decl`,
`ps_parse_module`, `impl_parse_module_tokens`, `ps_lex_error_result`, `ps_tokens_result`, `impl_parse_module_source`.

#### `parser/stmt.l1`

Retain statement dispatch, loop/body scopes, with cleanup forms, case/default recovery and terminal EOF handling.
Growable arm/header vectors are required by source input.

Functions: `ps_parse_pattern`, `ps_parse_block`, `ps_parse_break_stmt`, `ps_parse_continue_stmt`,
`ps_parse_return_stmt`, `ps_parse_drop_stmt`, `ps_parse_let_stmt`, `ps_parse_if_stmt`, `ps_parse_while_stmt`,
`ps_parse_for_stmt`, `ps_parse_for_update_stmt`, `ps_parse_match_stmt`, `ps_parse_with_item`, `ps_parse_with_stmt`,
`ps_parse_case_arm_value`, `ps_at_case_arm_start`, `ps_sync_case_invalid_arm`, `ps_parse_case_stmt`,
`ps_parse_simple_stmt`, `ps_parse_stmt`.

#### `parser/state.l1`

Retain arena-owning parse results and parser-owned diagnostic deduplication set. ps_destroy only destroys parser-local
state; callers explicitly transfer or free arenas and diagnostics.

Functions: `ps_create`, `ps_destroy`, `ps_emit_error`, `ps_has_error`.

#### `parser/token_value.l1`

Retain token payload extraction and width/rendering helpers shared by parsing and diagnostics. Payload spelling and
decoded value differ; ordinal token checks are not value comparisons.

Functions: `tok_is`, `tok_is_ident`, `tok_is_int`, `tok_is_bigint`, `tok_is_real`, `tok_is_byte`, `tok_is_string`,
`tok_is_future_extension`, `token_ident_text`, `token_int_text`, `token_int_value`, `token_bigint_text`,
`token_real_text`, `token_bigint_base`, `token_real_is_float`, `token_byte_text`, `token_byte_value`,
`token_string_text`, `token_string_value`, `token_text_for_width`, `token_width`.

#### `parser/type_ref.l1`

Retain ordered suffix construction, parenthesized/function types, array-bound expressions and variadic restrictions.
Legacy summary fields still have callers; replacing them requires a separate model migration.

Functions: `type_ref_vec_free`, `type_suffix_vec_free`, `ps_parse_const_int_expr`, `ps_parse_type_atom`,
`ps_mark_type_ref_variadic`, `ps_parse_type`.

### Tranche 2: Resolution and semantic foundations

#### `dea_prelude.l1`

Retain reserved builtin-module recognition, intrinsic signatures and synthesized symbol injection. Prelude symbols/types
are owned and have distinct signatures; an array of names would not replace construction semantics.

The `dea_module_name`, `dea_module_filename` and `dea_zero_span` accessors remain the shared API for synthetic provider
identity and source-location construction across passes.

Functions: `dea_module_name`, `dea_module_filename`, `dea_zero_span`, `dea_is_virtual_module_name`, `dea_is_symbol`,
`dea_is_intrinsic_symbol`, `dea_make_virtual_module`, `dea_put_local_symbol`, `dea_add_intrinsic`, `dea_add_type_alias`,
`dea_populate_locals`.

#### `locals.l1`

Retain nested function scopes, binding identities, declaration ordering and parameter/header registration. Local symbols
borrow declarations and own scope maps; generated numeric IDs are semantic identity, not pointer identity.

Functions: `lc_key`, `lc_scope_create`, `lc_scope_define`, `lc_scope_lookup`, `lc_scope_free`, `lc_func_env_free`,
`locals_free`, `locals_env_count`, `locals_env_get`, `locals_env_find`, `lc_func_env_get_block_scope`,
`lc_func_env_get_match_arm_scope`, `lc_scope_track`, `lc_scope_set_block`, `lc_bind_pattern`, `lc_visit_block`,
`lc_visit_scoped_stmt`, `lc_visit_match_arm`, `lc_visit_case_arm`, `lc_visit_case_else`, `lc_visit_with`,
`lc_visit_stmt`, `lc_make_function_env`, `locals_resolve`.

#### `scope_context.l1`

Retain independently owned declared/owned type snapshots, borrowed parent contexts and reverse binding lookup. These
distinctions support cleanup and backend consumers; slices cannot replace growing owned binding lists.

Functions: `sc_create`, `sc_var_free`, `sc_inline_cleanup_free_opt`, `sc_free`, `sc_add_declared`, `sc_add_owned`,
`sc_remove_owned`, `sc_lookup_declared_type`, `sc_has_inline_cleanup`, `sc_push_inline_cleanup`.

#### `sem_context.l1`

Retain owned expression/type, call-target and binding maps plus explicit cloned type storage. IDs connect parser arenas
to later passes; teardown and lookup wrappers document ownership boundaries.

Functions: `analysis_owned_type_map_put`, `analysis_result_free`, `analysis_has_errors`, `analysis_diag_count`,
`analysis_diag_get`, `analysis_source_names`, `analysis_source_texts`, `analysis_name_resolution`,
`analysis_signature_tables`, `analysis_locals`, `analysis_type_map_uses_floating_point`,
`analysis_struct_infos_use_floating_point`, `analysis_enum_infos_use_floating_point`, `analysis_uses_sys_real`,
`analysis_uses_floating_point`, `analysis_expr_key`, `analysis_get_expr_type`, `analysis_get_intrinsic_target`,
`analysis_get_var_ref_resolution`, `analysis_is_arc_type`, `analysis_has_arc_data`.

#### `name_resolver.l1`

Retain the thin orchestration entrypoint; collection, imports and query passes have independent state and error
ordering.

Functions: `nr_resolve`.

#### `name_resolver/collect.l1`

Retain module-scope symbol creation, exported-name registration, enum-variant injection and visibility diagnostics.
Separate namespace and export checks preserve duplicate/recovery order.

Functions: `nr_define_local`, `nr_collect_locals`, `nr_default_exports_name`, `nr_manifest_name_is_opaque`,
`nr_export_transparent_enum_variants`, `nr_compute_exports`, `nr_make_dea_env`.

#### `name_resolver/imports.l1`

Retain open/selective/qualified imports, intrinsic filtering and source/interface extern-shadow checks. Symbol clones
isolate imported names from provider-owned definitions.

Functions: `nr_path_is_same_signature`, `nr_extern_signatures_compatible`, `nr_add_pending_extern_shadow`,
`nr_symbols_same_identity`, `nr_sv_has`, `nr_format_quoted_names`, `nr_import_symbol`, `nr_open_imports_one`,
`nr_bind_import_alias`, `nr_bind_selective_import`, `nr_open_imports`.

#### `name_resolver/interface.l1`

Retain interface-to-symbol materialization and opaque nominal visibility. Function/const/alias payloads carry
information unavailable in source-only declarations.

Functions: `nr_make_interface_module`, `nr_define_interface_symbol`, `nr_export_all_interface_symbols`,
`nr_populate_interface_env`, `nr_make_interface_env`.

#### `name_resolver/query.l1`

Retain resolution by module path, qualifier, namespace and visibility. Alias/canonical-name queries have distinct error
and ownership contracts; merging them would obscure those boundaries.

Functions: `nr_dependency_symbol_name`, `nr_is_cross_module_symbol`, `nr_record_resolved_symbol`,
`nr_resolved_symbol_count`, `nr_resolved_symbol_get`, `nr_env_count`, `nr_env_get`, `nr_env_find`,
`nr_module_env_local`, `nr_module_env_imported`, `nr_module_env_all`, `nr_module_env_is_ambiguous`,
`nr_module_env_imports_module`, `nr_module_env_qualifies_module`, `nr_module_env_alias_target`,
`nr_module_env_has_prelude_name`, `nr_module_env_pending_extern_shadow_count`,
`nr_module_env_pending_extern_shadow_get`, `nr_module_env_local_keys`, `nr_module_env_imported_keys`,
`nr_module_env_export_keys`, `nr_module_env_all_keys`, `nr_env_names_sorted`.

#### `name_resolver/state.l1`

Retain owned resolution scopes and tables with borrowed driver/AST state. Constructor/destructor pairs separate symbol
ownership from module and declaration lifetime.

Functions: `nr_span_diag_error`, `nr_span_diag_warn`, `nr_map_symbol_get`, `nr_build_top_key`, `nr_symbol_free_map`,
`nr_module_env_free`, `nr_free`, `nr_make_env`, `nr_make_owned_env`.

#### `signatures.l1`

Retain the signature-pass entrypoint and ordered collection/resolution stages.

Functions: `sig_resolve`.

#### `signatures/const_init.l1`

Retain source-constant evaluation context, cache/state handling and typed initializer diagnostics. Optional values
distinguish unsupported/nonconstant expressions from valid null constants.

Functions: `sig_infer_literal_type`, `sig_symbol_is_zero_field_enum_variant`, `sig_const_args_are_constant`,
`sig_expr_is_const_initializer`, `sig_resolve_let`.

#### `signatures/cycles.l1`

Retain nominal dependency traversal and cycle diagnostics. Dependency vectors and visit-state maps encode graph
traversal, not fixed collections.

Functions: `sig_extract_dependencies`, `sig_cycle_visit`, `sig_detect_value_type_cycles`.

#### `signatures/declarations.l1`

Retain function, top-level binding and alias signature construction with contextual type resolution and explicit type
ownership.

Functions: `sig_resolve_struct`, `sig_resolve_enum`, `sig_resolve_func`.

#### `signatures/interface.l1`

Retain semantic materialization of interface aliases, exported function/let entries and enum/struct tables. Raw
interface types remain separate from resolved semantic copies.

Functions: `sig_check_materialized_interface_shapes`, `sig_replay_interface_struct`, `sig_replay_interface_enum`,
`sig_replay_interface_entries`, `sig_replay_interfaces`, `sig_check_interface_closure_type`,
`sig_check_interface_closure_surface`, `sig_check_interface_semantic_closures`.

#### `signatures/tables.l1`

Retain owned signature maps, keys, lookup helpers and teardown. Struct and enum field metadata are dynamic and their
borrowed lookup results must outlive expression analysis.

Functions: `sig_key`, `sig_top_decl_name`, `sig_top_decl_span`, `sig_diag_error`, `sig_name_diag_warn`,
`sig_name_diag_error`, `sig_type_vec_free`, `sig_set_free_opt`, `sig_type_vec_free_opt`,
`sig_struct_field_vec_temp_free`, `sig_enum_variant_vec_temp_free`, `sig_pending_shape_add`, `sig_pending_shapes_free`,
`sig_lookup_func_type`, `sig_lookup_struct_info`, `sig_lookup_enum_info`, `sig_lookup_let_type`, `sig_make_tables`,
`sig_type_contains_slice`, `sig_reject_slice_escape`, `sig_check_pending_materialized_shapes`.

#### `signatures/visibility.l1`

Retain export closure and private-type traversal through nested type constructors; diagnostic paths distinguish exported
declarations from dependencies.

Functions: `sig_nominal_display`, `sig_check_nominal_export_visibility`, `sig_check_export_surface_type`,
`sig_check_imported_opaque_layout_type`, `sig_check_internal_opaque_layouts`, `sig_check_exported_struct_surface`,
`sig_check_exported_enum_surface`, `sig_check_exported_surfaces`, `sig_check_pending_extern_shadows`.

#### `type_resolve/const_eval.l1`

Use native complement, bounded power-of-two shift and nonnegative bitwise operations. Preserve signed overflow guards,
negative-operand rejection, shift limits, optional failure and the zero/zero helper fallback. Keep expression recursion,
interface literal validation and cached symbol evaluation unchanged.

Functions: `tr_const_eval_interface_literal_raw`, `tr_const_eval_interface_symbol`, `tr_const_int_min_value`,
`tr_const_int_max_value`, `tr_const_safe_negate`, `tr_const_safe_bitwise_not`, `tr_const_safe_add`,
`tr_const_safe_subtract`, `tr_const_safe_multiply`, `tr_const_safe_divide`, `tr_const_safe_modulo`,
`tr_const_eval_pow2`, `tr_const_safe_positive_bitwise`, `tr_const_safe_shift_left`, `tr_const_safe_shift_right`,
`tr_const_eval_integer_binary_payload`, `tr_const_eval_integer_binary`, `tr_const_eval_integer_compare`,
`tr_const_eval_values_equal`, `tr_expr_names_resolved_const`.

#### `type_resolve/const_value.l1`

Retain tagged constant payloads, typed conversion/range checks, owned cached values and clone/free helpers. BIGINT
spelling/base and scalar null have distinct representations.

Functions: `tr_const_value_new`, `tr_const_value_clone`, `tr_const_value_free`, `tr_const_eval_context_create`,
`tr_const_eval_context_free`, `tr_const_eval_set_failure`, `tr_const_eval_failed`, `tr_const_eval_report_failure`,
`tr_const_value_is_integer_like`, `tr_const_bool_value`, `tr_const_int_value`, `tr_const_value_is_integer`,
`tr_type_is_integer`, `tr_builtin_int_range`, `tr_const_integer_text`, `tr_const_integer_fits`,
`tr_const_integer_for_target`, `tr_real_text_for_target`, `tr_const_value_for_type`, `tr_const_decl_builtin_name`,
`tr_const_value_for_decl`.

#### `type_resolve/lookup.l1`

Retain symbol-kind/visibility-aware type and variant lookup across local, imported and module-qualified names.
Diagnostic ownership and canonical provider identity cross resolver boundaries.

Functions: `tr_key`, `tr_module_from_path`, `tr_type_ref_full_name`, `tr_type_ref_simple_name`,
`tr_ambiguous_type_modules`, `tr_format_ambiguous_modules`, `tr_format_ambiguous_hints`, `tr_diag_error`,
`tr_type_free_opt`, `tr_symbol_lookup_result`, `tr_symbol_lookup_target`, `tr_symbol_lookup`.

#### `type_resolve/materialize.l1`

Retain recursive alias materialization with owned type replacement and cycle state. Transparent aliases expand
semantically without rewriting raw interface identity.

Functions: `tr_finalize_interface_types`, `tr_finalize_materialized_types`.

#### `type_resolve/ref.l1`

Retain contextual TypeRef resolution, ordered suffixes, array-bound evaluation and unsafe/variadic function metadata.
Source integer-domain constraints and diagnostic locations remain explicit.

Functions: `tr_const_eval_cast`, `tr_const_eval_unary`, `tr_const_eval_binary`, `tr_const_eval_symbol`,
`tr_const_eval_expr_in_env`, `tr_const_eval_expr`, `tr_resolve_alias`, `tr_replace_materialized_nominal`,
`tr_materialized_type_symbol`, `tr_finalize_materialized_type`, `tr_apply_suffix`, `tr_resolve_type_ref`.

### Tranche 3: Expression and statement analysis

#### `expr_types.l1`

Retain the expression-analysis orchestration wrapper and shared analysis state.

Functions: `expr_types_check`.

#### `expr_types/convert.l1`

Retain structural type equality, ordered numeric/nullable conversions, literal fit checks and explicit versus implicit
cast rules. Pointer identity cannot substitute for recursive type equality.

Functions: `etc_is_int`, `etc_is_bigint_literal_type`, `etc_nullable_integer_inner`, `etc_bigint_expr_text`,
`etc_bigint_expr_base`, `etc_set_bigint_expr_type`, `etc_diag_bigint_requires_context`, `etc_diag_bigint_context_error`,
`etc_diag_bigint_literal_range_error`, `etc_is_real`, `etc_is_numeric`, `etc_real_binary_result_type`,
`etc_can_widen_real`, `etc_is_nullable`, `etc_nullable_inner`, `etc_supports_equality`, `etc_is_bool`, `etc_is_string`,
`etc_types_equal`, `etc_types_equal_ignoring_func_unsafety`, `etc_has_function_unsafety_mismatch`,
`etc_builtin_int_range`, `etc_diag_int_literal_range_error`, `etc_can_widen_int`, `etc_check_assign_bigint_expr`,
`etc_check_assign_expr`, `etc_can_assign`, `etc_can_cast`, `etc_cast_const_int`, `etc_cast_is_const_null`.

#### `expr_types/expr.l1`

Retain expression dispatch, lvalue/type synthesis, argument evaluation and owned result types. Named-argument canonical
vectors preserve source evaluation order independently of parameter order.

Functions: `etc_infer_sizeof_intrinsic`, `etc_infer_ord_intrinsic`, `etc_infer_is_intrinsic`, `etc_infer_len_intrinsic`,
`etc_infer_slice_intrinsic`, `etc_infer_unary`, `etc_infer_binary`, `etc_infer_call`, `etc_infer_field`,
`etc_infer_index`, `etc_check_array_literal_expr`, `etc_check_expr_against_expected`,
`etc_check_array_literal_expr_mode`, `etc_check_initializer_expr`, `etc_check_array_constructor_arg`, `etc_infer_expr`.

#### `expr_types/liveness.l1`

Retain dynamic binding-state maps, cloned snapshots, branch merges and fixed-point loop restoration. Borrowed slices
cannot replace independently owned snapshots used after mutations.

Functions: `etc_alive_scope_stack_free`, `etc_alive_scope_clone`, `etc_alive_scope_stack_clone`,
`etc_alive_scope_stack_meet`, `etc_alive_scope_stack_equal`, `etc_alive_scope_stack_restore`,
`etc_alive_state_vec_free`, `etc_alive_state_vec_push_clone`, `etc_alive_state_vec_clone`,
`etc_alive_scope_stack_meet_many`, `etc_loop_flow_capture_free`, `etc_capture_break_state`,
`etc_capture_continue_state`, `etc_alive_scope_current`, `etc_alive_scope_push`, `etc_alive_scope_pop`,
`etc_decl_scope_current`, `etc_decl_scope_push`, `etc_decl_scope_pop`, `etc_scope_chain_push`, `etc_decl_outer_has`,
`etc_check_local_declaration`, `etc_alive_lookup`, `etc_alive_set`, `etc_alive_declare`,
`etc_alive_revive_assignment_target`, `etc_check_expr_liveness`.

#### `expr_types/lookup.l1`

Retain callable/intrinsic/constructor resolution, named and variadic argument validation and metadata capture. Canonical
intrinsic names and source aliases serve separate purposes.

Functions: `etc_check_imported_opaque_layout_type`, `etc_nested_symbol_path_full`, `etc_nested_symbol_path_simple`,
`etc_nested_symbol_path_message`, `etc_is_guarded_cleanup_header_local`, `etc_expr_contains_try`,
`etc_stmt_contains_try`, `etc_lookup_visible_local_symbol`, `etc_local_symbol_type`, `etc_lookup_local`,
`etc_lookup_symbol`, `etc_is_void`, `etc_in_unsafe_func`, `etc_symbol_as_type`, `etc_is_imported_opaque_nominal`,
`etc_diag_opaque_layout_use`, `etc_diag_type_ref_failure`, `etc_try_resolve_type_name`,
`etc_try_resolve_sizeof_type_expr`, `etc_try_resolve_enum_variant_symbol`, `etc_expr_is_unqualified_local_ref`,
`etc_expr_contains_unqualified_local_ref`, `etc_get_call_param_names`, `etc_get_struct_field_names`,
`etc_get_enum_variant_field_names_for_symbol`, `etc_get_enum_variant_field_names`, `etc_resolve_named_args`,
`etc_unwrap_paren_expr_id`.

#### `expr_types/patterns.l1`

Retain canonical enum variant lookup, payload bindings, duplicate/exhaustiveness checks and arm-local liveness. Pattern
metadata borrows AST nodes and owns resolved types.

Functions: `etc_bind_pattern_types`, `etc_find_enum_variant_info`, `etc_pattern_symbol_name`,
`etc_nested_pattern_path_message`, `etc_check_match_pattern`, `etc_format_missing_match_variants`,
`etc_match_variants_fully_covered`, `etc_check_match_exhaustiveness`, `etc_match_wildcard_is_unreachable`,
`etc_is_case_type`, `etc_classify_case_literal`, `etc_case_literal_key`, `etc_case_const_value_key`,
`etc_eval_case_const_value`, `etc_case_arm_is_aggregate_const`.

#### `expr_types/state.l1`

Retain analysis contexts, diagnostics and explicit scoped type/liveness state; wrappers preserve caller ownership
contracts.

Functions: `etc_diag_error`, `etc_diag_warn`, `etc_key`, `etc_set_expr_type`, `etc_pattern_var_key`,
`etc_set_pattern_var_type`, `etc_get_pattern_var_type`, `etc_set_var_res`, `etc_set_intrinsic_target`,
`etc_cleanup_header_guard_stack_free`, `etc_type_free_opt`.

#### `expr_types/stmt.l1`

Represent inline cleanup overrides with the existing StmtFlowKind domain. Preserve reverse cleanup order, first
terminating inline cleanup, separate cleanup precedence, reachability diagnostics and liveness restoration.

Functions: `etc_check_update_from_backedge_states`, `etc_check_loop_iteration`, `etc_loop_liveness_fixed_point`,
`etc_assignment_const_target_name`, `etc_const_bool_flow_eval`, `etc_const_bool_flow`, `etc_check_dead_const_stmt`,
`etc_check_dead_const_loop_parts`, `etc_check_stmt`, `etc_check_function`, `etc_check_top_level_initializers`.

### Tranche 4: Module interfaces and frontend integration

#### `analysis.l1`

Retain driver/resolver/signature/type pass ordering and result ownership. Early diagnostic exits preserve frontend
output and avoid partially initialized pass state.

Functions: `analysis_analyze_driver_state`, `analysis_analyze_entry`, `analysis_analyze_entry_with_resolution`,
`analysis_analyze_entry_with_interfaces`, `analysis_emit_interface`.

#### `driver.l1`

Retain the public driver entrypoint, configuration lifetime and shared resolution wrapper.

Functions: `driver_analyze_entry`, `driver_analyze_entry_with_resolution`, `driver_analyze_entry_with_interfaces`.

#### `driver/resolve.l1`

Retain source/interface loading, path validation, module-identity diagnostics and queued import traversal. Resolution
can add modules dynamically; fixed collections are unsuitable.

Functions: `dr_copy_parse_diags`, `dr_fail_without_node`, `dr_fail_interface`, `dr_validate_interface_roots`,
`dr_copy_interface_diags`, `dr_format_cycle`, `dr_parse_source`, `dr_resolve_interface_dependencies`,
`dr_resolve_module`, `dr_normalize_graph_interfaces`, `dr_activate_graph_interfaces`, `dr_analyze_entry_core`.

#### `driver/state.l1`

Retain owned module graph/results, source origins, interface roles and dependency metadata. Parsed AST arenas outlive
all borrowed declaration references.

Functions: `dr_unit_free`, `dr_units_free`, `dr_interfaces_free`, `driver_state_free`, `driver_has_errors`,
`driver_diag_count`, `driver_diag_get`, `driver_unit_count`, `driver_unit_get`, `driver_graph`,
`driver_interface_count`, `driver_interface_get`, `dr_interface_func_key`, `dr_register_unit`,
`dr_register_graph_interface`, `dr_register_interface`, `dr_register_projection_interface`, `driver_find_unit`,
`driver_find_interface`, `driver_find_graph_interface`, `driver_provider_fingerprint`,
`driver_find_projection_interface`, `driver_find_interface_func`, `driver_clone_interface_func_param_names`,
`driver_module_names_sorted`, `dr_emit_error`, `dr_state_create`, `dr_build_interface_candidates`, `dr_add_graph_node`.

#### `interface_emitter.l1`

Retain projection before canonical emission, escaping, ordered declarations and operational records. Text builders own
transient output; layout is part of the interface contract.

Functions: `ie_format_type`, `ie_emit_struct`, `ie_emit_enum`, `ie_emit_alias`, `ie_emit_func`, `ie_emit_const`,
`ie_emit_let`, `ie_emit_dep`, `ie_emit_module_import`, `ie_dep_sort_key`, `ie_find_dep_by_key`, `ie_collect_dep_keys`,
`ie_collect_dep_keys_excluding`, `ie_emit`.

#### `interface_fingerprint.l1`

Make the fixed domain string const. Retain checked measurement, preorder encoding plans and the SipHash native bridge.
The fixed byte buffer follows a C pointer/length ABI; array substitution alone would not remove that bridge.

Functions: `ifp_error`, `ifp_invalid`, `ifp_invalid_size`, `ifp_frame`, `ifp_append_atom_prefix`, `ifp_append_atom`,
`ifp_bool`, `ifp_checked_size_add`, `ifp_framed_size`, `ifp_add_string_atom_size`, `ifp_add_nested_atom_size`,
`ifp_finish_type_node`, `ifp_push_measure_frame`, `ifp_measure_child_count`, `ifp_measure_child`, `ifp_measure_type`,
`ifp_free_type_plan`, `ifp_plan_type`, `ifp_emit_planned_type`, `ifp_append_type_atom`, `ifp_add_name`,
`ifp_validate_surface`, `ifp_struct_record`, `ifp_enum_record`, `ifp_alias_record`, `ifp_func_record`, `ifp_let_record`,
`ifp_append_record`, `ifp_record_for_ref`, `ifp_canonicalize`, `ifp_hash_canonical_bytes`, `ifp_compute`,
`ifp_assign_computed`, `ifp_assign`, `ifp_algorithm_char`, `ifp_lower_hex`, `ifp_validate_value`,
`ifp_validate_provider_expectation`, `ifp_validate_dependencies`, `ifp_verify_computed`, `ifp_verify`.

#### `interface_literal.l1`

Remove the forwarding-only plain-string equality helper and compare the unwrapped canonical value directly. Retain
canonical scalar/aggregate spelling, exact literal reparsing and full-token rejection of recovery/trailing tokens. The
anonymous cast retains the optional owner until return; no named unwrap alias is introduced. An isolated owned-result
equality probe passed under both stages with identical 1,687 trace events, zero errors/warnings and zero leaked
pointers.

Functions: `il_format_int`, `il_format_byte`, `il_format_bool`, `il_format_string`, `il_cursor_peek`, `il_cursor_check`,
`il_cursor_match`, `il_cursor_ident`, `il_tokens_have_error`, `il_format_split_negative`, `il_parse_call`,
`il_parse_array`, `il_parse_named`, `il_parse_literal`, `il_canonicalize_literal`, `il_plain_equals`,
`il_literal_is_canonical`.

#### `interface_order.l1`

Use native string `<=` for stable name ordering after declaration-kind order. Retain stable merge sorting and dynamic
scratch storage; equal keys must retain input order.

Functions: `io_push_ref`, `io_ref_before_or_equal`, `io_set_ref`, `io_sort_refs`, `io_collect_declarations`,
`io_free_declarations`.

#### `interface_projection.l1`

Retain export/dependency closure, alias expansion rules and provider identity. Raw, semantic and projected interfaces
are distinct owned models; collapsing clones would mutate fingerprint inputs.

Functions: `mi_ice_string`, `mi_var_ref_name`, `mi_resolved_var_ref_name`, `mi_expr_is_const_cast`,
`mi_format_checked_bigint`, `mi_format_const_value`, `mi_format_literal_in`, `mi_format_literal`, `mi_has_dep`,
`mi_add_dep`, `mi_add_symbol_dep`, `mi_collect_type_refs`, `mi_collect_public_type_ref_in`,
`mi_collect_public_type_ref`, `mi_collect_value_refs`, `mi_collect_value_refs_for`, `mi_collect_param_names`,
`analysis_module_entry_type`, `mi_project_module_imports`, `mi_project_surface`, `mi_cached_provider_fingerprint`,
`mi_compute_provider_fingerprint`, `mi_provider_fingerprint_cached`, `mi_populate_dependency_fingerprints`,
`mi_populate_module_import_fingerprints`, `mi_populate_provider_fingerprints`, `mi_project`.

#### `mi_utils.l1`

Retain constructors, deep clones and destructor helpers for all interface entry kinds. Child type/metadata ownership is
not interchangeable with shallow slice views.

Functions: `miu_clone_struct_info`, `miu_clone_enum_info`, `miu_clone_dep_entry`, `miu_clone_module_import`,
`miu_clone_func_entry`, `miu_clone_let_entry`, `miu_clone_alias_entry`, `miu_clone_interface`, `miu_build_alias_map`,
`miu_find_local_alias`, `miu_replace_nominal_type`, `miu_resolve_alias_refs_in_type`,
`miu_resolve_interface_alias_refs`, `mi_func_entry_free`, `mi_let_entry_free`, `mi_alias_entry_free`,
`mi_dep_entry_free`, `mi_module_import_free`, `mi_module_import_vec_free`, `mi_free`, `ipr_has_errors`, `ipr_free`.

#### `module_interface.l1`

Retain interface records and enum declarations (no function bodies). Operational dependency ordering and exported
payload models are shared by parse, projection, fingerprint and emission.

Coverage: all record/enum fields and their ownership contracts; no function bodies.

#### `parser/interface.l1`

Retain strict monotonic operational regions, duplicate/group diagnostics and ownership transfer. Normalize only after a
successful complete parse.

Functions: `pi_parse_interface_with_peers`, `pi_parse_interface`.

#### `parser/interface/header.l1`

Retain exact header/dependency grammar, shared parser teardown and synchronization. The result adapter consumes
source-parser failures without retaining AST arenas.

Functions: `pi_destroy_state`, `pi_result_from_impl`, `pi_check_ident_text`, `pi_expect_string`, `pi_parse_dep_line`,
`pi_parse_entry_line`, `pi_parse_module_import_line`, `pi_operational_error`, `pi_parse_header`,
`pi_sync_to_semi_or_rbrace`.

#### `parser/interface/declarations.l1`

Retain ordered declaration dispatch, canonical literal construction and resource guards on partial parse failures.
Opaque declarations, extern/unsafe functions and final variadics have distinct wire grammar.

Functions: `pi_parse_call_literal`, `pi_parse_array_literal`, `pi_parse_literal`, `pi_register_decl_name`,
`pi_parse_struct_decl`, `pi_parse_opaque_struct_decl`, `pi_parse_enum_decl`, `pi_parse_opaque_enum_decl`,
`pi_parse_alias_decl`, `pi_parse_func_decl`, `pi_parse_const_decl`, `pi_parse_let_decl`, `pi_parse_one_decl`,
`pi_decl_group`.

#### `parser/interface/normalize.l1`

Retain local-before-peer-before-source nominal classification and recursive type traversal. Alias expansion belongs to
later semantic materialization, not wire parsing.

Functions: `pi_has_struct`, `pi_has_enum`, `pi_normalize_against_peers`, `pi_source_has_enum`, `pi_source_has_struct`,
`pi_normalize_against_sources`, `pi_normalize_type_with_sources`, `pi_normalize_type`,
`pi_normalize_interface_types_with_sources`, `pi_normalize_interface_types`.

#### `parser/interface/types.l1`

Retain lowering from shared TypeRef syntax, owned function parameter/result transfer and ordered suffix application.
Unsupported qualified/null type forms retain their exact diagnostics.

Functions: `pi_type_free_opt`, `pi_field_info_vec_free`, `pi_variant_info_vec_free`, `pi_is_type_start`,
`pi_module_path_text`, `pi_apply_type_ref_suffix`, `pi_type_from_ref`, `pi_parse_type`.

## Retained constraints and L2 observations

- Dynamic heterogeneous tables still use typed wrappers around `VectorBase*` and `void*` payloads. Examples include
  interface entries, signature field metadata and scope bindings. Their cost is explicit casts and paired destruction;
  existing arrays/slices do not provide generic owned containers.
- AST arena IDs and parallel semantic maps remain intentional. The model provides stable identities across passes and
  owns nodes centrally; direct pointers would change lifetime and snapshot assumptions.
- Const evaluation intentionally uses a checked signed-int subset even though L1 supports native bitwise operators.
  Operator availability does not justify broadening accepted compile-time expressions.
- Native preparation and SipHash bridges serve ABI/portability contracts. L1 syntax improvements do not eliminate their
  C support requirements.

These are implementation observations, not accepted language proposals. No external follow-up is required for the
reviewed Phase 2 implementation.

[ledger]: review.md
[measurements]: phase2-measurements.json
