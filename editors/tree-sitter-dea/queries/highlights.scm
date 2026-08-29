; Comments and literals

[
  (line_comment)
  (block_comment)
] @comment

(string_literal) @string
(byte_literal) @string
(escape_sequence) @string.escape
(integer_literal) @number
(float_literal) @number
(boolean_literal) @boolean
(null_literal) @constant.builtin
(wildcard_pattern) @constant.builtin

(case_default_arm
  "_" @constant.builtin)

; Types and declarations

(builtin_type) @type.builtin

(struct_declaration
  name: (identifier) @type)

(enum_declaration
  name: (identifier) @type)

(type_alias_declaration
  name: (identifier) @type)

(function_declaration
  name: (identifier) @function)

(extern_function_declaration
  name: (identifier) @function)

(parameter
  name: (identifier) @variable.parameter)

(function_type_parameter) @type

(field_declaration
  name: (identifier) @property)

(variant_field
  name: (identifier) @property)

(enum_variant_declaration
  name: (identifier) @constructor)

(pattern_binding_list
  name: (identifier) @variable)

(variant_pattern
  variant: (qualified_identifier) @constructor)

; Modules, calls, and member access

(module_declaration
  name: (module_path) @module)

(import_declaration
  module: (module_path) @module)

(call_expression
  function: (qualified_identifier) @function)

(call_expression
  function: (field_expression
    field: (identifier) @function))

(field_expression
  field: (identifier) @property)

(named_argument
  name: (identifier) @variable.parameter)

; Keywords and operators

[
  "module"
  "export"
  "opaque"
  "import"
  "from"
  "func"
  "struct"
  "enum"
  "type"
  "extern"
  "unsafe"
  "let"
  "const"
  "return"
  "match"
  "case"
  "if"
  "else"
  "while"
  "for"
  "with"
  "cleanup"
  "drop"
  "new"
] @keyword

[
  (break_statement)
  (continue_statement)
] @keyword

"as" @keyword

[
  "->"
  "=>"
  "="
  "=="
  "!="
  "<"
  "<="
  ">"
  ">="
  "+"
  "-"
  "*"
  "/"
  "%"
  "&&"
  "||"
  "!"
  "&"
  "|"
  "^"
  "~"
  "<<"
  ">>"
  "?"
  "..."
] @operator

[
  "("
  ")"
  "["
  "]"
  "{"
  "}"
] @punctuation.bracket

[
  ","
  "."
  ":"
  "::"
  ";"
] @punctuation.delimiter
