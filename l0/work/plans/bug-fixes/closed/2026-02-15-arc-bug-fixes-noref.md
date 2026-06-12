# Bug Fix Plan

## ARC leaks for temporaries and discarded results

- Date: 2026-02-14
- Status: Closed (fixed)
- Title: Fix ARC leaks for temporaries and discarded results in Stage 1 backend
- Kind: Bug Fix
- Severity: High (leaks + double-free)
- Stage: 1
- Subsystem: Backend Codegen
- Modules: `compiler/stage1_py/l0_backend.py`, `compiler/stage1_py/tests/test_l0_codegen_semantics.py`

## Summary

Two bugs in the Stage 1 backend cause ARC leaks for temporary values that are not assigned to named variables:

1. **Discarded expression results leak**: `concat_s("a", "b");` as an `ExprStmt` — the fresh string is never released.
2. **Nested call temporaries leak**: `f(concat_s("a", "b"))` — the inner call produces a fresh string passed as a
   borrow; after `f()` returns, it's never released.

Both stem from the same gap: the backend only tracks ownership for named bindings (`let` variables), not anonymous
rvalues.

A third bug exists around parameter reassignment:

3. **Param reassignment double-free + leak**: `s = "new"` on a borrowed ARC param releases the caller's value
   (double-free) and never releases the new value (leak).

## Files to modify

- `compiler/stage1_py/l0_backend.py` — main changes
- `compiler/stage1_py/tests/test_l0_codegen_semantics.py` — regression tests

## Approach

### A. Helper: `_materialize_arc_temp(c_expr, expr_type) -> str`

New method in the backend (~5 lines). Given a C expression string and its L0 type:

1. `temp = self.emitter.fresh_tmp("arc")`
2. `self.emitter.emit_temp_decl(self.emitter.emit_type(expr_type), temp, c_expr)`
3. `self._current_scope.add_owned(temp, expr_type)`
4. Return `temp`

The existing scope-exit cleanup will release it automatically. Follows the match-scrutinee precedent at lines 1337-1340.

### B. Fix ExprStmt

After emitting the expression, check if it's a non-place rvalue returning an ARC type. If so, materialize it into a
scope-owned temp instead of emitting as a bare `expr;`:

```python
elif isinstance(stmt, ExprStmt):
c_expr = self._emit_expr(stmt.expr, is_statement=True)
if c_expr:
    expr_ty = self.analysis.expr_types.get(id(stmt.expr))
    if (expr_ty and self.analysis.has_arc_data(expr_ty)
            and not self._is_place_expr(stmt.expr)):
        self._materialize_arc_temp(c_expr, expr_ty)
    else:
        self.emitter.emit_expr_stmt(c_expr)
return None
```

### C. Fix nested call arguments (lines 2099-2105)

When emitting arguments for a `CallExpr`, if an argument is a non-place expression whose **natural type** has ARC data,
materialize it into a temp before passing:

```python
# In the CallExpr branch, replace the inline arg emission:
c_arg_parts = []
for a, p in zip(expr.args, func_ty.params):
    c_a = self._emit_expr_with_expected_type(a, p)
    a_ty = self.analysis.expr_types.get(id(a))
    if (a_ty and self.analysis.has_arc_data(a_ty)
            and not self._is_place_expr(a)):
        c_a = self._materialize_arc_temp(c_a, a_ty)
    c_arg_parts.append(c_a)
c_args = ", ".join(c_arg_parts)
```

Also apply to the fallback path (line 2105) and complex-callee path (line 2112).

### D. Tests for leak fixes

Add to `compiler/stage1_py/tests/test_l0_codegen_semantics.py`, following the pattern of the existing
`test_codegen_return_from_field_place_expr_retains` (line 362).

**New leak-fix tests:**

1. `test_codegen_discarded_arc_call_released` — `concat_s("a","b");` as ExprStmt → emitted C has a temp +
   `rt_string_release`
2. `test_codegen_nested_arc_call_temps_released` — `let x = concat_s("hello", concat_s(", ", "world"));` → inner temp
   released; compile+run to confirm no leak (valgrind-style verification via refcount correctness)
3. `test_codegen_discarded_struct_with_arc_call` — if applicable: call returning struct-with-string field, discarded

**Regression tests for return-from-borrow ownership:**

4. `test_codegen_return_borrowed_param_retains` — `func id_s(s: string) -> string { return s; }` → verify
   `rt_string_retain` in `id_s` body; compile+run with `let x = id_s(some_string); printl_s(x); printl_s(some_string);`
   to confirm both are valid
5. `test_codegen_return_borrowed_param_with_cleanup` — same but with other owned locals in the function, forcing the
   `needs_cleanup` path (line 1012-1022) to exercise the `__ret_N` temp + cleanup-before-return sequence
6. `test_codegen_return_borrowed_param_no_move` — verify that `_lookup_owned_local_name` returns `None` for a param by
   checking the emitted C does NOT use the move-return path (i.e., retain IS present)

### E. Fix param reassignment of borrowed ARC values (lines 1143-1169)

**Bug**: `_emit_reassignment` on a borrowed ARC param (1) releases the caller's value (double-free) and (2) never
releases the new value at scope exit (leak).

**New helper: `_find_declaring_scope(mangled_name) -> Optional[ScopeContext]`** Walk the scope chain; return the scope
whose `declared_vars` contains the name, or `None`.

**New helper: `_is_borrowed_arc_param(target_expr, dst_ty) -> (bool, Optional[ScopeContext])`** Returns True + declaring
scope when: target is a `VarRef`, `has_arc_data(dst_ty)`, the mangled name is in `declared_vars` but NOT in `owned_vars`
anywhere in the scope chain.

**In `_emit_reassignment`**, when `has_arc_data(dst_ty)` and target is a borrowed ARC param:

1. **Skip** `_emit_value_cleanup(c_target, dst_ty)` — old value is borrowed, not ours to release
2. **Promote** param to `declaring_scope.add_owned(mangled, dst_ty)` — so scope-exit cleanup releases the new value
3. Emit the assignment as normal

Subsequent reassignments will find the param already in `owned_vars` → normal release-old + assign-new path.

**Critical**: promote on the **declaring (function) scope**, not `_current_scope`, to avoid premature release when
reassignment happens inside a nested block.

### F. Tests for param reassignment

7. `test_codegen_param_reassign_no_double_free` — `func f(s: string) { s = "new"; }` called with an owned string →
   verify no release of old borrowed value, verify new value released at scope exit
8. `test_codegen_param_reassign_in_nested_scope` — reassignment inside `if` body → verify param released at function
   exit, not inner scope exit
9. `test_codegen_param_reassign_twice` — two reassignments → first skips release, second releases the first new value

## Verification

```bash
cd compiler/stage1_py
pytest -n 3                              # full suite
pytest -k "test_codegen"                 # codegen tests
./l0c -P examples gen <test_file>        # inspect emitted C for correct retain/release
```
