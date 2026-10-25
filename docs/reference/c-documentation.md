# C Function Documentation

Version: 2026-10-26

This convention applies to repository-owned maintained `.c` and `.h` files across every language level, shared support,
editor bindings, examples, tests, and benchmark probes. It changes documentation placement without changing C code or
moving header-only libraries into source files.

## Canonical contracts

Every function definition has a complete multiline Doxygen block immediately before its definition. Put `/**` on its own
line, prefix content lines with ` *`, and use Javadoc autobrief: the first sentence is the brief. Omit explicit `@brief`
and `\brief` commands. All production reference configurations enable `JAVADOC_AUTOBRIEF = YES`. Subsequent sentences
and paragraphs form the detailed description. Include applicable parameter and return descriptions, ownership and
lifetime rules, failures, preconditions, and guarantees. Consolidate differing header and implementation descriptions
into one accurate contract rather than discarding either occurrence's information.

```c
/**
 * Read the complete file into caller-owned storage.
 *
 * The caller releases a successful result with free(). Failure leaves no allocation.
 *
 * @param path Borrowed, NUL-terminated native filename.
 * @return Owned NUL-terminated contents, or NULL on open, read, or allocation failure.
 */
char *read_contents(const char *path) {

    /* Implementation omitted in this documentation example. */
}
```

The corresponding header prototype has only an ordinary one-line block reproducing the canonical first sentence exactly:

```c
/* Read the complete file into caller-owned storage. */
char *read_contents(const char *path);
```

Functions defined in headers retain their full Doxygen contracts there. This includes static, inline, private
preparation helpers, and header-only libraries such as `dea_siphash.h`. A forward prototype in the same header still
uses the short ordinary comment. Document every physical definition in conditional alternatives.

Leave a blank source line before every ordinary or Doxygen block comment, except at the beginning of a file. This
includes function, implementation, and section comments. Type, field, enum, macro, and file documentation remains in its
natural location. Comments must not interrupt preprocessor continuation lines or otherwise change executable code.

## Inventories and validation

Run `python3 scripts/check_c_docs.py` from the repository root. The pre-commit configuration runs the same check for C
changes. It inventories tracked C/header files, rejects explicit brief commands, checks block spacing and adjacent
multiline definition contracts, and compares ordinary header briefs with matching definition signatures. Static
functions in separate files and functions from separate language levels are distinct. The lexical checker resolves
unambiguous simple typedef chains, but does not expand C macros or infer arbitrary C type equivalence. Real-Doxygen
regressions independently verify extracted contracts and source locations.

The checker explicitly excludes `tools/` third-party code, generated backend golden C, the generated Tree-sitter parser,
and Tree-sitter's upstream support headers. It does not exclude owned header-only libraries or owned benchmark
attachments. Preserve excluded files and their existing documentation.

Documentation source manifests must include implementation `.c` files and implementation headers as well as public
headers. Keep `INPUT`, `FILE_PATTERNS`, shadow copying, language filters, and exclusion patterns aligned with those
manifests. C shadow files retain their comments and original source line structure. Compiler-language adapters must not
rewrite C input.

Extract separate language bindings and alternative native implementation roles independently before combining their
references. Doxygen otherwise associates unrelated same-signature functions and copies their parameter and return
descriptions across bindings. Preserve original source paths, line numbers, and signatures when combining output.

Undocumented-function reports recognize documentation on either occurrence of the same C declaration/definition.
Association must use source identity and signature, with language and linkage boundaries retained. A name alone is
insufficient: unrelated static functions, different signatures, and separate Dea/C bindings remain separate findings. If
a Doxygen version omits an explicit declaration/body relationship, keep the undocumented occurrence separate even when
its normalized signature matches a documented function. When header and definition parameter names differ, preserve
their original signatures and use Doxygen's explicit declaration/definition name relationship to label copied parameter
descriptions for the displayed occurrence. Reports describe their selected production inventories; they do not imply
coverage of examples, fixtures, or generated and vendored code that the reference does not select.

L1 and L2 native extraction explicitly enables the trace-located APIs (`DEA_TRACE_ARC`, `DEA_TRACE_MEMORY`) and
SipHash's implementation (`SIPHASH_IMPLEMENTATION`). L0 enables the SipHash implementation and otherwise uses its
ordinary preprocessing profile. These profiles select documented native bodies; they do not enumerate every mutually
exclusive platform, sanitizer, checking, or trace branch. The physical-source checker covers conditional definitions
separately.

Regenerate affected full references after changing contracts or inventories. Review parameters, returns, ownership,
failures, header-defined functions, and declaration/body locations in real Doxygen output. Inspect remaining report
entries individually before describing them as genuine gaps or extraction limitations.
