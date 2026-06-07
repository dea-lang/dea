# Compiler Diagnostic Code Catalog

Version: 2026-06-07

Normative catalog of Dea compiler diagnostic codes.

## Related Docs

- [l0/docs/specs/compiler/diagnostic-code-policy.md](../../../l0/docs/specs/compiler/diagnostic-code-policy.md): L0
  Stage 1/Stage 2 parity and reuse supplement for this shared registry.
- [l0/docs/specs/compiler/diagnostic-format.md](../../../l0/docs/specs/compiler/diagnostic-format.md): output rendering
  format.
- [l0/compiler/stage1_py/l0_diagnostics.py](../../../l0/compiler/stage1_py/l0_diagnostics.py): current L0 registered
  family/code source of truth.
- [l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py](../../../l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py):
  trigger matrix for registered code meanings.

## Scope

This catalog normatively defines the shared compiler diagnostic code registry currently tracked in the repository.

It is intended to be shared across Dea compiler implementations rather than tied to a specific level or stage.

This document is the normative shared registry for diagnostic code identifiers, `Level`, and `Meaning`.

For L0 compiler work, `l0/docs/specs/compiler/diagnostic-code-policy.md` remains the normative Stage 1/Stage 2 parity
and reuse supplement for applying this registry within L0.

## Notes

- Codes are grouped by family following `DIAGNOSTIC_CODE_FAMILIES`; additional Dea-wide codes not yet present in the
  current L0 Stage 1 registry appear in numeric order within their family tables.
- Each family is presented as a table so the catalog can be extended incrementally as new compiler rules and diagnostic
  families are implemented.
- Level-specific compiler-code families that share numeric slots use paired concrete-code columns; blank cells mean no
  code is registered for that level in that row.
- For L0 compiler codes, Python Stage 1 is the current L0 oracle inventory and meaning source.
- `Level` records the Dea-level applicability of the code.
- `Meaning` records the current canonical issue represented by the code.
- `Level` uses `All` for shared entries, `L0 only` and `L1 only` for level-specific compiler-code entries, and `L1+` for
  codes intentionally introduced for L1 and higher levels.
- `ICE-xxxx` codes are currently not part of that central register and are therefore not included in this catalog.
- Any change to the registered compiler inventory should update this document in the same change, including `Level` and
  `Meaning`.

## Lexical Analysis

| Code       | Level   | Meaning                                                |
| ---------- | ------- | ------------------------------------------------------ |
| `LEX-0010` | All     | Unterminated string literal                            |
| `LEX-0020` | All     | Unterminated char literal                              |
| `LEX-0021` | All     | Invalid char literal, expected closing single quote    |
| `LEX-0030` | All     | Character literal must represent a single byte         |
| `LEX-0031` | All     | Character literal hex escape out of range (0-255)      |
| `LEX-0040` | All     | Unexpected character in source text                    |
| `LEX-0050` | All     | Invalid hex escape sequence                            |
| `LEX-0051` | All     | Invalid unicode escape sequence (\\u)                  |
| `LEX-0052` | All     | Invalid unicode escape sequence (\\U)                  |
| `LEX-0053` | All     | Octal escape sequence out of range (0-255)             |
| `LEX-0054` | All     | Unicode code point out of range (must be \<= 0x10FFFF) |
| `LEX-0059` | All     | Unknown escape sequence                                |
| `LEX-0060` | L0 only | Integer literal exceeds 32-bit signed range            |
| `LEX-0061` | All     | Invalid character after integer literal                |
| `LEX-0062` | L1+     | Invalid hexadecimal integer literal                    |
| `LEX-0063` | L1+     | Invalid binary integer literal                         |
| `LEX-0064` | L1+     | Invalid octal integer literal                          |
| `LEX-0065` | L1+     | Invalid real literal: missing exponent digits          |
| `LEX-0066` | L1+     | Invalid character after real literal                   |
| `LEX-0067` | L1+     | Invalid suffix after real literal                      |
| `LEX-0068` | L1+     | Invalid float suffix after integer literal             |
| `LEX-0070` | All     | Unterminated block comment                             |

