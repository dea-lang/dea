# Dea/L<sub>0</sub> Grammar

Version: 2026-08-25

The following is the formal grammar for the Dea/L<sub>0</sub> programming language in EBNF-style. This describes the
concrete syntax that lexers and parsers should accept.

## 1. Lexical structure

### 1.1 Identifiers

```ebnf
Ident           ::=     Letter (Letter | Digit | "_")*

Letter          ::=     "A".."Z" | "a".."z" | "_"
Digit           ::=     "0".."9"
OctDigit        ::=     "0".."7"
HexDigit        ::=     "0".."9" | "A".."F" | "a".."f"
```

`Ident` is ASCII-only. `Letter` and `Digit` are limited to the ranges shown above; non-ASCII Unicode characters are not
part of identifiers even though Dea source files are UTF-8. See
[docs/specs/language/source-text-and-language-vocabulary.md](../../../docs/specs/language/source-text-and-language-vocabulary.md).

### 1.2 Literals

```ebnf
IntLiteral          ::=     ( "-" )? Digit+ (* ambiguity with unary minus operator resolved in context by the lexer *)

BoolLiteral         ::=     "true" | "false"

ByteLiteral         ::=     "'" SingleByteChar "'"
SingleByteChar      ::=     '\' EscapedChar
                      |     any character except '\', "'" or newline (* must fit in one byte *)

StringLiteral       ::=     '"' StringChar* '"'
StringChar          ::=     '\' EscapedChar
                      |     any character except '\', '"' or newline (* multi-byte UTF-8 allowed *)

Oct1to3             ::=     OctDigit ( OctDigit ( OctDigit )? )?
Hex4                ::=     HexDigit HexDigit HexDigit HexDigit
Hex8                ::=     Hex4 Hex4
EscapedChar         ::=     '"' | '\' | 'n' | 't' | 'r' | "'" | Oct1to3
                      |     'u' Hex4 | 'U' Hex8 | 'x' HexDigit HexDigit*
```

String literal payload text may contain Unicode characters encoded as UTF-8, subject to the delimiter and escape rules
above. Comments may also contain Unicode text valid under the source encoding. Outside those free-text regions, the
language vocabulary remains ASCII-only.

### 1.3 Keywords

Reserved words (not valid as identifiers):

```text
module import func struct enum type extern let const
return match case if else while for break continue in with cleanup
true false null as new drop void bool string int byte
tiny short long ushort uint ulong float double
```

Builtin type names such as `void`, `bool`, `string`, `int`, and `byte` are reserved. In addition, `tiny`, `short`,
`long`, `ushort`, `uint`, `ulong`, `float`, and `double` are reserved for future extensions.

### 1.4 Symbols / operators

```text
{ } ( ) [ ] ; , : . ::
-> => 
= == != < <= > >=
+ - * /
&& || !
& | ^ ~ << >> (* reserved; deferred to Dea/L1 *)
?   (* used in types and as postfix try operator *)
```

### 1.5 Special identifier `_`

The single identifier `_` is tokenized as a dedicated `UNDERSCORE` token and used only as the wildcard pattern. It is
not a normal Ident in patterns.

Line comments: `// ...` until end of line. Whitespace: spaces, tabs, newlines, carriage returns are skipped.

## 2. Top-level structure

One file corresponds to one module, path names are dot-separated.

```ebnf
CompilationUnit     ::=     ModuleDecl ImportDecl* TopLevelDecl*

ModuleDecl          ::=     "module" ModulePath ";"

ImportDecl          ::=     "import" ModulePath ";"

ModulePath          ::=     Ident ("." Ident)*
```

`Ident` here is the module name component (no hierarchical packages in L<sub>0</sub> beyond dot-separated modules). This
implies each module path component must be a valid identifier; hyphens and leading digits are not valid.

## 3. Top-level declarations

```ebnf
TopLevelDecl        ::=     FunctionDecl
                      |     StructDecl
                      |     EnumDecl
                      |     TypeAliasDecl
                      |     ExternFuncDecl
```

### 3.1 Functions

```ebnf
FunctionDecl        ::=     "func" Ident "(" ParamList? ")" "->" Type Block

ParamList           ::=     Param ("," Param)*
Param               ::=     Ident ":" Type
```

### 3.2 Extern functions

```ebnf
ExternFuncDecl      ::=     "extern" "func" Ident "(" ParamList? ")" "->" Type ";"
```

Extern functions have no body; they declare functions implemented in the runtime.

### 3.3 Structs

```ebnf
StructDecl      ::=     "struct" Ident "{" FieldDecl* "}"

FieldDecl       ::=     Ident ":" Type ";"
```

### 3.4 Enums (sum types)

```ebnf
EnumDecl                ::=     "enum" Ident "{" EnumVariantDecl* "}"

EnumVariantDecl         ::=     Ident VariantFields? ";"

VariantFields           ::=     "(" VariantFieldList? ")"
VariantFieldList        ::=     VariantField ("," VariantField)*

VariantField            ::=     Ident ":" Type
```

