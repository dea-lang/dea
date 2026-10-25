# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Regressions for physical C documentation contracts and source inventory."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_c_docs import brief, executable_tokens, exclusion, functions, validate


def write_sources(root, sources):
    """Write a small header/definition fixture.

    Args:
        root: Temporary fixture directory.
        sources: Mapping of real relative filenames to C source text.

    Returns:
        Repository-relative fixture paths in insertion order.
    """
    paths = []
    for name, source in sources.items():
        path = Path(name)
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(source, encoding="utf-8")
        paths.append(path)
    return paths


def test_matching_wrapped_brief_ignores_parameter_names(tmp_path):
    paths = write_sources(tmp_path, {
        "api.h": "/* Read an owned value safely. */\nint read_value(const char *path);\n",
        "api.c": "/**\n * Read an owned value\n * safely.\n *\n * @param filename Input filename.\n * @return Owned value, or -1 on failure.\n */\nint read_value(const char *filename) { return 0; }\n",
    })
    assert validate(tmp_path, paths) == []


def test_different_brief_is_reported_only_for_matching_signature(tmp_path):
    (tmp_path / "api.h").write_text("/* Return a value. */\nint value(int input);\n")
    (tmp_path / "api.c").write_text("/**\n * Compute a value.\n */\nint value(int n) { return n; }\n")
    paths = [Path("api.h"), Path("api.c")]
    assert any("header brief differs" in error for error in validate(tmp_path, paths))
    (tmp_path / "api.c").write_text("/**\n * Compute a value.\n */\nint value(char *n) { return 0; }\n")
    assert validate(tmp_path, paths) == []


def test_static_functions_and_language_levels_do_not_share_contracts(tmp_path):
    paths = write_sources(tmp_path, {
        "l1/api.h": "/* Return a value. */\nint value(int input);\n",
        "l2/api.c": "/**\n * Compute a value.\n */\nint value(int input) { return input; }\n",
        "l1/other.c": "/**\n * Compute another value.\n */\nstatic int value(int input) { return input; }\n",
    })
    assert validate(tmp_path, paths) == []


@pytest.mark.parametrize("source", [
    "int value(void) { return 1; }\n",
    "/** Return a value. */\nint value(void) { return 1; }\n",
    "/* Return a value. */\nint value(void) { return 1; }\n",
    "/**\n * Return a value.\n */\nint other;\nint value(void) { return 1; }\n",
])
def test_each_physical_definition_requires_adjacent_multiline_doxygen(tmp_path, source):
    (tmp_path / "api.c").write_text(source)
    assert any("definition needs" in error for error in validate(tmp_path, [Path("api.c")]))


def test_header_defined_and_conditional_functions_keep_full_contracts(tmp_path):
    source = """#if USE_FAST

/**
 * Return the input unchanged.
 */
static inline int value(int input) { return input; }
#else

/**
 * Return the input unchanged.
 */
static inline int value(int input) { return input; }
#endif
"""
    (tmp_path / "inline.h").write_text(source)
    assert len(functions(source)) == 2
    assert validate(tmp_path, [Path("inline.h")]) == []


def test_parenthesized_names_are_definitions_and_body_calls_are_not():
    source = "int (value)(int x) { return helper(x); }\nint next(void) { return value(2); }\n"
    actual = functions(source)
    assert [function.name for function in actual] == ["value", "next"]
    assert all(function.definition for function in actual)


def test_literals_macros_and_function_pointer_fields_are_not_functions():
    source = '''#define DECLARE(name) int name(void) { return 0; }
const char *text = "/* fake comment */ fake() { }";
struct Callbacks { int (*call)(int); };
typedef int (*Callback)(int);
extern "C" {
int real(int (*callback)(int));
}
'''
    assert [function.name for function in functions(source)] == ["real"]


def test_spacing_checks_ordinary_blocks_but_ignores_literal_bytes(tmp_path):
    source = 'const char *text = "/* not a comment */";\n/* section */\nint x; /* inline */\n'
    (tmp_path / "api.c").write_text(source)
    errors = validate(tmp_path, [Path("api.c")])
    assert len(errors) == 2
    assert all("blank source line" in error for error in errors)


def test_token_equivalence_preserves_literals_operators_and_directive_boundaries():
    assert executable_tokens('int x=1; /* note */ x++;') == executable_tokens('int x = 1;\n\n/**\n * Note.\n */\nx ++;')
    assert executable_tokens('x++;') != executable_tokens('x + +;')
    assert executable_tokens('char *x="/* a */";') != executable_tokens('char *x="/* b */";')
    assert executable_tokens('#define VALUE 1\nint x;') != executable_tokens('#define VALUE\n1 int x;')