## Parsing and Parse-Time Analysis

| Code       | Level   | Meaning                                                                  |
| ---------- | ------- | ------------------------------------------------------------------------ |
| `PAR-0000` | All     | Fallback parser error when no specific parse/lex diagnostic is available |
| `PAR-0010` | All     | Invalid variable name: reserved for future language use                  |
| `PAR-0011` | All     | Invalid variable name: reserved identifier                               |
| `PAR-0020` | All     | Unexpected top-level declaration                                         |
| `PAR-0030` | All     | Expected 'extern'                                                        |
| `PAR-0040` | All     | Expected 'func'                                                          |
| `PAR-0041` | All     | Expected function name                                                   |
| `PAR-0042` | All     | Expected '('                                                             |
| `PAR-0043` | All     | Expected parameter name                                                  |
| `PAR-0044` | All     | Expected ':' after parameter name                                        |
| `PAR-0045` | All     | Expected ')' after parameters                                            |
| `PAR-0046` | All     | Expected ';' after extern function decl                                  |
| `PAR-0050` | All     | Expected 'struct'                                                        |
| `PAR-0051` | All     | Expected struct name                                                     |
| `PAR-0052` | All     | Expected '{' after struct name                                           |
| `PAR-0053` | All     | Expected field name                                                      |
| `PAR-0054` | All     | Expected ':' after field name                                            |
| `PAR-0055` | All     | Expected ';' after field declaration                                     |
| `PAR-0056` | All     | Expected '}' after struct body                                           |
| `PAR-0060` | All     | Expected 'enum'                                                          |
| `PAR-0061` | All     | Expected enum name                                                       |
| `PAR-0062` | All     | Expected '{' after enum name                                             |
| `PAR-0063` | All     | Expected variant name                                                    |
| `PAR-0064` | All     | Expected variant field name                                              |
| `PAR-0065` | All     | Expected ':'                                                             |
| `PAR-0066` | All     | Expected ')' after variant payload                                       |
| `PAR-0067` | All     | Expected ';' after variant                                               |
| `PAR-0068` | All     | Expected '}' after enum body                                             |
| `PAR-0070` | All     | Expected type name                                                       |
| `PAR-0071` | All     | Expected type alias name                                                 |
| `PAR-0072` | All     | Expected '=' in type alias                                               |
| `PAR-0073` | All     | Expected ';' after type alias                                            |
| `PAR-0080` | All     | Expected 'let'                                                           |
| `PAR-0081` | All     | Expected variable name                                                   |
| `PAR-0082` | All     | Expected '=' in let binding                                              |
| `PAR-0083` | All     | Expected ';' after let declaration                                       |
| `PAR-0090` | All     | Expected '{' to start block                                              |
| `PAR-0091` | All     | Expected '}' after block                                                 |
| `PAR-0100` | All     | Expected ';' after statement                                             |
| `PAR-0110` | All     | Expected 'let'                                                           |
| `PAR-0111` | All     | Expected variable name                                                   |
| `PAR-0112` | All     | Expected '=' in let binding                                              |
| `PAR-0120` | All     | Expected 'if'                                                            |
| `PAR-0121` | All     | Expected '(' after 'if'                                                  |
| `PAR-0122` | All     | Expected ')' after condition                                             |
| `PAR-0130` | All     | Expected 'while'                                                         |
| `PAR-0131` | All     | Expected '('                                                             |
| `PAR-0132` | All     | Expected ')'                                                             |
| `PAR-0140` | All     | Expected 'for'                                                           |
| `PAR-0141` | All     | Expected '(' after 'for'                                                 |
| `PAR-0142` | All     | Expected ';' after for loop initialization                               |
| `PAR-0143` | All     | Expected ';' after for loop condition                                    |
| `PAR-0144` | All     | Expected ')' after for loop clauses                                      |
| `PAR-0150` | All     | Expected 'return'                                                        |
| `PAR-0160` | All     | Expected 'drop'                                                          |
| `PAR-0161` | All     | Expected variable name after 'drop'                                      |
| `PAR-0170` | All     | Expected 'match'                                                         |
| `PAR-0171` | All     | Expected '('                                                             |
| `PAR-0172` | All     | Expected ')'                                                             |
| `PAR-0173` | All     | Expected '{' after match expression                                      |
| `PAR-0174` | All     | Expected '=>' in match arm                                               |
| `PAR-0175` | All     | Expected '}' after match                                                 |
| `PAR-0176` | All     | Duplicate variant patterns in match statement                            |
| `PAR-0177` | All     | Match statement must have at least one arm                               |
| `PAR-0180` | All     | Expected pattern variable name                                           |
| `PAR-0181` | All     | Expected ')' in pattern                                                  |
| `PAR-0182` | All     | Unexpected pattern syntax                                                |
| `PAR-0190` | All     | Expected 'break'                                                         |
| `PAR-0200` | All     | Expected 'continue'                                                      |
| `PAR-0210` | All     | Expected ')' after arguments                                             |
| `PAR-0211` | All     | Expected '\]' after index                                                |
| `PAR-0212` | All     | Expected field name after '.'                                            |
| `PAR-0223` | All     | Expected ')' after arguments to 'new'                                    |
| `PAR-0224` | All     | Expected ')' after expression                                            |
| `PAR-0225` | All     | Expected expression                                                      |
| `PAR-0226` | L0 only | Operator is not yet supported                                            |
| `PAR-0230` | All     | Expected 'case'                                                          |
| `PAR-0231` | All     | Expected '('                                                             |
| `PAR-0232` | All     | Expected ')'                                                             |
| `PAR-0233` | All     | Expected '{' after 'case' expression                                     |
| `PAR-0234` | All     | Value arm cannot appear after the default arm in 'case' statement        |
| `PAR-0235` | All     | Expected '=>' in 'case' arm                                              |
| `PAR-0236` | All     | Duplicate default arm in 'case' statement                                |
| `PAR-0237` | All     | '=>' not allowed in 'else' arm                                           |
| `PAR-0238` | All     | Expected value literal, `_`, or `else` in `case` arm                     |
| `PAR-0239` | All     | Expected '}' after 'case' statement                                      |
| `PAR-0240` | All     | 'case' statement must have at least one arm                              |
| `PAR-0241` | All     | Expected literal in 'case' arm                                           |
| `PAR-0242` | All     | Deprecated `else` default arm in `case`; use `_ =>` instead (warning)    |
| `PAR-0243` | All     | Ambiguous `else` after `if` in `case` value arm; brace it or use `_ =>`  |
| `PAR-0260` | L1+     | `const` declarations require an explicit type annotation                 |
| `PAR-0261` | L1+     | Expected '=' in const binding                                            |
| `PAR-0262` | L1+     | Expected ';' after const declaration                                     |
| `PAR-0263` | L1+     | `const` declarations are only supported at top level                     |
| `PAR-0300` | All     | Expected identifier after '.' in module name                             |
| `PAR-0310` | All     | Expected 'module'                                                        |
| `PAR-0311` | All     | Expected module name                                                     |
| `PAR-0312` | All     | Expected ';' after module name                                           |
| `PAR-0320` | All     | Expected imported module name                                            |
| `PAR-0321` | All     | Expected ';' after import                                                |
| `PAR-0400` | All     | Expected type name                                                       |
| `PAR-0401` | All     | Expected identifier after '::' in qualified name                         |
| `PAR-0500` | All     | Expected 'with'                                                          |
| `PAR-0501` | All     | Expected '(' after 'with'                                                |
| `PAR-0502` | All     | Expected ')' after with items                                            |
| `PAR-0503` | All     | 'with': all items must use '=>' or none                                  |
| `PAR-0504` | All     | 'with': cannot have both '=>' and cleanup block                          |
| `PAR-0505` | All     | 'with': cleanup block required when '=>' is not used                     |
| `PAR-0540` | L1+     | Expected exported name or '\*' in export manifest                        |
| `PAR-0541` | L1+     | Expected ';' after export manifest                                       |
| `PAR-0542` | L1+     | Export manifest is not allowed after imports or declarations             |
| `PAR-0543` | L1+     | Duplicate export manifest                                                |
| `PAR-0544` | L1+     | Expected imported symbol name after ',' in selective import              |
| `PAR-0545` | L1+     | Expected 'from' after selective import list                              |
| `PAR-0546` | L1+     | Expected imported module name after 'from'                               |
| `PAR-0547` | L1+     | Expected import alias after 'as'                                         |
| `PAR-0550` | L1+     | Cannot mix named and positional arguments in one call or allocation      |
| `PAR-0560` | L1+     | Expected `module` keyword at start of interface file                     |
| `PAR-0561` | L1+     | Expected `interface` keyword in module interface declaration             |
| `PAR-0562` | L1+     | Expected module name in interface file header                            |
| `PAR-0563` | L1+     | Expected ';' after module interface declaration                          |
| `PAR-0564` | L1+     | Expected `fingerprint` declaration after module interface header         |
| `PAR-0565` | L1+     | Expected string literal after `fingerprint`                              |
| `PAR-0566` | L1+     | Expected ';' after fingerprint declaration                               |
| `PAR-0567` | L1+     | Expected ':' or '=' after name in interface declaration                  |
| `PAR-0568` | L1+     | Expected ';' after function signature in interface file                  |
| `PAR-0569` | L1+     | Expected ';' after let declaration in interface file                     |
| `PAR-0570` | L1+     | Expected constant literal value after '=' in interface const declaration |
| `PAR-0571` | L1+     | Expected ';' after const declaration in interface file                   |
| `PAR-0572` | L1+     | Unsupported or unexpected token in interface file                        |
| `PAR-0573` | L1+     | Expected identifier after keyword in interface declaration               |
| `PAR-0600` | L1+     | Expected `func` or `extern` after `unsafe` in top-level declaration      |
| `PAR-0601` | L1+     | Expected `func` after `unsafe` in function type                          |
| `PAR-0602` | L1+     | Expected `func` after `unsafe` in interface file                         |
| `PAR-0620` | L1+     | Expected integer length in array type suffix                             |
| `PAR-0621` | L1+     | Expected '\]' after array type length                                    |
| `PAR-0622` | L1+     | Expected '\]' after array literal                                        |
| `PAR-0623` | L1+     | Expected ')' after array constructor arguments                           |
| `PAR-9401` | L0 only | Array types are not supported in L0                                      |

