# Dea/L<sub>1</sub> Grammar

Version: 2026-06-08

The following is the formal grammar for the Dea/L<sub>1</sub> programming language in EBNF-style. This describes the
concrete syntax that lexers and parsers should accept.

## 1. Lexical structure

### 1.1 Identifiers

```ebnf
Ident           ::=     Letter (Letter | Digit | "_")*

Letter          ::=     "A".."Z" | "a".."z" | "_"
Digit           ::=     "0".."9"
BinDigit        ::=     "0" | "1"
OctDigit        ::=     "0".."7"
HexDigit        ::=     "0".."9" | "A".."F" | "a".."f"
```

### 1.2 Literals

```ebnf
IntLiteral          ::=     ( "-" )? Digit+
                      |     ( "-" )? "0b" BinDigit+
                      |     ( "-" )? "0o" OctDigit+
                      |     ( "-" )? "0x" HexDigit+

BoolLiteral         ::=     "true" | "false"

FloatLiteral        ::=     ( "-" )? Digit+ "." Digit+ ( ExponentPart )? ( TypeSuffix )?
                      |     ( "-" )? Digit+ ExponentPart ( FTypeSuffix )?
ExponentPart        ::=     ( "e" | "E" ) ( "+" | "-" )? Digit+
FTypeSuffix         ::=     "f" | "F"

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

Note: ambiguity between `-` as a unary operator and as part of a negative literal is resolved in context by the lexer.

### 1.3 Keywords

Reserved words (not valid as identifiers):

```text
module export import from func struct enum type extern let const
return match case if else while for break continue in with cleanup
true false null as new drop void bool string
byte tiny short int long ushort uint ulong float double
```

Builtin type names such as `void`, `bool`, `string`, `byte`, `tiny`, `short`, `int`, `long`, `ushort`, `uint`, `ulong`,
`float`, and `double` are reserved. The grammar is prescriptive here and may intentionally lead the current bootstrap
implementation. In addition, `in` remains reserved for a future extension.

### 1.4 Symbols / operators

```text
{ } ( ) [ ] ; , : . ::
-> => 
= == != < <= > >=
+ - * / %
&& || !
& | ^ ~ << >>
?   (* used in types and as postfix try operator *)
```

Note: the current bootstrap implementation uses `&` only as the binary bitwise-AND operator. No forward-looking design
decision has been made yet on whether prefix address-of will become part of the L<sub>1</sub> language surface. Postfix
indexing syntax is part of the current surface: `ptr[index]` is the raw-pointer indexing form, accepted only in
`unsafe func` bodies, with `int` indexes and direct unchecked lowering for sized non-`void` pointee types. `arr[index]`
on fixed-size arrays is safe, bounds checked, and also requires an `int` index.

### 1.5 Special identifier `_`

The single identifier `_` is tokenized as a dedicated `UNDERSCORE` token and used only as the wildcard pattern. It is
not a normal Ident in patterns.

Line comments: `// ...` until end of line. Whitespace: spaces, tabs, newlines, carriage returns are skipped.

## 2. Top-level structure

One file corresponds to one module, path names are dot-separated.

```ebnf
CompilationUnit     ::=     ModuleDecl ExportDecl? ImportDecl* TopLevelDecl*

ModuleDecl          ::=     "module" ModulePath ";"

ExportDecl          ::=     "export" "*" ";"
                      |     "export" IdentList ";"

ImportDecl          ::=     "import" ModulePath ";"
                      |     "import" ModulePath "as" Ident ";"
                      |     "import" IdentList "from" ModulePath ";"

ModulePath          ::=     Ident ("." Ident)*

IdentList           ::=     Ident ("," Ident)*
```

`Ident` here is the module name component (no hierarchical packages in L<sub>1</sub> beyond dot-separated modules). This
implies each module path component must be a valid identifier; hyphens and leading digits are not valid.

Semantic notes:

- `export *;` exports every top-level symbol, including names beginning with `_`. `export a, b;` exports only the named
  top-level symbols. If no export manifest is present, all top-level names except `_`-prefixed names are exported.
- Plain `import module.path;` opens the imported module's export set into the current module and permits
  `module.path::name` lookup. `import module.path as alias;` binds only the `alias::name` namespace.
  `import a, b from module.path;` binds only the named exports as unqualified imports.
- Intrinsic availability and the implicit `dea` prelude are semantic behavior, not grammar extensions. See
  `design-decisions.md` for the current prelude/import rules.

## 3. Top-level declarations

```ebnf
TopLevelDecl        ::=     FunctionDecl
                      |     UnsafeFunctionDecl
                      |     StructDecl
                      |     EnumDecl
                      |     TypeAliasDecl
                      |     ExternFuncDecl
                      |     LetDecl
                      |     ConstDecl
```

### 3.1 Functions