def test_explicit_vendor_and_generated_exclusions_do_not_hide_owned_header_libraries():
    assert exclusion(Path("tools/third-party/file.h"))
    assert exclusion(Path("editors/tree-sitter-dea/src/parser.c"))
    assert exclusion(Path("editors/tree-sitter-dea/src/tree_sitter/parser.h"))
    assert exclusion(Path("l0/compiler/stage2_l0/tests/fixtures/backend_golden/basic_main/basic_main.golden.c"))
    assert exclusion(Path("l1/compiler/shared/runtime/internal/dea_siphash.h")) is None
    assert exclusion(Path("l1/compiler/support/preparation/profile.h")) is None
    assert exclusion(Path("l1/work/benchmark.c")) is None


def test_canonical_brief_retains_punctuation_and_drops_contract_details():
    assert brief("/**\n * Read a value safely. Further details.\n *\n * @return Owned value.\n */") == "Read a value safely."
    assert brief("/* Read a value safely. */") == "Read a value safely."


@pytest.mark.parametrize("header", [
    "/* Return a value. Additional ownership details. */",
    "/* Return a value.  */",
    "/* @brief Return a value. */",
])
def test_header_reproduces_the_exact_brief_without_additional_details(tmp_path, header):
    paths = write_sources(tmp_path, {
        "api.h": header + "\nint value(void);\n",
        "api.c": "/**\n * Return a value.\n *\n * @return An owned value.\n */\nint value(void) { return 1; }\n",
    })
    errors = validate(tmp_path, paths)
    if header == "/* Return a value.  */":
        # Spacing inside the delimiters is ordinary comment trivia; the text
        # itself still matches exactly.
        assert errors == []
    else:
        assert any("header brief differs" in error for error in errors)


def test_simple_typedef_chains_match_real_l0_header_implementation_aliases(tmp_path):
    paths = write_sources(tmp_path, {
        "l0/dea_rt.h": "typedef int l0_int;\ntypedef l0_int dea_int;\n\n/* Return a value. */\ndea_int value(dea_int input);\n",
        "l0/l0_runtime.h": "/**\n * Return another value.\n */\nl0_int value(l0_int n) { return n; }\n",
    })
    assert any("header brief differs" in error for error in validate(tmp_path, paths))


def test_conflicting_typedefs_are_not_guessed_or_merged(tmp_path):
    paths = write_sources(tmp_path, {
        "first.h": "typedef int Number;\n\n/* Return a value. */\nNumber value(Number input);\n",
        "second.c": "typedef char Number;\n\n/**\n * Return another value.\n */\nint value(int input) { return input; }\n",
    })
    assert validate(tmp_path, paths) == []


def test_callback_parameter_names_do_not_change_function_identity(tmp_path):
    paths = write_sources(tmp_path, {
        "api.h": "/* Return a value. */\nint value(int (*callback)(const char *name, int (*nested)(int x)));\n",
        "api.c": "/**\n * Return another value.\n */\nint value(int (*invoke)(const char *path, int (*call)(int y))) { return 0; }\n",
    })
    assert any("header brief differs" in error for error in validate(tmp_path, paths))
    source = (tmp_path / "api.c").read_text()
    (tmp_path / "api.c").write_text(source.replace("int y", "char y"))
    assert validate(tmp_path, paths) == []


def test_static_header_prototypes_match_only_definitions_in_the_same_header(tmp_path):
    paths = write_sources(tmp_path, {
        "api.h": "/* Return a value. */\nstatic int value(void);\n",
        "other.c": "/**\n * Return another value.\n */\nint value(void) { return 0; }\n",
    })
    assert validate(tmp_path, paths) == []
    with (tmp_path / "api.h").open("a") as stream:
        stream.write("\n/**\n * Return another value.\n */\nstatic int value(void) { return 0; }\n")
    assert any("header brief differs" in error for error in validate(tmp_path, paths))


@pytest.mark.parametrize("contract", [
    "/**\nBad content prefix.\n */",
    "/**\n* Missing source indentation.\n */",
    "/**\n * Return a value.\n*/",
    "/**\n * Return a value.\n * @file api.c\n */",
    "/**\n * A record.\n * @struct Record\n */",
])
def test_function_contracts_have_multiline_style_and_function_owned_content(tmp_path, contract):
    paths = write_sources(tmp_path, {"api.c": contract + "\nint value(void) { return 1; }\n"})
    assert any("function-owned Doxygen" in error for error in validate(tmp_path, paths))