## Driver and Environment

| Code       | Level | Meaning                                                                               |
| ---------- | ----- | ------------------------------------------------------------------------------------- |
| `DRV-0010` | All   | File-related driver error, e.g. module source file not found                          |
| `DRV-0011` | All   | Cannot read source file for a resolved module                                         |
| `DRV-0020` | All   | Input validation error, e.g. declared module name does not match the requested module |
| `DRV-0030` | All   | Import-related driver error, e.g. cyclic module imports                               |
| `DRV-0040` | All   | Source decoding error, e.g. input file is not valid UTF-8                             |

## Build, Code Generation, and Runtime

| L0 code    | L1 code    | Level   | Meaning                                                                                               |
| ---------- | ---------- | ------- | ----------------------------------------------------------------------------------------------------- |
| `L0C-0009` | `L1C-0009` | All     | No C compiler found: use '--c-compiler' or the level-specific C compiler environment variable         |
| `L0C-0010` | `L1C-0010` | All     | C compilation failed                                                                                  |
| `L0C-0011` | `L1C-0011` | All     | Invalid entry module name: module components must be valid identifiers                                |
| `L0C-0012` | `L1C-0012` | All     | Entry module not found in analysis result or does not define a build/run `main` function              |
| `L0C-0013` | `L1C-0013` | All     | Entry `main` returns a non-preferred type; the generated C entry wrapper ignores the return value     |
| `L0C-0014` | `L1C-0014` | All     | Runtime library path does not exist or is not a directory                                             |
|            | `L1C-0015` | L1 only | Runtime library directory does not contain any supported runtime library                              |
| `L0C-0016` | `L1C-0016` | All     | Missing type information for the entry `main` function                                                |
| `L0C-0017` | `L1C-0017` | All     | '--output' is ignored in '--run' mode unless '--keep-c' is set; the executable path remains temporary |
|            | `L1C-0018` | L1 only | Explicit C compiler option violates the L1 floating-point backend contract                            |
|            | `L1C-0019` | L1 only | Trace flags under '--gen' require the caller to link or compile against the traced runtime surface    |
| `L0C-0020` |            | L0 only | Analysis or AST command failed with an exception                                                      |
| `L0C-0030` |            | L0 only | Entry module not found in compilation unit                                                            |
| `L0C-0040` | `L1C-0040` | All     | Cannot read an input source file during token dump                                                    |
| `L0C-0041` |            | L0 only | Source file encoding error during token dump                                                          |
| `L0C-0050` |            | L0 only | Compilation-unit discovery failed during all-modules token dump                                       |
| `L0C-0060` |            | L0 only | Discovered module path could not be resolved during all-modules token dump                            |
| `L0C-0070` | `L1C-0070` | All     | Entry module path or unit could not be resolved for token dump or Stage 1 introspection commands      |
| `L0C-2001` | `L1C-2001` | All     | Unknown command-line option                                                                           |
| `L0C-2002` | `L1C-2002` | All     | Multiple conflicting mode flags were provided                                                         |
| `L0C-2003` | `L1C-2003` | All     | Missing value for an option that requires an argument                                                 |
| `L0C-2010` | `L1C-2010` | All     | '--output' is valid only with '--build', '--gen', or '--run'                                          |
| `L0C-2011` | `L1C-2011` | All     | '--keep-c' is valid only with '--build' or '--run'                                                    |
| `L0C-2012` | `L1C-2012` | All     | '--c-compiler' is valid only with '--build' or '--run'                                                |
| `L0C-2013` | `L1C-2013` | All     | '--c-options' is valid only with '--build' or '--run'                                                 |
| `L0C-2014` | `L1C-2014` | All     | '--runtime-include' is valid only with '--build' or '--run'                                           |
| `L0C-2015` | `L1C-2015` | All     | '--runtime-lib' is valid only with '--build' or '--run'                                               |
| `L0C-2016` | `L1C-2016` | All     | '--no-line-directives' is valid only with '--build', '--gen', or '--run'                              |
| `L0C-2017` | `L1C-2017` | All     | '--trace-arc' is valid only with '--build', '--gen', or '--run'                                       |
| `L0C-2018` | `L1C-2018` | All     | '--trace-memory' is valid only with '--build', '--gen', or '--run'                                    |
| `L0C-2019` | `L1C-2019` | All     | '--all-modules' is valid only with '--ast', '--sym', '--tok', or '--type'                             |
| `L0C-2020` | `L1C-2020` | All     | '--include-eof' is valid only with '--tok'                                                            |
| `L0C-2021` | `L1C-2021` | All     | Missing required target module or file name                                                           |
| `L0C-2022` | `L1C-2022` | All     | '--run' accepts exactly one target; use '--' before runtime program arguments                         |
| `L0C-2023` | `L1C-2023` | All     | Arguments after '--' are valid only with '--run'                                                      |
| `L0C-2024` | `L1C-2024` | All     | Multiple targets are not supported yet; pass exactly one target                                       |
| `L0C-9510` | `L1C-9510` | All     | Requested CLI mode is not implemented in Stage 1 yet                                                  |
| `L0C-9511` | `L1C-9511` | All     | Cannot write an output file                                                                           |

