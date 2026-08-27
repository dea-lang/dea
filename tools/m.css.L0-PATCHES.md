# Vendored `m.css` Notes

- Third-party notice index: `THIRD_PARTY_NOTICES`
- Upstream snapshot: `0a460a7a`
- Vendored as a tracked source snapshot for reproducible offline docs builds.
- Local adjustments in `documentation/doxygen.py`:
  - allow `Python`, `C`, `Markdown`, and `Objective-C` compounds in addition to `C++`
  - handle nested or empty heading/title text via `itertext()`
  - avoid false heading warnings on empty text nodes with children
  - validate and normalize Doxygen 1.18 anonymous nested-compound field paths when their `[struct]` / `[union]`
    markers prevent the child display name from using the parent display name as a literal prefix
  - preserve bitfield width metadata from Doxygen XML for member-variable declarations
  - treat unnamed bitfields with C-keyword placeholder names (for example `int`) as declaration-only types
- Local adjustments in `documentation/templates/doxygen/`:
  - `base-class-reference.html`: detect L0 compounds (`*.l0`) and label member-variable sections as `Fields` / `Field documentation`; non-L0 compounds use `Public attributes` / `Member data documentation`
  - `entry-var.html` and `details-var.html`: render L0 non-static struct/class members with L0 syntax `name: type`, omit C++ scope-style prefixes, append bitfield widths (`: N`) to variable declarations, and collapse anonymous Doxygen inline type placeholders (`::@...`) to plain `struct` / `union`
  - `entry-enum.html`: render L0 enum variants with L0 syntax (`Variant(payload);`) by removing C-style `=` before payloads and using `;` separators

The repo docs pipeline uses `tools/m.css/documentation/doxygen.py` directly and does not clone `m.css` at build time.