def test_field_comments_and_external_abi_prototypes_do_not_supply_function_contracts(tmp_path):
    paths = write_sources(tmp_path, {
        "api.h": "/* Import the external allocator hook. */\nvoid external_allocate(int bytes);\n",
        "api.c": "struct Record { int field; }; /* A record field. */\nint undocumented(void) { return 1; }\n",
    })
    errors = validate(tmp_path, paths)
    assert any("undocumented: definition needs" in error for error in errors)
    assert not any("external_allocate" in error for error in errors)


@pytest.mark.parametrize(("left", "right"), [
    ("double x=1e+3;", "double x=1e + 3;"),
    ("double x=0x1p+3;", "double x=0x1p + 3;"),
    ("int x<:2:>;", "int x < :2:>;"),
    ("#define F(x) x\n", "#define F (x) x\n"),
    ("int x??(2??);", "int x? ?(2??);"),
    ('char *x=L"text";', 'char *x=L "text";'),
    ('char x=\'\\n\';', 'char x=\'n\';'),
])
def test_executable_tokens_preserve_preprocessing_token_boundaries(left, right):
    assert executable_tokens(left) != executable_tokens(right)


def test_executable_tokens_preserve_line_splicing_and_comments_between_identifiers():
    assert executable_tokens("#define F(x) \\\n x\n") == executable_tokens("#define F(x) x\n")
    assert executable_tokens("int x/**/y;") == executable_tokens("int x y;")
    assert executable_tokens("int x/**/y;") != executable_tokens("int xy;")


def test_unnamed_qualified_typedef_parameters_are_types_not_declarator_names(tmp_path):
    paths = write_sources(tmp_path, {
        "api.h": "typedef int Number;\n\n/* Return a value. */\nint value(const Number, const Number *, struct Record *);\n",
        "api.c": "/**\n * Return another value.\n */\nint value(const Number input, const Number *other, struct Record *record) { return 0; }\n",
    })
    assert any("header brief differs" in error for error in validate(tmp_path, paths))


@pytest.mark.parametrize("command", ["@brief", "\\brief"])
@pytest.mark.parametrize("filename", ["api.c", "api.h"])
def test_explicit_brief_commands_require_javadoc_autobrief(tmp_path, command, filename):
    source = "/**\n * " + command + " Return a value.\n */\nint value(void) { return 1; }\n"
    paths = write_sources(tmp_path, {filename: source})
    errors = validate(tmp_path, paths)
    assert len(errors) == 1
    assert errors[0].startswith(filename + ":2: use Javadoc autobrief:")
    assert "start with the brief sentence" in errors[0]
    assert "omit explicit" in errors[0]


@pytest.mark.parametrize("command", ["@brief", "\\brief"])
def test_autobrief_applies_to_nonfunction_documentation_too(tmp_path, command):
    paths = write_sources(tmp_path, {
        "types.h": "/**\n * " + command + " An integer field.\n */\ntypedef int Field;\n",
    })
    assert any("use Javadoc autobrief" in error for error in validate(tmp_path, paths))


def test_autobrief_uses_the_first_sentence_not_the_entire_first_paragraph(tmp_path):
    paths = write_sources(tmp_path, {
        "api.h": "/* Return an owned value. */\nint value(void);\n",
        "api.c": "/**\n * Return an owned value. The caller releases it exactly once.\n * Allocation failure returns -1 without acquiring a resource.\n *\n * @return The owned value, or -1 on failure.\n */\nint value(void) { return 1; }\n",
    })
    assert validate(tmp_path, paths) == []
    comment = "/**\n * Return an owned value. The caller releases it exactly once.\n */"
    assert brief(comment) == "Return an owned value."
    (tmp_path / "api.h").write_text("/* Return an owned value. The caller releases it exactly once. */\nint value(void);\n")
    assert any("header brief differs" in error for error in validate(tmp_path, paths))


def test_brief_parser_remains_compatible_without_accepting_explicit_commands(tmp_path):
    for command in ("@brief", "\\brief"):
        comment = "/**\n * " + command + " Read a value. Further details.\n */"
        assert brief(comment) == "Read a value."
        paths = write_sources(tmp_path, {"api.c": comment + "\nint value(void) { return 1; }\n"})
        assert any("use Javadoc autobrief" in error for error in validate(tmp_path, paths))


def test_autobrief_does_not_rewrite_or_validate_vendor_exclusions(tmp_path):
    paths = write_sources(tmp_path, {
        "tools/vendor/api.h": "/** @brief Original third-party contract. */\nint value(void);\n",
    })
    assert validate(tmp_path, paths) == []