## Name Resolution and Import Analysis

| Code       | Level | Meaning                                                                              |
| ---------- | ----- | ------------------------------------------------------------------------------------ |
| `RES-0010` | All   | Duplicate top-level definition in the same module                                    |
| `RES-0020` | All   | Imported extern function is shadowed by a compatible local extern declaration        |
| `RES-0021` | All   | Imported symbol is shadowed by a local definition                                    |
| `RES-0022` | All   | Ambiguous unqualified import: the same symbol name is imported from multiple modules |
| `RES-0029` | All   | Import refers to an unknown module                                                   |
| `RES-0030` | L1+   | Duplicate name in explicit export manifest                                           |
| `RES-0031` | L1+   | Explicit export manifest names an unknown top-level symbol                           |
| `RES-0032` | L1+   | Selective import names a symbol that the imported module does not export             |
| `RES-0033` | L1+   | Duplicate import alias in the same module                                            |
| `RES-0034` | L1+   | Name is used both as an import alias and as a visible symbol in the same module      |
| `RES-0035` | L1+   | Redundant selective import names symbols already imported from the same module       |
| `RES-0036` | All   | Duplicate open import declaration for the same module                                |

## Signature Analysis and Type Resolution for Type Declarations, Type Aliases, and Type References

| Code       | Level | Meaning                                                                           |
| ---------- | ----- | --------------------------------------------------------------------------------- |
| `SIG-0010` | All   | Symbol is not a type                                                              |
| `SIG-0011` | All   | Type 'void' cannot be nullable                                                    |
| `SIG-0018` | All   | Nested symbol paths are not supported                                             |
| `SIG-0019` | All   | Unknown or ambiguous type reference                                               |
| `SIG-0020` | All   | Cyclic type alias definition                                                      |
| `SIG-0021` | All   | Internal error: compiler-inserted type alias has no backing declaration           |
| `SIG-0030` | All   | Cannot infer type for let - type annotation required for non-literal initializers |
| `SIG-0040` | All   | Value-type cycle creates an infinitely sized type                                 |
| `SIG-0200` | L1+   | `const` initializer must be compile-time constant                                 |
| `SIG-9029` | All   | Internal error: a type-alias symbol does not reference a type-alias declaration   |