Each variant may have zero or more named payload fields.

### 3.5 Type aliases

```ebnf
TypeAliasDecl ::= "type" Ident "=" Type ";"
```

Used for things like `type RawPtr = void*;`.

## 4. Types

L<sub>0</sub> has simple named types, pointer suffixes, and an optional nullable suffix.

```ebnf
Type                ::=     SimpleType PointerSuffix* NullableSuffix?

SimpleType          ::=     QualifiedIdent
PointerSuffix       ::=     "*"
NullableSuffix      ::=     "?"     (* applies to the preceding type syntactically *)

QualifiedIdent      ::=     Ident
                      |     ModulePath "::" Ident
                      |     ModulePath "::" Ident ( "::" Ident )+   (* parsed, rejected semantically *)
```

Note: multi-segment `::` paths (e.g. `color::Color::Red`) are consumed by the parser to avoid confusing leftover-token
errors, but are rejected during semantic analysis with a diagnostic suggesting the correct single-`::` form.

Examples (all syntactically valid types in L<sub>0</sub>):

- `string`
- `Expr*`
- `Expr**`
- `int?`
- `Expr*?`

Exact semantic rules (e.g. when `?` is allowed) are enforced in the type checker, not in the grammar.

## 5. Blocks and statements

```ebnf
Block           ::=     "{" Stmt* "}"

Stmt            ::=     Block
                  |     IfStmt
                  |     MatchStmt
                  |     CaseStmt
                  |     WhileStmt
                  |     ForStmt
                  |     WithStmt
                  |     SimpleStmt ";"

SimpleStmt      ::=     LetStmt
                  |     NonDeclStmt

NonDeclStmt     ::=     AssignStmt
                  |     BreakStmt
                  |     ContinueStmt
                  |     ReturnStmt
                  |     DropStmt
                  |     Expr

DropStmt        ::=     "drop" Ident
```

### 5.1 Variable declarations

```ebnf
LetStmt     ::=     "let" Ident ( ":" Type )? "=" Expr
```

### 5.2 Assignments

Assignments are *statements only* in L<sub>0</sub>; `=` does not appear as an expression operator.

```ebnf
AssignStmt      ::=     LValue "=" Expr 

LValue          ::=     PrimaryExpr ( PostfixOp )*
                        (* Must resolve to an assignable location; checked semantically. *)
```

### 5.3 Conditionals and loops

```ebnf
IfStmt          ::=     "if" "(" Expr ")" Stmt ( "else" Stmt )?

WhileStmt       ::=     "while" "(" Expr ")" Block

ForStmt         ::=     "for" "(" ( ForInitStmt )? ";" ( Expr )? ";" ( ForUpdateStmt )? ")" Block

ForInitStmt     ::=     SimpleStmt

ForUpdateStmt   ::=     NonDeclStmt

BreakStmt       ::=     "break" 

ContinueStmt    ::=     "continue" 
```

The initialization and update clauses execute in the surrounding loop context. A `break` or `continue` in either clause
therefore targets an enclosing loop and is invalid when no enclosing loop exists. Only the body belongs to the new `for`
loop. The update clause excludes `let` declarations but otherwise accepts every non-declaration simple statement.
Definite-return analysis remains conservative: loop bodies do not prove that a function returns on every path, even for
syntactically infinite loops such as `while (true)` or `for (;;)`.

### 5.4 Return

```ebnf
ReturnStmt      ::=     "return" ( Expr )? 
```

### 5.5 Match (statement-only in L<sub>0</sub>)

```ebnf
MatchStmt       ::=     "match" "(" Expr ")" "{" ( MatchArm )+ "}"

MatchArm        ::=     Pattern "=>" Block
```

### 5.6 Case (scalar/string dispatch)

```ebnf
CaseStmt        ::=     "case" "(" Expr ")" "{" CaseArm* WildcardArm? "}"

CaseArm         ::=     CaseLiteral "=>" Stmt

WildcardArm     ::=     "_" "=>" Stmt

CaseLiteral     ::=     IntLiteral | ByteLiteral | StringLiteral | BoolLiteral
```

`_ =>` is the sole `case` default-arm spelling, mirrors the `match` wildcard arm, and may appear at most once.

Patterns (L<sub>0</sub> subset):

```ebnf
Pattern             ::=     VariantPattern | WildcardPattern

VariantPattern      ::=     QualifiedIdent ( "(" ( PatternVarList )? ")" )?
PatternVarList      ::=     Ident ( "," Ident )*

WildcardPattern     ::=     "_"
```

No literal patterns, nested patterns, or or-patterns in L<sub>0</sub>.

### 5.6 With (deterministic resource cleanup)

```ebnf
WithStmt        ::=     "with" "(" WithItemList ")" Block
                  |     "with" "(" WithItemList ")" Block "cleanup" Block

WithItemList    ::=     WithItem ( "," WithItem )*

WithItem        ::=     SimpleStmt "=>" SimpleStmt        (* inline cleanup *)
                  |     SimpleStmt                        (* cleanup-block form *)
```