```ebnf
FunctionDecl        ::=     "func" Ident "(" ParamList? ")" "->" Type Block
UnsafeFunctionDecl  ::=     "unsafe" ( "func" Ident "(" ParamList? ")" "->" Type Block
                                     | "extern" "func" Ident "(" ParamList? ")" "->" Type ";" )

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

### 3.6 Top-level bindings

```ebnf
LetDecl             ::=     "let" Ident ( ":" Type )? "=" Expr ";"

ConstDecl           ::=     "const" Ident ":" Type "=" Expr ";"
```

`const` is currently top-level only. Block-local `let` exists; block-local `const` is not part of the current accepted
syntax.

## 4. Types

L<sub>1</sub> has simple named types, function pointer types, and source-ordered pointer, nullable, and fixed-size array
suffixes.

```ebnf
Type                ::=     UnsuffixedType TypeSuffix*

UnsuffixedType      ::=     SimpleType
                      |     FuncPointerType
                      |     "(" FuncPointerType ")"     (* useful before nullable suffixes *)
SimpleType          ::=     QualifiedIdent
FuncPointerType     ::=     ( "unsafe" )? "func" "(" TypeList? ")" "->" Type
TypeList            ::=     Type ("," Type)*
TypeSuffix          ::=     PointerSuffix | ArraySuffix | NullableSuffix
PointerSuffix       ::=     "*"
ArraySuffix         ::=     "[" IntLiteral "]"
NullableSuffix      ::=     "?"     (* applies to the preceding type syntactically *)

QualifiedIdent      ::=     Ident
                      |     ModulePath "::" Ident
                      |     ModulePath "::" Ident ( "::" Ident )+   (* parsed, rejected semantically *)
```

Note: multi-segment `::` paths (e.g. `color::Color::Red`) are consumed by the parser to avoid confusing leftover-token
errors, but are rejected during semantic analysis with a diagnostic suggesting the correct single-`::` form.

Examples (all syntactically valid types in L<sub>1</sub>):

- `string`
- `Expr*`
- `Expr**`
- `int[3]`
- `int*[2]`
- `int[2]*`
- `int[2][3]`
- `int?`
- `int?*`
- `int??`
- `Expr*?`
- `Expr*??`
- `func(int, bool) -> int`
- `unsafe func(byte*) -> int`
- `(func() -> void)?`

Fixed-size array lengths must be positive `int` literals. Adjacent array suffixes preserve source-order dimensions:
`int[2][3]` is two rows of three `int` values. Exact semantic rules (e.g. when `?` is allowed) are enforced in the type
checker, not in the grammar.

Type suffixes apply left-to-right and build an ordered constructor stack. `T?*` is a pointer to an optional `T`; `T*?`
is an optional pointer to `T`; `T??` is an optional optional `T` and is not collapsed by the type system. `void*` is
valid, but `void?` and `void?*` are rejected because `void` is not a value object.

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
                  |     AssignStmt
                  |     BreakStmt
                  |     ContinueStmt
                  |     ReturnStmt
                  |     Expr
```

### 5.1 Variable declarations

```ebnf
LetStmt     ::=     "let" Ident ( ":" Type )? "=" Expr
```

### 5.2 Assignments

Assignments are statements only in L<sub>1</sub>; `=` does not appear as an expression operator.

```ebnf
AssignStmt      ::=     LValue "=" Expr 

LValue          ::=     PrimaryExpr ( PostfixOp )*
                        (* Must resolve to an assignable location; checked semantically. *)
```

### 5.3 Conditionals and loops

```ebnf
IfStmt          ::=     "if" "(" Expr ")" Stmt ( "else" Stmt )?

WhileStmt       ::=     "while" "(" Expr ")" Stmt

ForStmt         ::=     "for" "(" ( SimpleStmt )? ";" ( Expr )? ";" ( SimpleStmt )? ")" Stmt

BreakStmt       ::=     "break" 

ContinueStmt    ::=     "continue" 
```

### 5.4 Return

```ebnf
ReturnStmt      ::=     "return" ( Expr )? 
```

### 5.5 Match (statement-only in L<sub>1</sub>)

```ebnf
MatchStmt       ::=     "match" "(" Expr ")" "{" ( MatchArm )+ "}"

MatchArm        ::=     Pattern "=>" Stmt
```

### 5.6 Case (scalar/string dispatch)

```ebnf
CaseStmt        ::=     "case" "(" Expr ")" "{" CaseArm* WildcardArm? "}"

CaseArm         ::=     CaseLiteral "=>" Stmt

WildcardArm     ::=     "_" "=>" Stmt

CaseLiteral     ::=     IntLiteral | ByteLiteral | StringLiteral | BoolLiteral
```

Patterns (current L<sub>1</sub> bootstrap subset):

```ebnf
Pattern             ::=     VariantPattern | WildcardPattern

VariantPattern      ::=     QualifiedIdent ( "(" ( PatternVarList )? ")" )?
PatternVarList      ::=     Ident ( "," Ident )*

WildcardPattern     ::=     "_"
```

No literal patterns, nested patterns, or or-patterns in the current L<sub>1</sub> bootstrap surface.

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