## Expression Type Checking, Type Inference, and Type-Related Semantic Analysis

| Code       | Level   | Meaning                                                                                                |
| ---------- | ------- | ------------------------------------------------------------------------------------------------------ |
| `TYP-0001` | All     | No compilation unit available for expression type checking                                             |
| `TYP-0002` | All     | Internal error: missing resolved function type during expression checking                              |
| `TYP-0010` | All     | Not all control paths return the required value type                                                   |
| `TYP-0020` | All     | Local variable already declared in this scope                                                          |
| `TYP-0021` | All     | Local variable shadows variable from outer scope                                                       |
| `TYP-0022` | All     | Local variable shadows an enum variant in the same module                                              |
| `TYP-0023` | All     | Local variable shadows an imported enum variant                                                        |
| `TYP-0024` | All     | Local variable shadows an ambiguously imported symbol                                                  |
| `TYP-0025` | All     | Local variable shadows a top-level symbol                                                              |
| `TYP-0030` | All     | Unreachable code                                                                                       |
| `TYP-0031` | All     | Unreachable code after 'return'                                                                        |
| `TYP-0040` | All     | Cannot resolve type annotation for variable                                                            |
| `TYP-0050` | All     | Variable cannot have type 'void'                                                                       |
| `TYP-0051` | All     | Initializer for type mismatch                                                                          |
| `TYP-0052` | All     | Cannot infer type from 'null'; explicit type required                                                  |
| `TYP-0053` | All     | Initializer is 'void', cannot assign to variable                                                       |
| `TYP-0060` | All     | Unknown variable                                                                                       |
| `TYP-0061` | All     | Cannot drop non-pointer type                                                                           |
| `TYP-0062` | All     | Use of dropped variable                                                                                |
| `TYP-0063` | All     | Cannot drop module-level let                                                                           |
| `TYP-0070` | All     | If condition must have type 'bool'                                                                     |
| `TYP-0080` | All     | While condition must have type 'bool'                                                                  |
| `TYP-0090` | All     | For loop condition must have type 'bool'                                                               |
| `TYP-0100` | All     | Match expression must have enum type                                                                   |
| `TYP-0101` | All     | Pattern variable count mismatch: variant has fields but pattern has variables                          |
| `TYP-0102` | All     | Unknown variant for enum                                                                               |
| `TYP-0103` | All     | No type information for enum                                                                           |
| `TYP-0104` | All     | Non-exhaustive match                                                                                   |
| `TYP-0105` | All     | Unreachable wildcard pattern in match: all variants of enum are already covered                        |
| `TYP-0106` | All     | `case` scrutinee must have type `int`, `byte`, `bool`, or `string`                                     |
| `TYP-0107` | All     | 'case' arm literal must be int, byte, bool, or string                                                  |
| `TYP-0108` | All     | Duplicate literal value in 'case' statement                                                            |
| `TYP-0109` | All     | Invalid escape in 'case' literal                                                                       |
| `TYP-0110` | All     | 'break' statement not within a loop                                                                    |
| `TYP-0120` | All     | 'continue' statement not within a loop                                                                 |
| `TYP-0139` | All     | Unknown statement type                                                                                 |
| `TYP-0149` | All     | Internal error: cannot infer the type of an empty expression placeholder                               |
| `TYP-0150` | All     | Use of dropped variable                                                                                |
| `TYP-0151` | All     | Symbol is not a value                                                                                  |
| `TYP-0152` | All     | Variant requires arguments; use '(...)' constructor syntax                                             |
| `TYP-0153` | All     | Unknown identifier from an unknown module                                                              |
| `TYP-0154` | All     | Identifier refers to a non-imported module                                                             |
| `TYP-0155` | All     | Ambiguous identifier                                                                                   |
| `TYP-0156` | All     | 'cleanup' block references 'with' header variable that may be uninitialized on '?' header-failure path |
| `TYP-0158` | All     | Nested symbol paths are not supported                                                                  |
| `TYP-0159` | All     | Unknown identifier                                                                                     |
| `TYP-0160` | All     | Unary `-` requires an integer operand                                                                  |
| `TYP-0161` | All     | Unary `!` requires a `bool` operand                                                                    |
| `TYP-0162` | All     | Cannot dereference a non-pointer expression                                                            |
| `TYP-0170` | All     | Operator requires integer operands                                                                     |
| `TYP-0171` | All     | Operator requires boolean operands                                                                     |
| `TYP-0172` | All     | Equality operator requires same-type operands (except for 'null' checks)                               |
| `TYP-0173` | All     | Equality not supported for the type in question                                                        |
| `TYP-0180` | All     | Callee must be a function name                                                                         |
| `TYP-0181` | All     | Symbol is not callable                                                                                 |
| `TYP-0182` | All     | Callee is not a function                                                                               |
| `TYP-0183` | All     | Function call argument count mismatch                                                                  |
| `TYP-0189` | All     | Unknown or ambiguous callee identifier                                                                 |
| `TYP-0190` | All     | No type information for struct                                                                         |
| `TYP-0191` | All     | Struct constructor argument count mismatch                                                             |
| `TYP-0200` | All     | Variant has no type information                                                                        |
| `TYP-0201` | All     | Variant constructor argument count mismatch                                                            |
| `TYP-0210` | All     | Index expression must have type `int`                                                                  |
| `TYP-0211` | All     | Cannot index into a nullable base expression                                                           |
| `TYP-0212` | L0 only | Cannot index into expression of the given type; indexing is not yet supported                          |
| `TYP-0213` | L1+     | Cannot index into a non-pointer expression                                                             |
| `TYP-0214` | L1+     | Pointer indexing is allowed only inside an `unsafe func` body                                          |
| `TYP-0215` | L1+     | Cannot index through a pointer to an unsupported unsized pointee type such as `void`                   |
| `TYP-0220` | All     | Cannot access a field on a nullable struct                                                             |
| `TYP-0221` | All     | Struct has no field                                                                                    |
| `TYP-0222` | All     | Cannot access field on non-struct type                                                                 |
| `TYP-0230` | All     | Invalid explicit cast                                                                                  |
| `TYP-0240` | All     | Cannot take `sizeof(void)`                                                                             |
| `TYP-0241` | All     | `sizeof` expects exactly 1 argument                                                                    |
| `TYP-0242` | All     | `ord` expects exactly 1 argument                                                                       |
| `TYP-0243` | All     | `ord` expects an enum value                                                                            |
| `TYP-0244` | L1+     | Intrinsic reference may only be used in call position                                                  |
| `TYP-0245` | L1+     | `is` expects exactly 2 arguments                                                                       |
| `TYP-0246` | L1+     | `is` expects an enum value as its first argument                                                       |
| `TYP-0247` | L1+     | `is` expects an enum variant reference as its second argument                                          |
| `TYP-0248` | L1+     | `is` expects a variant of the first argument's enum type                                               |
| `TYP-0250` | All     | Cannot apply '?' to non-nullable type                                                                  |
| `TYP-0251` | All     | Cannot use '?' in a function that does not return a nullable type (T?)                                 |
| `TYP-0260` | All     | Return statement outside of function                                                                   |
| `TYP-0270` | All     | Type alias does not have a resolved type                                                               |
| `TYP-0271` | All     | Symbol is not a type                                                                                   |
| `TYP-0278` | All     | Type 'void' cannot be nullable                                                                         |
| `TYP-0279` | All     | Unknown or ambiguous type                                                                              |
| `TYP-0280` | All     | Unknown type in 'new' expression                                                                       |
| `TYP-0281` | All     | Cannot allocate enum type without a variant                                                            |
| `TYP-0282` | All     | Missing struct layout information                                                                      |
| `TYP-0283` | All     | Heap-allocated struct argument count mismatch                                                          |
| `TYP-0285` | All     | `new` scalar initializer arity mismatch                                                                |
| `TYP-0286` | All     | Invalid scalar initializer for `new`                                                                   |
| `TYP-0290` | All     | Type expression is only valid as argument to type-accepting intrinsics such as 'sizeof'                |
| `TYP-0300` | All     | Unknown type from an unknown module                                                                    |
| `TYP-0301` | All     | Type refers to a non-imported module                                                                   |
| `TYP-0303` | All     | Ambiguous identifier                                                                                   |
| `TYP-0310` | All     | Expression type mismatch                                                                               |
| `TYP-0311` | All     | Assignment type mismatch                                                                               |
| `TYP-0312` | All     | Function call argument type mismatch                                                                   |
| `TYP-0313` | All     | Struct constructor field type mismatch                                                                 |
| `TYP-0314` | All     | Enum variant constructor field type mismatch                                                           |
| `TYP-0315` | All     | Return expression type mismatch                                                                        |
| `TYP-0316` | All     | Heap allocation initializer type mismatch                                                              |
| `TYP-0319` | All     | Internal default code for widening-context type mismatches                                             |
| `TYP-0360` | L1+     | Cannot assign to const binding                                                                         |
| `TYP-0700` | All     | Integer literal is outside the target integer type range                                               |
| `TYP-0701` | All     | Explicit nullable-pointer-to-pointer cast is provably null at compile time                             |
| `TYP-0702` | All     | Integer literal outside `int` requires a contextual integer type                                       |
| `TYP-0703` | All     | Integer literal outside `int` cannot be used in this contextual type                                   |
| `TYP-0760` | L1+     | Named arguments are not accepted by this callee or intrinsic                                           |
| `TYP-0761` | L1+     | Internal error: named argument label count mismatch                                                    |
| `TYP-0762` | L1+     | Unknown named argument                                                                                 |
| `TYP-0763` | L1+     | Duplicate named argument                                                                               |
| `TYP-0764` | L1+     | Missing required named argument                                                                        |
| `TYP-0780` | L1+     | Unsafe/plain function type mismatch                                                                    |
| `TYP-0800` | L1+     | Array length must be a positive `int` literal                                                          |
| `TYP-0801` | L1+     | Array literal requires a contextual array type                                                         |
| `TYP-0802` | L1+     | Array literal has more elements than the contextual target length                                      |
| `TYP-0803` | L1+     | Array literal element type mismatch                                                                    |
| `TYP-0804` | L1+     | Array constructor target must be an array type                                                         |
| `TYP-0805` | L1+     | Array constructor or allocation has invalid arity                                                      |
| `TYP-0806` | L1+     | Array scalar fill value type mismatch                                                                  |
| `TYP-0807` | L1+     | Unknown or ambiguous array constructor target type                                                     |
| `TYP-9209` | All     | Internal error: variant does not produce enum type                                                     |
| `TYP-9288` | All     | Internal error: 'new' outside function context                                                         |
| `TYP-9289` | All     | Internal error: missing module environment for the current function                                    |
