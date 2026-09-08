# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass
from l0_ast import Node, MatchStmt, Expr, IntLiteral, StringLiteral, BoolLiteral, VariantPattern, WildcardPattern, ByteLiteral
from l0_resolve import resolve_symbol, ResolveErrorKind
from l0_signatures import EnumInfo
from l0_string_escape import decode_l0_string_token, EscapeDecodeError
from l0_symbols import SymbolKind
from l0_types import Type, EnumType, format_type
from l0_check_lookup import SemanticLookup
from l0_check_state import CheckerState


@dataclass
class MatchCoverage:
    """Pattern validation results shared with statement and liveness traversal."""

    defined_variants: set[str]
    validated_variant_names: list[str | None]
    covered_variants: set[str]
    wildcard_is_unreachable: bool
    reachable_arm_count: int


@dataclass
class PatternAnalysis:
    """Case literals, validated enum patterns, and match coverage diagnostics."""

    lookup: SemanticLookup
    state: CheckerState

    def _case_literal_info(self, expr: Expr) -> tuple[Type, object] | None:
        """Get type and value for a case arm literal."""
        if isinstance(expr, IntLiteral):
            return self.state.int_type, expr.value
        if isinstance(expr, ByteLiteral):
            decoded = self._decode_escaped_bytes(expr.value, expr)
            if decoded is None or len(decoded) != 1:
                return None
            value = decoded[0]
            return self.state.byte_type, value
        if isinstance(expr, BoolLiteral):
            return self.state.bool_type, expr.value
        if isinstance(expr, StringLiteral):
            decoded = self._decode_escaped_bytes(expr.value, expr)
            if decoded is None:
                return None
            return self.state.string_type, decoded
        return None

    def _decode_escaped_bytes(self, text: str, node: Node) -> bytes | None:
        """Decode a string literal, reporting errors."""
        try:
            return decode_l0_string_token(text)
        except EscapeDecodeError as err:
            if err.code == "invalid_unicode_escape":
                self.state._error(node, "[TYP-0109] invalid unicode escape in 'case' literal")
                return None
            if err.code == "unicode_out_of_range":
                self.state._error(node, "[TYP-0109] unicode escape out of range in 'case' literal")
                return None
            self.state._error(node, "[TYP-0109] invalid escape in 'case' literal")
            return None

    def _validate_match_variant_pattern(
            self,
            pattern: VariantPattern,
            scrutinee_ty: EnumType,
            enum_info: EnumInfo | None,
    ) -> str | None:
        """Validate one match variant and return its canonical enum name."""
        if self.lookup._reject_name_qualifier(
                pattern, pattern.name, pattern.name_qualifier, pattern.module_path
        ):
            return None

        if pattern.module_path is not None:
            assert self.state._current_func_env is not None
            module_name = self.state._current_func_env.module_name
            sym_result = resolve_symbol(
                self.state.module_envs,
                module_name,
                pattern.name,
                module_path=pattern.module_path,
            )
            sym = sym_result.symbol
            qualified = f"{'.'.join(pattern.module_path)}::{pattern.name}"
            if sym is None:
                if sym_result.error is ResolveErrorKind.UNKNOWN_MODULE:
                    self.state._error(
                        pattern,
                        f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'"
                        f" (unknown module '{sym_result.module_name}')",
                    )
                elif sym_result.error is ResolveErrorKind.MODULE_NOT_IMPORTED:
                    self.state._error(
                        pattern,
                        f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'"
                        f" (module '{sym_result.module_name}' not imported)",
                    )
                else:
                    self.state._error(
                        pattern,
                        f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'",
                    )
                return None
            if sym.kind is not SymbolKind.ENUM_VARIANT or sym.module.name != scrutinee_ty.module:
                self.state._error(
                    pattern,
                    f"[TYP-0102] unknown variant '{qualified}' for enum '{format_type(scrutinee_ty)}'",
                )
                return None

        if enum_info is None:
            return None
        variant_info = enum_info.variants.get(pattern.name)
        if variant_info is None:
            self.state._error(
                pattern,
                f"[TYP-0102] unknown variant '{pattern.name}' for enum '{format_type(scrutinee_ty)}'",
            )
            return None
        if len(pattern.vars) != len(variant_info.field_types):
            self.state._error(
                pattern,
                f"[TYP-0101] pattern variable count mismatch: variant '{pattern.name}' "
                f"has {len(variant_info.field_types)} fields but pattern has {len(pattern.vars)} variables",
            )
            return None
        return variant_info.name

    def _match_coverage(self, stmt: MatchStmt, scrutinee_ty: EnumType,
                        enum_info: EnumInfo | None) -> MatchCoverage:
        """Validate patterns and compute coverage before traversing arm bodies.

        Args:
            stmt: Match statement being checked.
            scrutinee_ty: Resolved enum type of the scrutinee.
            enum_info: Resolved enum metadata, when available.

        Returns:
            Validated variant names, wildcard reachability, and coverage sets.
        """
        defined_variants = set(enum_info.variants.keys()) if enum_info is not None else set()
        validated_variant_names: list[str | None] = []
        for arm in stmt.arms:
            if isinstance(arm.pattern, VariantPattern):
                validated_variant_names.append(
                    self._validate_match_variant_pattern(arm.pattern, scrutinee_ty, enum_info)
                )
            else:
                validated_variant_names.append(None)
        covered_variants = {name for name in validated_variant_names if name is not None}
        variants_before_wildcard: set[str] = set()
        for arm, validated_name in zip(stmt.arms, validated_variant_names):
            if isinstance(arm.pattern, WildcardPattern):
                break
            if validated_name is not None:
                variants_before_wildcard.add(validated_name)
        wildcard_is_unreachable = enum_info is not None and variants_before_wildcard == defined_variants
        reachable_arm_count = sum(
            not (isinstance(arm.pattern, WildcardPattern) and wildcard_is_unreachable)
            for arm in stmt.arms
        )
        return MatchCoverage(defined_variants, validated_variant_names,
                             covered_variants, wildcard_is_unreachable,
                             reachable_arm_count)

    def _check_exhaustiveness(self, stmt: MatchStmt, scrutinee_ty: EnumType,
                              coverage: MatchCoverage) -> bool:
        """Report match coverage diagnostics after checking all arm bodies.

        Args:
            stmt: Match statement being checked.
            scrutinee_ty: Resolved enum type of the scrutinee.
            coverage: Validated patterns and reachability from before traversal.

        Returns:
            Whether a wildcard or explicit variants cover the complete enum.
        """
        # check that all variants are covered (or wildcard present)
        is_wildcard_present = any(isinstance(arm.pattern, WildcardPattern) for arm in stmt.arms)
        is_exhaustive = is_wildcard_present
        if not is_wildcard_present:
            if coverage.covered_variants == coverage.defined_variants:
                is_exhaustive = True
            else:
                missing_variants = coverage.defined_variants - coverage.covered_variants
                self.state._error(
                    stmt,
                    f"[TYP-0104] non-exhaustive match: missing variants ("
                    f"{', '.join(missing_variants)}) for enum '{format_type(scrutinee_ty)}'"
                )
        elif coverage.wildcard_is_unreachable:
            # wildcard is a no-op if all variants are already covered
            self.state._warn(stmt,
                       f"[TYP-0105] unreachable wildcard pattern in match: all variants of "
                       f"enum '{format_type(scrutinee_ty)}' are already covered")

        return is_exhaustive
