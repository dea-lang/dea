/**
 * @file Tree-sitter grammar for the Dea L0 and L1 languages
 * @author Guglielmo Nigri <googlielmo@gmail.com>
 * @license MIT OR Apache-2.0
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

const PREC = {
  LOGICAL_OR: 1,
  LOGICAL_AND: 2,
  BITWISE_OR: 3,
  BITWISE_XOR: 4,
  BITWISE_AND: 5,
  EQUALITY: 6,
  RELATIONAL: 7,
  SHIFT: 8,
  ADDITIVE: 9,
  MULTIPLICATIVE: 10,
  UNARY: 11,
  CAST: 12,
  POSTFIX: 13,
};

const BINARY_OPERATORS = [
  ["||", PREC.LOGICAL_OR],
  ["&&", PREC.LOGICAL_AND],
  ["|", PREC.BITWISE_OR],
  ["^", PREC.BITWISE_XOR],
  ["&", PREC.BITWISE_AND],
  ["==", PREC.EQUALITY],
  ["!=", PREC.EQUALITY],
  ["<", PREC.RELATIONAL],
  ["<=", PREC.RELATIONAL],
  [">", PREC.RELATIONAL],
  [">=", PREC.RELATIONAL],
  ["<<", PREC.SHIFT],
  [">>", PREC.SHIFT],
  ["+", PREC.ADDITIVE],
  ["-", PREC.ADDITIVE],
  ["*", PREC.MULTIPLICATIVE],
  ["/", PREC.MULTIPLICATIVE],
  ["%", PREC.MULTIPLICATIVE],
];

export default grammar({
  name: "dea",

  extras: $ => [
    /[\s\uFEFF]+/,
    $.line_comment,
    $.block_comment,
  ],

  word: $ => $.identifier,

  supertypes: $ => [
    $._declaration,
    $._statement,
    $._expression,
  ],

  conflicts: $ => [
    [$.module_path, $.qualified_identifier],
    [$._expression, $.type_expression],
  ],

  rules: {
    source_file: $ => seq(
      $.module_declaration,
      optional($.export_declaration),
      repeat($.import_declaration),
      repeat($._declaration),
    ),

    module_declaration: $ => seq(
      "module",
      field("name", $.module_path),
      ";",
    ),

    export_declaration: $ => seq(
      "export",
      choice(
        "*",
        commaSep1($.export_item),
      ),
      ";",
    ),

    export_item: $ => choice(
      field("name", $.identifier),
      $.opaque_export,
    ),

    opaque_export: $ => seq(
      "opaque",
      "{",
      commaSep1(field("name", $.identifier)),
      "}",
    ),

    import_declaration: $ => seq(
      "import",
      choice(
        seq(
          field("module", $.module_path),
          optional(seq("as", field("alias", $.identifier))),
        ),
        seq(
          commaSep1(field("name", $.identifier)),
          "from",
          field("module", $.module_path),
        ),
      ),
      ";",
    ),

    module_path: $ => seq(
      field("segment", $.identifier),
      repeat(seq(".", field("segment", $.identifier))),
    ),

    _declaration: $ => choice(
      $.function_declaration,
      $.extern_function_declaration,
      $.struct_declaration,
      $.enum_declaration,
      $.type_alias_declaration,
      $.global_let_declaration,
      $.const_declaration,
    ),

    function_declaration: $ => seq(
      optional("unsafe"),
      "func",
      field("name", $.identifier),
      field("parameters", $.parameter_list),
      optional(seq(
        "->",
        field("return_type", $.type),
      )),
      field("body", $.block),
    ),

    extern_function_declaration: $ => seq(
      optional("unsafe"),
      "extern",
      "func",
      field("name", $.identifier),
      field("parameters", $.parameter_list),
      optional(seq(
        "->",
        field("return_type", $.type),
      )),
      ";",
    ),

    parameter_list: $ => seq(
      "(",
      commaSep($.parameter),
      ")",
    ),

    parameter: $ => seq(
      field("name", $.identifier),
      ":",
      field("type", $.type),
      optional(field("variadic", "...")),
    ),

    struct_declaration: $ => seq(
      "struct",
      field("name", $.identifier),
      field("body", $.struct_body),
    ),

    struct_body: $ => seq(
      "{",
      repeat($.field_declaration),
      "}",
    ),

    field_declaration: $ => seq(
      field("name", $.identifier),
      ":",
      field("type", $.type),
      ";",
    ),

    enum_declaration: $ => seq(
      "enum",
      field("name", $.identifier),
      field("body", $.enum_body),
    ),

    enum_body: $ => seq(
      "{",
      repeat($.enum_variant_declaration),
      "}",
    ),

    enum_variant_declaration: $ => seq(
      field("name", $.identifier),
      optional(field("fields", $.variant_field_list)),
      ";",
    ),

    variant_field_list: $ => seq(
      "(",
      commaSep($.variant_field),
      ")",
    ),

    variant_field: $ => seq(
      field("name", $.identifier),
      ":",
      field("type", $.type),
    ),

    type_alias_declaration: $ => seq(
      "type",
      field("name", $.identifier),
      "=",
      field("type", $.type),
      ";",
    ),

    global_let_declaration: $ => seq(
      "let",
      field("name", $.identifier),
      optional(seq(":", field("type", $.type))),
      "=",
      field("value", $._expression),
      ";",
    ),

    const_declaration: $ => seq(
      "const",
      field("name", $.identifier),
      ":",
      field("type", $.type),
      "=",
      field("value", $._expression),
      ";",
    ),

    type: $ => prec.right(seq(
      field("base", choice(
        $.builtin_type,
        $.qualified_identifier,
        $.function_type,
        $.parenthesized_function_type,
      )),
      repeat(field("suffix", $.type_suffix)),
    )),

    function_type: $ => seq(
      optional("unsafe"),
      "func",
      field("parameters", $.function_type_parameter_list),
      "->",
      field("return_type", $.type),
    ),

    function_type_parameter_list: $ => seq(
      "(",
      commaSep($.function_type_parameter),
      ")",
    ),

    function_type_parameter: $ => seq(
      field("type", $.type),
      optional(field("variadic", "...")),
    ),

    parenthesized_function_type: $ => seq(
      "(",
      $.function_type,
      ")",
    ),

    type_suffix: $ => choice(
      $.pointer_type_suffix,
      $.array_type_suffix,
      $.slice_type_suffix,
      $.nullable_type_suffix,
    ),

    pointer_type_suffix: _ => "*",

    array_type_suffix: $ => seq(
      "[",
      field("length", choice(
        $.signed_integer_literal,
        $.qualified_identifier,
      )),
      "]",
    ),

    slice_type_suffix: _ => seq("[", "]"),

    nullable_type_suffix: _ => "?",

    builtin_type: _ => choice(
      "void",
      "bool",
      "string",
      "byte",
      "tiny",
      "short",
      "int",
      "long",
      "ushort",
      "uint",
      "ulong",
      "float",
      "double",
    ),

    qualified_identifier: $ => choice(
      field("name", $.identifier),
      seq(
        field("module", $.module_path),
        "::",
        field("name", $.identifier),
        repeat(seq("::", field("member", $.identifier))),
      ),
    ),

    block: $ => seq(
      "{",
      repeat($._statement),
      "}",
    ),

    _statement: $ => choice(
      $.block,
      $.if_statement,
      $.match_statement,
      $.case_statement,
      $.while_statement,
      $.for_statement,
      $.with_statement,
      $.simple_statement,
    ),

    simple_statement: $ => seq(
      $._simple_statement,
      ";",
    ),

    _simple_statement: $ => choice(
      $.let_statement,
      $.assignment_statement,
      $.break_statement,
      $.continue_statement,
      $.return_statement,
      $.drop_statement,
      $.expression_statement,
    ),

    let_statement: $ => seq(
      "let",
      field("name", $.identifier),
      optional(seq(":", field("type", $.type))),
      "=",
      field("value", $._expression),
    ),

    assignment_statement: $ => seq(
      field("left", $._expression),
      "=",
      field("right", $._expression),
    ),

    break_statement: _ => "break",

    continue_statement: _ => "continue",

    return_statement: $ => seq(
      "return",
      optional(field("value", $._expression)),
    ),

    drop_statement: $ => seq(
      "drop",
      field("value", $.identifier),
    ),

    expression_statement: $ => $._expression,

    if_statement: $ => prec.right(seq(
      "if",
      "(",
      field("condition", $._expression),
      ")",
      field("consequence", $._statement),
      optional(seq(
        "else",
        field("alternative", $._statement),
      )),
    )),

    while_statement: $ => seq(
      "while",
      "(",
      field("condition", $._expression),
      ")",
      field("body", $._statement),
    ),

    for_statement: $ => seq(
      "for",
      "(",
      optional(field("initializer", $._simple_statement)),
      ";",
      optional(field("condition", $._expression)),
      ";",
      optional(field("update", $._non_declaration_statement)),
      ")",
      field("body", $._statement),
    ),

    _non_declaration_statement: $ => choice(
      $.assignment_statement,
      $.break_statement,
      $.continue_statement,
      $.return_statement,
      $.drop_statement,
      $.expression_statement,
    ),

    match_statement: $ => seq(
      "match",
      "(",
      field("value", $._expression),
      ")",
      "{",
      repeat1($.match_arm),
      "}",
    ),

    match_arm: $ => seq(
      field("pattern", $.pattern),
      "=>",
      field("body", $._statement),
    ),

    pattern: $ => choice(
      $.variant_pattern,
      $.wildcard_pattern,
    ),

    variant_pattern: $ => seq(
      field("variant", $.qualified_identifier),
      optional(field("bindings", $.pattern_binding_list)),
    ),

    pattern_binding_list: $ => seq(
      "(",
      commaSep(field("name", $.identifier)),
      ")",
    ),

    wildcard_pattern: _ => "_",

    case_statement: $ => seq(
      "case",
      "(",
      field("value", $._expression),
      ")",
      "{",
      repeat($.case_arm),
      optional($.case_default_arm),
      "}",
    ),

    case_arm: $ => seq(
      field("value", $.case_arm_value),
      "=>",
      field("body", $._statement),
    ),

    case_arm_value: $ => choice(
      $.signed_integer_literal,
      $.signed_float_literal,
      $.byte_literal,
      $.string_literal,
      $.boolean_literal,
      $.qualified_identifier,
    ),

    case_default_arm: $ => seq(
      "_",
      "=>",
      field("body", $._statement),
    ),

    with_statement: $ => seq(
      "with",
      "(",
      commaSep1($.with_item),
      ")",
      field("body", $.block),
      optional(seq(
        "cleanup",
        field("cleanup", $.block),
      )),
    ),

    with_item: $ => seq(
      field("initialize", $._simple_statement),
      optional(seq(
        "=>",
        field("cleanup", $._simple_statement),
      )),
    ),

    _expression: $ => choice(
      $.integer_literal,
      $.float_literal,
      $.byte_literal,
      $.string_literal,
      $.boolean_literal,
      $.null_literal,
      $.builtin_type,
      $.qualified_identifier,
      $.array_literal,
      $.new_expression,
      $.parenthesized_expression,
      $.call_expression,
      $.index_expression,
      $.field_expression,
      $.try_expression,
      $.cast_expression,
      $.unary_expression,
      $.binary_expression,
    ),

    parenthesized_expression: $ => seq(
      "(",
      $._expression,
      ")",
    ),

    array_literal: $ => seq(
      "[",
      optional(seq(
        commaSep1($._expression),
        optional(","),
      )),
      "]",
    ),

    new_expression: $ => prec.right(PREC.POSTFIX, seq(
      "new",
      field("type", $.type),
      optional(field("arguments", $.argument_list)),
    )),

    call_expression: $ => prec.left(PREC.POSTFIX, seq(
      field("function", $._expression),
      field("arguments", $.argument_list),
    )),

    argument_list: $ => seq(
      "(",
      commaSep($.argument),
      ")",
    ),

    argument: $ => choice(
      $.named_argument,
      $.spread_argument,
      $.type_expression,
      $._expression,
    ),

    named_argument: $ => seq(
      field("name", $.identifier),
      ":",
      field("value", choice(
        $.type_expression,
        $._expression,
      )),
    ),

    spread_argument: $ => seq(
      field("value", $._expression),
      "...",
    ),

    type_expression: $ => choice(
      seq(
        field("base", $.builtin_type),
        repeat(field("suffix", $.type_suffix)),
      ),
      seq(
        field("base", $.qualified_identifier),
        repeat1(field("suffix", choice(
          $.pointer_type_suffix,
          $.nullable_type_suffix,
        ))),
      ),
    ),

    index_expression: $ => prec.left(PREC.POSTFIX, seq(
      field("value", $._expression),
      "[",
      field("index", $._expression),
      "]",
    )),

    field_expression: $ => prec.left(PREC.POSTFIX, seq(
      field("value", $._expression),
      ".",
      field("field", $.identifier),
    )),

    try_expression: $ => prec.left(PREC.POSTFIX, seq(
      field("value", $._expression),
      "?",
    )),

    cast_expression: $ => prec.left(PREC.CAST, seq(
      field("value", $._expression),
      "as",
      field("type", $.type),
    )),

    unary_expression: $ => prec.right(PREC.UNARY, seq(
      field("operator", choice("-", "!", "*", "~")),
      field("argument", $._expression),
    )),

    binary_expression: $ => choice(
      ...BINARY_OPERATORS.map(([operator, precedence]) =>
        prec.left(precedence, seq(
          field("left", $._expression),
          field("operator", operator),
          field("right", $._expression),
        )),
      ),
    ),

    signed_integer_literal: $ => choice(
      $.integer_literal,
      seq("-", $.integer_literal),
    ),

    signed_float_literal: $ => choice(
      $.float_literal,
      seq("-", $.float_literal),
    ),

    integer_literal: _ => token(choice(
      /0[bB][01]+/,
      /0[oO][0-7]+/,
      /0[xX][0-9A-Fa-f]+/,
      /[0-9]+/,
    )),

    float_literal: _ => token(choice(
      /[0-9]+\.[0-9]+([eE][+-]?[0-9]+)?[fF]?/,
      /[0-9]+[eE][+-]?[0-9]+[fF]?/,
    )),

    byte_literal: $ => seq(
      "'",
      choice(
        $.escape_sequence,
        alias(token.immediate(/[^'\\\r\n]/), $.byte_content),
      ),
      "'",
    ),

    string_literal: $ => seq(
      '"',
      repeat(choice(
        $.escape_sequence,
        $.string_content,
      )),
      '"',
    ),

    string_content: _ => token.immediate(prec(1, /[^"\\\r\n]+/)),

    escape_sequence: _ => token.immediate(seq(
      "\\",
      choice(
        /["\\?abfnrtv']/,
        /[0-7]{1,3}/,
        /x[0-9A-Fa-f]+/,
        /u[0-9A-Fa-f]{4}/,
        /U[0-9A-Fa-f]{8}/,
      ),
    )),

    boolean_literal: _ => choice("true", "false"),

    null_literal: _ => "null",

    identifier: _ => /[A-Za-z_][A-Za-z0-9_]*/,

    line_comment: _ => token(seq("//", /[^\r\n]*/)),

    block_comment: _ => token(seq(
      "/*",
      /[^*]*\*+([^/*][^*]*\*+)*/,
      "/",
    )),
  },
});

/**
 * Match zero or more comma-separated instances of a rule.
 *
 * @param {Rule} rule
 * @returns {ChoiceRule}
 */
function commaSep(rule) {
  return optional(commaSep1(rule));
}

/**
 * Match one or more comma-separated instances of a rule.
 *
 * @param {Rule} rule
 * @returns {SeqRule}
 */
function commaSep1(rule) {
  return seq(rule, repeat(seq(",", rule)));
}