Constraints enforced by the parser:

- All items must use `=>` (inline form) or none (cleanup-block form); mixing is rejected.
- The inline form (`=>`) and the `cleanup` block are mutually exclusive.
- When no items use `=>`, a trailing `cleanup` block is required.

Inline cleanup statements are executed in LIFO (reverse declaration) order.

Cleanup is guaranteed to run at block end and before any early exit (`return`, `break`, `continue`) from the body.

Cleanup statements are also guaranteed to run before any early exit from header initializers, including short-circuits
via `?` if the header expressions use that operator.

For the inline form, header statements are evaluated in declaration order, and if a header statement short-circuits via
`?` only the cleanup statements corresponding to successfully completed header statements are run.

Additional `cleanup`-block safety rule, enforced by the type checker:

- If header initializers may short-circuit via `?`, cleanup must not reference non-nullable header variables that may be
  uninitialized on those failure paths. Use nullable header types for variables that cleanup needs to inspect.

## 6. Expressions

L<sub>0</sub> expressions are side-effectful, but assignment is not an expression.

Precedence (from lowest to highest):

01. `||`
02. `&&`
03. `|` (bitwise OR)
04. `^` (bitwise XOR)
05. `&` (bitwise AND)
06. `==`, `!=`
07. `<`, `<=`, `>`, `>=`
08. `+`, `-`
09. `*`, `/`
10. unary `-`, `!`, `*`, `~`
11. postfix call/index/field/try

There is **no** ternary `?:` operator in L<sub>0</sub>.

```ebnf
Expr                ::=     OrExpr

OrExpr              ::=     AndExpr ( "||" AndExpr )*

AndExpr             ::=     BitOrExpr ( "&&" BitOrExpr )*

BitOrExpr           ::=     BitXorExpr ( "|" BitXorExpr )*
BitXorExpr          ::=     BitAndExpr ( "^" BitAndExpr )*
BitAndExpr          ::=     EqualityExpr ( "&" EqualityExpr )*

EqualityExpr        ::=     RelExpr ( ( "==" | "!=" ) RelExpr )*

RelExpr             ::=     ShiftExpr ( ( "<" | "<=" | ">" | ">=" ) ShiftExpr )*

ShiftExpr           ::=     AddExpr ( ( "<<" | ">>" ) AddExpr )*

AddExpr             ::=     MulExpr ( ( "+" | "-" ) MulExpr )*

MulExpr             ::=     UnaryExpr ( ( "*" | "/" ) UnaryExpr )*

UnaryExpr           ::=     ( "-" | "!" | "~" ) UnaryExpr
                      |     CastExpr

CastExpr            ::=     PostfixExpr ( "as" Type )?

PostfixExpr         ::=     PrimaryExpr ( PostfixOp )*

PostfixOp           ::=     "(" ( ArgList )? ")"    (* function call *)
                      |     "[" Expr "]"            (* indexing *)
                      |     "." Ident               (* field access *)
                      |     "?"                     (* try / optional chaining *)

ArgList             ::=     Arg ( "," Arg )*

Arg                 ::=     TypeExpr
                      |     Expr

TypeExpr            ::=     BuiltinTypeName ( "*" )* ( "?" )?
                      |     QualifiedIdent ( "*" )+ ( "?" )?

BuiltinTypeName     ::=     "int" | "byte" | "bool" | "string" | "void"

PrimaryExpr         ::=     IntLiteral
                      |     ByteLiteral
                      |     StringLiteral
                      |     BoolLiteral
                      |     QualifiedIdent
                      |     "new" Type ( "(" ArgList? ")" )?
                      |     "(" Expr ")"
```

Notes:

- `QualifiedIdent` in expressions resolves to a module-qualified symbol reference. The module must be imported.
- `Ident` as a primary expression is a simple variable reference. When the identifier resolves to a zero-argument enum
  variant, it acts as a constructor (e.g. `Red` is equivalent to `Red()`).
- `as` casts support `T?` \<-> `T` conversion.
- The `?` type suffix denotes nullable types in the `Type` grammar.
- `?` as a postfix operator is the **null propagation operator** (also known as the **try operator**).
- `TypeExpr` allows types in argument position for intrinsics like `sizeof(int*)`.
- A `TypeExpr` is syntactically unambiguous: either a builtin type name, or an identifier (including a qualified name)
  followed by `*` or `?` suffixes that end at an argument boundary (`,` or `)`).
- Plain identifiers like `sizeof(Point)` parse as `Expr`; the type checker resolves whether `Point` refers to a type or
  variable.
- Intrinsics such as `sizeof` and `ord` are parsed as ordinary identifiers and given special meaning during semantic
  analysis and lowering.

This grammar is intended to be just expressive enough to:

- Write the compiler and standard library in L<sub>0</sub>.
- Avoid undefined behavior at the language level.
- Keep the lexer/parser implementation straightforward.