L<sub>1</sub> expressions are side-effectful, but assignment is not an expression.

Precedence (from lowest to highest):

01. `||`
02. `&&`
03. `|` (bitwise OR)
04. `^` (bitwise XOR)
05. `&` (bitwise AND)
06. `==`, `!=`
07. `<`, `<=`, `>`, `>=`
08. `<<`, `>>`
09. `+`, `-`
10. `*`, `/`, `%`
11. unary `-`, `!`, `*`, `~`
12. postfix call/index/field/try

There is **no** ternary `?:` operator in L<sub>1</sub>.

Bitwise operators follow the C-family ordering shown here: shifts bind tighter than relational operators, and unary `~`
shares the ordinary unary-precedence level with `-`, `!`, and dereference `*`.

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

MulExpr             ::=     UnaryExpr ( ( "*" | "/" | "%" ) UnaryExpr )*

UnaryExpr           ::=     ( "-" | "!" | "*" | "~" ) UnaryExpr
                      |     CastExpr

CastExpr            ::=     PostfixExpr ( "as" Type )?

PostfixExpr         ::=     PrimaryExpr ( PostfixOp )*

PostfixOp           ::=     "(" ( ArgList )? ")"    (* function call *)
                      |     "[" Expr "]"            (* indexing *)
                      |     "." Ident               (* field access *)
                      |     "?"                     (* try / optional chaining *)

ArgList             ::=     Arg ( "," Arg )*

Arg                 ::=     Ident ":" ArgValue
                      |     ArgValue

ArgValue            ::=     TypeExpr
                      |     Expr

TypeExpr            ::=     BuiltinTypeName TypeSuffix*
                      |     QualifiedIdent PointerNullableSuffix+
PointerNullableSuffix
                    ::=     PointerSuffix | NullableSuffix

BuiltinTypeName     ::=     "tiny" | "short" | "int" | "long"
                      |     "byte" | "ushort" | "uint" | "ulong"
                      |     "float" | "double" | "bool" | "string" | "void"

PrimaryExpr         ::=     IntLiteral
                      |     FloatLiteral
                      |     ByteLiteral
                      |     StringLiteral
                      |     BoolLiteral
                      |     ArrayLiteral
                      |     ArrayConstructor
                      |     QualifiedIdent
                      |     "new" Type ( "(" ArgList? ")" )?
                      |     "(" Expr ")"

ArrayLiteral        ::=     "[" ( Expr ( "," Expr )* ","? )? "]"
ArrayConstructor    ::=     TypeWithArraySuffix "(" Expr ")"
TypeWithArraySuffix ::=     UnsuffixedType TypeSuffix* ArraySuffix TypeSuffix*
```

Notes:

- `QualifiedIdent` in expressions resolves to a module-qualified symbol reference. The module must be imported.
- `Ident` as a primary expression is a simple variable reference. When the identifier resolves to a zero-argument enum
  variant, it acts as a constructor (e.g. `Red` is equivalent to `Red()`).
- `as` casts support `T?` \<-> `T` conversion. Integer casts may also target nullable integer types when the same cast
  to the nullable inner type is valid, such as `0 as ulong?`.
- Type suffixes apply left-to-right. `T?*`, `T*?`, and `T??` are distinct types.
- The `?` type suffix denotes nullable types in the `Type` grammar.
- `?` as a postfix operator is the **null propagation operator** (also known as the **try operator**).
- `TypeExpr` allows types in argument position for intrinsics such as `sizeof(int*)` a.k.a. `dea::sizeof(int*)`.
- Call and `new` argument lists must be all positional or all named. Named arguments are accepted for function calls,
  struct constructors, and enum-variant constructors; labels are checked semantically against the required parameter,
  field, or payload names.
- Array literals require a contextual `T[N]` type. Short literals zero/default-pad trailing elements; overlong literals
  are rejected.
- Array constructors are restricted to array type calls such as `int[3]([1, 2])` or `byte[1024](0xFF)`. Fill arguments
  have the outer array's element type, so `int[10][20]([1, 2, 3])` broadcasts one contextually-built `int[20]` row.
- A `TypeExpr` is syntactically unambiguous in call arguments: either a builtin type name, or an identifier (including a
  qualified name) followed by one or more `*`/`?` suffixes that end at an argument boundary (`,` or `)`).
- Builtin type expressions may include array suffixes, such as `sizeof(int[4])`. Qualified identifier array suffixes are
  parsed as value indexing first, so `value[index]` in a call argument remains value indexing. The `sizeof` semantic
  path recognizes `TypeName[4]`-shaped arguments as array type expressions when the base resolves to a type name.
- Plain identifiers like `sizeof(Point)` parse as `Expr`; the type checker resolves whether `Point` refers to a type or
  variable.
- Calls to `sizeof`, `ord`, and `is` are parsed as ordinary function calls. Semantic analysis then resolves whether the
  callee is one of the implicit `dea` prelude symbols or an ordinary user-defined function.
