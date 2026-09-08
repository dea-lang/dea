# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from l0_analysis import VarRefResolution
from l0_ast import Expr, IntLiteral, StringLiteral, BoolLiteral, NullLiteral, VarRef, UnaryOp, BinaryOp, CallExpr, IndexExpr, FieldAccessExpr, ParenExpr, CastExpr, TryExpr, TypeExpr, NewExpr, ByteLiteral
from l0_resolve import resolve_symbol, ResolveErrorKind
from l0_symbols import SymbolKind, Symbol
from l0_types import Type, FuncType, BuiltinType, StructType, EnumType, PointerType, NullableType, NullType, format_type
from l0_check_compat import TypeCompatibility
from l0_check_liveness import ExpressionLiveness
from l0_check_lookup import SemanticLookup
from l0_check_state import CheckerState


@dataclass
class ExpressionInference:
    """Mutually recursive expression inference over explicit semantic dependencies."""

    compat: TypeCompatibility
    liveness: ExpressionLiveness
    lookup: SemanticLookup
    state: CheckerState

    def _infer_type_expr(self, expr: TypeExpr) -> Type | None:
        """TypeExpr is only valid as an argument to type-accepting intrinsics."""
        self.state._error(expr,
                    "[TYP-0290] type expression is only valid as argument to type-accepting intrinsics such as 'sizeof'")
        return None

    def _infer_expr(self, expr: Expr | None, *,
                    widening_type: Type | None = None,
                    context_code: str = "TYP-0319",
                    context_descriptor: str = "expression") -> Type | None:
        """Infer the type of an expression.

        Args:
            expr: The expression to type-check.
            widening_type: Optional expected type for context-sensitive checking.
            context_code: Diagnostic code for type mismatch.
            context_descriptor: Description of context for diagnostic.

        Returns:
            The resolved Type of the expression, or None on error.
        """
        if expr is None:
            return self.state._error(Expr(), "[TYP-0149] cannot infer type of None expression")

        existing = self.state.expr_types.get(id(expr))
        if self.state._liveness_diagnostics_only:
            self.liveness._check_expr_liveness(expr)
            return existing
        if existing is not None:
            return existing

        result: Type | None

        match expr:
            case IntLiteral():
                result = self.state.int_type

            case ByteLiteral():
                result = self.state.byte_type

            case StringLiteral():
                result = self.state.string_type

            case BoolLiteral():
                result = self.state.bool_type

            case NullLiteral():
                result = self.state.null_type

            case VarRef():
                result = self._infer_var_ref(expr)

            case UnaryOp():
                result = self._infer_unary(expr)

            case BinaryOp():
                result = self._infer_binary(expr)

            case CallExpr():
                result = self._infer_call(expr)

            case IndexExpr():
                result = self._infer_index(expr)

            case FieldAccessExpr():
                result = self._infer_field_access(expr)

            case ParenExpr(inner=inner):
                result = self._infer_expr(inner)

            case CastExpr():
                result = self._infer_cast(expr)

            case NewExpr():
                result = self._infer_new(expr)

            case TypeExpr():
                return self._infer_type_expr(expr)

            case TryExpr():
                result = self._infer_try(expr)

            case _:
                result = None

        if result is not None and not self.state._liveness_diagnostics_only:
            self.state.expr_types[id(expr)] = result  # Always store natural type

        if result is not None and widening_type is not None:
            # Check widening if provided from context
            # (e.g., assignment target, struct field, function arg, etc.)
            if not self.compat._can_assign(widening_type, result):
                return self.state._error(
                    expr,
                    f"[{context_code}] {context_descriptor} type mismatch: "
                    f"expected '{format_type(widening_type)}', got '{format_type(result)}'",
                )

        return result

    def _infer_var_ref(self, expr: VarRef) -> Type | None:
        """Infer type for a variable reference."""
        # Reject overqualified names early (e.g. color::Color::Red)
        if self.lookup._reject_name_qualifier(expr, expr.name, expr.name_qualifier, expr.module_path):
            return None

        # 1. Locals / parameters
        if expr.module_path is None:
            local_scope_idx = self.lookup._lookup_local_scope_index(expr.name)
            if local_scope_idx is not None:
                local_ty = self.state._local_scopes[local_scope_idx][expr.name]
                self.state._store_var_resolution(expr, VarRefResolution.LOCAL)
                if self.state._is_guarded_cleanup_header_ref(expr.name, local_scope_idx):
                    self.state._error(
                        expr,
                        f"[TYP-0156] 'cleanup' block references 'with' header variable '{expr.name}' "
                        f"that may be uninitialized on '?' header-failure path; "
                        f"use nullable type or inline '=>' cleanup"
                    )
                alive = self.state._lookup_alive(expr.name)
                if alive is False:
                    self.state._error(expr, f"[TYP-0150] use of dropped variable '{expr.name}'")
                return local_ty

        # 2. Module-level symbols (functions only, for now)
        assert self.state._current_func_env is not None
        module_name = self.state._current_func_env.module_name

        sym_result = resolve_symbol(self.state.module_envs, module_name, expr.name, module_path=expr.module_path)
        sym = sym_result.symbol
        if sym is None:
            qualified_name = (
                f"{'.'.join(expr.module_path)}::{expr.name}"
                if expr.module_path
                else expr.name
            )
            if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                self.state._error(
                    expr,
                    f"[TYP-0153] unknown identifier '{qualified_name}' (unknown module '{sym_result.module_name}')",
                )
            elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
                self.state._error(
                    expr,
                    f"[TYP-0154] unknown identifier '{qualified_name}' (module '{sym_result.module_name}' not imported)",
                )
            elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{expr.name}'" for m in sym_result.ambiguous_modules)
                self.state._error(
                    expr,
                    f"[TYP-0155] ambiguous identifier '{expr.name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
            else:
                self.state._error(expr, f"[TYP-0159] unknown identifier '{qualified_name}'")
            return None

        if sym.kind is SymbolKind.FUNC and sym.type is not None:
            # Functions have a FuncType
            self.state._store_var_resolution(expr, VarRefResolution.MODULE)
            return sym.type

        if sym.kind is SymbolKind.LET and sym.type is not None:
            # Top-level let bindings have their resolved type
            self.state._store_var_resolution(expr, VarRefResolution.MODULE)
            return sym.type

        # Zero-arg enum variants can be used as bare identifiers (e.g. `Red` instead of `Red()`).
        if sym.kind is SymbolKind.ENUM_VARIANT and isinstance(sym.type, FuncType):
            self.state._store_var_resolution(expr, VarRefResolution.MODULE)
            variant_type = sym.type
            if len(variant_type.params) == 0:
                enum_type = variant_type.result
                if isinstance(enum_type, EnumType):
                    return enum_type
            # Variant has payload fields — bare usage is an error.
            self.state._error(
                expr,
                f"[TYP-0152] variant '{expr.name}' requires arguments; use '{expr.name}(...)' constructor syntax",
            )
            return None

        # Struct, enum, and other type symbols are not values by themselves.
        self.state._error(expr, f"[TYP-0151] symbol '{expr.name}' is not a value")
        return None

    def _infer_unary(self, expr: UnaryOp) -> Type | None:
        """Infer type for a unary operation."""
        op = expr.op
        operand_ty = self._infer_expr(expr.operand)

        # Unary minus: int -> int
        if op == "-":
            if self.compat._is_int_assignable(operand_ty):
                return self.state.int_type
            if operand_ty is not None:
                self.state._error(
                    expr,
                    f"[TYP-0160] unary '-' expects operand of type 'int', got '{format_type(operand_ty)}'",
                )
            return None

        # Logical not: bool -> bool
        if op == "!":
            if self.compat._is_bool(operand_ty):
                return self.state.bool_type
            if operand_ty is not None:
                self.state._error(
                    expr,
                    f"[TYP-0161] unary '!' expects operand of type 'bool', got '{format_type(operand_ty)}'",
                )
            return None

        # Dereference: T* -> T
        if op == "*":
            if isinstance(operand_ty, PointerType):
                return operand_ty.inner
            if operand_ty is not None:
                self.state._error(
                    expr,
                    f"[TYP-0162] cannot dereference expression of type '{format_type(operand_ty)}'; "
                    "expected a pointer type",
                )
            return None

        return operand_ty

    def _infer_binary(self, expr: BinaryOp) -> Type | None:
        """Infer type for a binary operation."""
        op = expr.op
        left_ty = self._infer_expr(expr.left)
        right_ty = self._infer_expr(expr.right)

        # string + string -> string
        if op == "+" and self.compat._is_string(left_ty) and self.compat._is_string(right_ty):
            return self.state.string_type

        # Arithmetic int ops -> int
        if op in {"+", "-", "*", "/", "%"}:
            return self._binary_expect_both_int(expr, left_ty, right_ty, result=self.state.int_type)

        # Comparison ops -> bool. Accept ints (existing) or two strings (lexicographic).
        if op in {"<", "<=", ">", ">="}:
            if self.compat._is_string(left_ty) and self.compat._is_string(right_ty):
                return self.state.bool_type
            return self._binary_expect_both_int(expr, left_ty, right_ty, result=self.state.bool_type)

        # Equality: same-type operands OR null check -> bool
        if op in {"==", "!="}:
            return self._binary_equality(expr, left_ty, right_ty)

        # Logical bool ops -> bool
        if op in {"&&", "||"}:
            return self._binary_expect_both_bool(expr, left_ty, right_ty, result=self.state.bool_type)

        # Future: bitwise, etc.

        return None

    def _binary_expect_both_int(
            self, expr: BinaryOp, left: Type | None, right: Type | None, result: Type | None
    ) -> Type | None:
        """Check that both operands of a binary op are int-assignable."""
        if self.compat._is_int_assignable(left) and self.compat._is_int_assignable(right):
            return result
        if left is not None and right is not None:
            self.state._error(
                expr,
                f"[TYP-0170] operator '{expr.op}' expects operands of type 'int', got "
                f"'{format_type(left)}' and '{format_type(right)}'",
            )
        return None

    def _binary_expect_both_bool(
            self, expr: BinaryOp, left: Type | None, right: Type | None, result: Type | None
    ) -> Type | None:
        """Check that both operands of a binary op are bool."""
        if self.compat._is_bool(left) and self.compat._is_bool(right):
            return result
        if left is not None and right is not None:
            self.state._error(
                expr,
                f"[TYP-0171] operator '{expr.op}' expects operands of type 'bool', got "
                f"'{format_type(left)}' and '{format_type(right)}'",
            )
        return None

    def _binary_equality(
            self, expr: BinaryOp, left: Type | None, right: Type | None
    ) -> Type | None:
        """Infer type for equality/inequality comparison."""
        if left is None or right is None:
            return None

        # Check for null comparison: One side is NullType, other is Nullable/Ptr
        is_null_check = (
                (isinstance(left, NullType) and self.compat._is_nullable_or_ptr(right)) or
                (isinstance(right, NullType) and self.compat._is_nullable_or_ptr(left))
        )

        # If it's not a null check, enforce both sides have the same type (or compatible)
        if not is_null_check and not (self.compat._can_assign(right, left) or self.compat._can_assign(left, right)):
            self.state._error(
                expr,
                f"[TYP-0172] equality operator '{expr.op}' requires both operands to have the "
                f"same type (or be a valid null check), got '{format_type(left)}' and '{format_type(right)}'",
            )
            return None

        # Restrict what types can be compared for equality (int, bool, string).
        if not is_null_check and not (
                self.compat._is_int_assignable(left) or self.compat._is_bool(left) or self.compat._is_string(left)
        ):
            self.state._error(
                expr,
                f"[TYP-0173] equality not supported for type '{format_type(left)}'",
            )
            return None

        return self.state.bool_type

    def _try_infer_intrinsic(self, expr: CallExpr) -> Type | None:
        """Handle compiler intrinsics calls."""
        if not isinstance(expr.callee, VarRef):
            return None

        name = expr.callee.name

        if name == "sizeof":
            return self._infer_sizeof_intrinsic(expr)

        if name == "ord":
            return self._infer_ord_intrinsic(expr)

        # Not an intrinsic
        return None

    def _infer_sizeof_intrinsic(self, expr: CallExpr) -> Type:
        """Handle sizeof(T) or sizeof(expr) intrinsic."""
        if len(expr.args) != 1:
            self.state._error(expr, "[TYP-0241] sizeof expects exactly 1 argument")
            return self.state.int_type

        arg = expr.args[0]

        if isinstance(arg, TypeExpr):
            # sizeof(T) - direct type argument
            target_ty = self.lookup._resolve_type_ref(arg.type_ref)
            if target_ty is None:
                return self.state.int_type
            if self.compat._is_void(target_ty):
                self.state._error(expr, "[TYP-0240] cannot take sizeof(void)")
            # Store resolved type for codegen
            self.state._store_sizeof_target(expr, target_ty)
            return self.state.int_type

        if isinstance(arg, VarRef):
            # Could be sizeof(TypeName) or sizeof(variable)
            # Try resolving as type first
            target_ty = self.lookup._try_resolve_type_name(arg.name, node=arg, module_path=arg.module_path)
            if target_ty is not None:
                if self.compat._is_void(target_ty):
                    self.state._error(expr, "[TYP-0240] cannot take sizeof(void)")
                self.state._store_sizeof_target(expr, target_ty)
                return self.state.int_type

            # Fall through to treat as expression

        # sizeof(expr) - use expression's type
        arg_ty = self._infer_expr(arg)
        if arg_ty is None:
            return self.state.int_type
        if self.compat._is_void(arg_ty):
            self.state._error(expr, "[TYP-0240] cannot take sizeof(void)")
        self.state._store_sizeof_target(expr, arg_ty)
        return self.state.int_type

    def _infer_ord_intrinsic(self, expr: CallExpr) -> Type:
        """Handle ord(enum_value) intrinsic - returns 0-based ordinal of enum variant."""
        if len(expr.args) != 1:
            self.state._error(expr, "[TYP-0242] ord expects exactly 1 argument")
            return self.state.int_type

        arg = expr.args[0]
        arg_ty = self._infer_expr(arg)

        if arg_ty is None:
            return self.state.int_type

        if not isinstance(arg_ty, EnumType):
            self.state._error(expr, f"[TYP-0243] ord expects an enum value, got '{format_type(arg_ty)}'")
            return self.state.int_type

        return self.state.int_type

    def _infer_call(self, expr: CallExpr) -> Type | None:
        """Infer type for a function or constructor call."""
        # Check for intrinsic calls first
        if isinstance(expr.callee, VarRef):
            intrinsic_result = self._try_infer_intrinsic(expr)
            if intrinsic_result is not None:
                return intrinsic_result

        # Only allow calling plain identifiers.
        if not isinstance(expr.callee, VarRef):
            self.state._error(expr, "[TYP-0180] callee must be a function name")
            # Still traverse arguments to type-check them.
            for arg in expr.args:
                self._infer_expr(arg)
            return None

        # Reject overqualified callee names early (e.g. color::Color::Red(...))
        if isinstance(expr.callee, VarRef) and self.lookup._reject_name_qualifier(
                expr, expr.callee.name, expr.callee.name_qualifier, expr.callee.module_path
        ):
            return None

        assert self.state._current_func_env is not None
        module_name = self.state._current_func_env.module_name

        sym_result = resolve_symbol(self.state.module_envs, module_name, expr.callee.name,
                                    module_path=expr.callee.module_path)
        sym = sym_result.symbol
        if sym is None:
            qualified_name = (
                f"{'.'.join(expr.callee.module_path)}::{expr.callee.name}"
                if expr.callee.module_path
                else expr.callee.name
            )
            if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                self.state._error(
                    expr,
                    f"[TYP-0189] unknown identifier '{qualified_name}' (unknown module '{sym_result.module_name}')",
                )
            elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
                self.state._error(
                    expr,
                    f"[TYP-0189] unknown identifier '{qualified_name}' (module '{sym_result.module_name}' not imported)",
                )
            elif sym_result.error is ResolveErrorKind.AMBIGUOUS_SYMBOL:
                modules_str = "', '".join(sym_result.ambiguous_modules)
                hints = " or ".join(f"'{m}::{expr.callee.name}'" for m in sym_result.ambiguous_modules)
                self.state._error(
                    expr,
                    f"[TYP-0189] ambiguous identifier '{expr.callee.name}' (imported from modules '{modules_str}'); "
                    f"use {hints} to disambiguate",
                )
            else:
                self.state._error(expr, f"[TYP-0189] unknown identifier '{qualified_name}'")
            return None

        # Handle struct constructors or type-alias-to-struct constructors
        if sym.kind is SymbolKind.STRUCT or (sym.kind is SymbolKind.TYPE_ALIAS and isinstance(sym.type, StructType)):
            return self._infer_struct_constructor(expr, sym)

        # Handle enum variant constructors
        if sym.kind is SymbolKind.ENUM_VARIANT:
            return self._infer_variant_constructor(expr, sym)

        # Handle regular function calls
        if sym.kind is not SymbolKind.FUNC:
            self.state._error(expr, f"[TYP-0181] symbol '{expr.callee.name}' is not callable")
            return None

        callee_ty = sym.type
        if not isinstance(callee_ty, FuncType):
            if callee_ty is not None:
                self.state._error(expr, "[TYP-0182] callee is not a function")
            return None

        # Arity check
        expected_arity = len(callee_ty.params)
        given_arity = len(expr.args)
        if expected_arity != given_arity:
            self.state._error(
                expr,
                f"[TYP-0183] function call has wrong number of arguments: "
                f"expected {expected_arity}, got {given_arity}",
            )

        # Type-check arguments
        for index, arg in enumerate(expr.args):
            if index < len(callee_ty.params):
                param_ty = callee_ty.params[index]
                self._infer_expr(arg, widening_type=param_ty,
                                 context_code="TYP-0312",
                                 context_descriptor=f"argument {index + 1} to function '{expr.callee.name}'")
        return callee_ty.result

    def _infer_struct_constructor(self, expr: CallExpr, sym: Symbol) -> Type | None:
        """Infer type for a struct constructor call."""
        assert isinstance(expr.callee, VarRef)
        if sym.kind is SymbolKind.TYPE_ALIAS and isinstance(sym.type, StructType):
            # Type alias to struct
            struct_type = sym.type
            module_name = struct_type.module
            struct_name = struct_type.name
        else:
            # Direct struct
            module_name = sym.module.name
            struct_name = expr.callee.name
            struct_type = StructType(module_name, struct_name)

        # Look up struct info to get field types
        info = self.state.struct_infos.get((module_name, struct_name))
        if info is None:
            self.state._error(expr, f"[TYP-0190] no type information for struct '{struct_name}'")
            return None

        # Arity check
        expected_arity = len(info.fields)
        given_arity = len(expr.args)
        if expected_arity != given_arity:
            self.state._error(
                expr,
                f"[TYP-0191] struct constructor '{struct_name}' expects {expected_arity} "
                f"argument(s), got {given_arity}",
            )

        # Type-check arguments against field types
        for index, arg in enumerate(expr.args):
            if index < len(info.fields):
                field_info = info.fields[index]
                self._infer_expr(arg, widening_type=field_info.type,
                                 context_code="TYP-0313",
                                 context_descriptor=f"argument {index + 1} to struct constructor '{struct_name}' for field '{field_info.name}'")

        return struct_type

    def _infer_variant_constructor(self, expr: CallExpr, sym: Symbol) -> Type | None:
        """Infer type for an enum variant constructor call."""
        assert isinstance(expr.callee, VarRef)
        variant_name = expr.callee.name

        # The variant's type should be a FuncType: (payload...) -> EnumType
        # This was set by SignatureResolver
        if not isinstance(sym.type, FuncType):
            self.state._error(expr, f"[TYP-0200] variant '{variant_name}' has no type information")
            return None

        variant_type = sym.type
        enum_type = variant_type.result

        if not isinstance(enum_type, EnumType):
            self.state._error(expr, f"[TYP-9209] internal error: variant '{variant_name}' does not produce enum type")
            return None

        # Arity check
        expected_arity = len(variant_type.params)
        given_arity = len(expr.args)
        if expected_arity != given_arity:
            self.state._error(
                expr,
                f"[TYP-0201] variant constructor '{variant_name}' expects {expected_arity} "
                f"argument(s), got {given_arity}",
            )

        # Type-check arguments against payload types
        for index, arg in enumerate(expr.args):
            if index < len(variant_type.params):
                param_ty = variant_type.params[index]
                self._infer_expr(arg,
                                 widening_type=param_ty,
                                 context_code="TYP-0314",
                                 context_descriptor=f"argument {index + 1} to variant constructor '{variant_name}'")

        return enum_type

    def _infer_index(self, expr: IndexExpr) -> Type | None:
        """Infer type for an indexing expression."""
        array_ty = self._infer_expr(expr.array)
        index_ty = self._infer_expr(expr.index)

        if index_ty is not None and not self.compat._is_int_assignable(index_ty):
            self.state._error(expr, f"[TYP-0210] index expression must have type 'int', got '{format_type(index_ty)}'")

        if isinstance(array_ty, NullableType):
            self.state._error(
                expr,
                f"[TYP-0211] cannot index into nullable type '{format_type(array_ty)}'; indexing is not yet supported",
            )
            return None

        # if isinstance(array_ty, ArrayType): # TODO Uncomment when ArrayType is defined (buffers and slices)
        #     return array_ty.inner

        if array_ty is not None:
            self.state._error(
                expr,
                f"[TYP-0212] cannot index into expression of type '{format_type(array_ty)}'; indexing is not yet supported",
            )

        return None

    def _infer_field_access(self, expr: FieldAccessExpr) -> Type | None:
        """Infer type for a field access expression."""
        obj_ty = self._infer_expr(expr.obj)

        if isinstance(obj_ty, NullableType) and isinstance(obj_ty.inner, StructType):
            self.state._error(
                expr,
                f"[TYP-0220] cannot access field '{expr.field}' on nullable struct '{format_type(obj_ty)}'; expected a non-null struct",
            )
            return None

        # Dereference pointer to struct if needed
        if isinstance(obj_ty, PointerType) and isinstance(obj_ty.inner, StructType):
            obj_ty = obj_ty.inner

        if isinstance(obj_ty, StructType):
            info = self.state.struct_infos.get((obj_ty.module, obj_ty.name))
            if info is None:
                return None

            for field_info in info.fields:
                if field_info.name == expr.field:
                    return field_info.type

            self.state._error(
                expr,
                f"[TYP-0221] struct '{format_type(obj_ty)}' has no field '{expr.field}'",
            )
            return None

        if obj_ty is not None:
            self.state._error(
                expr,
                f"[TYP-0222] cannot access field '{expr.field}' on non-struct type '{format_type(obj_ty)}'",
            )

        return None

    def _infer_cast(self, expr: CastExpr) -> Type | None:
        """Infer type for a cast expression and validate compatibility."""
        expr_ty = self._infer_expr(expr.expr)
        if expr_ty is None:
            return None

        target_ty = self.lookup._resolve_type_ref(expr.target_type)
        if target_ty is None:
            return None

        # Explicit int -> byte casts with compile-time-known values are checked in analysis.
        if (
                isinstance(expr_ty, BuiltinType)
                and expr_ty.name == "int"
                and isinstance(target_ty, BuiltinType)
                and target_ty.name == "byte"
        ):
            const_int = self.compat._get_const_int_for_explicit_cast(expr.expr)
            if const_int is not None and (const_int < 0 or const_int > 255):
                return self.state._error(
                    expr,
                    f"[TYP-0700] explicit cast from 'int' to 'byte' overflows: {const_int} is outside 0..255",
                )

        # Explicit unwrap from nullable pointer to pointer cannot be proven-null.
        if (
                isinstance(expr_ty, NullableType)
                and isinstance(expr_ty.inner, PointerType)
                and isinstance(target_ty, PointerType)
                and self.compat._types_equal(target_ty, expr_ty.inner)
                and self.compat._is_const_null_for_explicit_cast(expr.expr)
        ):
            return self.state._error(
                expr,
                f"[TYP-0701] explicit cast from '{format_type(expr_ty)}' to '{format_type(target_ty)}' is null at compile time",
            )

        # Allow the cast if the types are assignable
        if self.compat._can_assign(target_ty, expr_ty, allow_promotion=True):
            return target_ty

        return self.state._error(
            expr, f"[TYP-0230] cannot cast from '{format_type(expr_ty)}' to '{format_type(target_ty)}'"
        )

    def _infer_try(self, expr: TryExpr) -> Type | None:
        """Infer type for a '?' try operator expression."""
        if self.state._current_func_type is None:
            return None

        inner_ty = self._infer_expr(expr.expr)
        if inner_ty is None:
            return None

        if not isinstance(inner_ty, NullableType):
            self.state._error(expr, f"[TYP-0250] cannot apply '?' to non-nullable type '{format_type(inner_ty)}'")
            return None

        if not isinstance(self.state._current_func_type.result, NullableType):
            self.state._error(expr, "[TYP-0251] cannot use '?' in a function that does not return a nullable type (T?)")
            return None

        return inner_ty.inner

    def _infer_new(self, expr: NewExpr) -> Type | None:
        """Infer type for a 'new' heap allocation expression."""
        if self.state._current_func_env is None:
            return self.state._error(expr, f"[TYP-9288] internal error: 'new' outside function context")

        module_name = self.state._current_func_env.module_name
        mod_env = self.state.module_envs.get(module_name)

        if mod_env is None:
            return self.state._error(expr, f"[TYP-9289] internal error: no module env for '{module_name}'")

        base_ty = self.lookup._resolve_type_ref(expr.type_ref)

        if base_ty is None:
            # Type resolution failed - check if it's an enum variant constructor (e.g., new CaseA(42))
            sym_result = resolve_symbol(
                self.state.module_envs,
                module_name,
                expr.type_ref.name,
                module_path=expr.type_ref.module_path,
            )
            sym = sym_result.symbol
            if sym and sym.kind is SymbolKind.ENUM_VARIANT:
                enum_ty = self._infer_variant_constructor(
                    CallExpr(callee=VarRef(name=expr.type_ref.name, module_path=expr.type_ref.module_path),
                             args=expr.args),
                    sym,
                )
                return PointerType(enum_ty) if enum_ty else None
            return self.state._error(expr, f"[TYP-0280] unknown type in 'new' expression")

        if isinstance(base_ty, EnumType):
            return self.state._error(expr, f"[TYP-0281] cannot allocate enum type '{format_type(base_ty)}' without a variant")

        if isinstance(base_ty, StructType):
            info = self.state.struct_infos.get((base_ty.module, base_ty.name))
            if info is None:
                return self.state._error(expr, f"[TYP-0282] missing struct info for {base_ty.module}.{base_ty.name}")

            if len(expr.args) > 0:
                if len(expr.args) != len(info.fields):
                    self.state._error(expr,
                                f"[TYP-0283] struct '{base_ty.name}' expects {len(info.fields)} argument(s), got {len(expr.args)}")

                for field, arg in zip(info.fields, expr.args):
                    self._infer_expr(arg, widening_type=field.type,
                                     context_code="TYP-0316",
                                     context_descriptor=f"field '{field.name}' of struct '{base_ty.name}'")

        else:
            # Non-struct types (builtins, pointers, nullable): expect 0 or 1 argument
            if len(expr.args) > 1:
                self.state._error(expr,
                            f"[TYP-0285] 'new {format_type(base_ty)}' expects at most 1 argument, got {len(expr.args)}")
            elif len(expr.args) == 1:
                arg_ty = self._infer_expr(expr.args[0])
                if arg_ty is not None and not self.compat._can_assign(base_ty, arg_ty):
                    self.state._error(expr.args[0],
                                f"[TYP-0286] cannot initialize '{format_type(base_ty)}' with value of type '{format_type(arg_ty)}'")

        return PointerType(base_ty)
