(module_declaration
  name: (module_path) @name) @definition.module

(function_declaration
  name: (identifier) @name) @definition.function

(extern_function_declaration
  name: (identifier) @name) @definition.function

(struct_declaration
  name: (identifier) @name) @definition.type

(enum_declaration
  name: (identifier) @name) @definition.type

(type_alias_declaration
  name: (identifier) @name) @definition.type

(enum_variant_declaration
  name: (identifier) @name) @definition.constant

(field_declaration
  name: (identifier) @name) @definition.field

(variant_field
  name: (identifier) @name) @definition.field

(global_let_declaration
  name: (identifier) @name) @definition.variable

(const_declaration
  name: (identifier) @name) @definition.constant

(call_expression
  function: (qualified_identifier) @name) @reference.call
