" Vim syntax file
" Language: Dea/L0
" SPDX-License-Identifier: MIT OR Apache-2.0
" Copyright (c) 2026 gwz

if exists("b:current_syntax")
  finish
endif

syntax case match

syntax keyword deaTodo TODO FIXME XXX NOTE contained
syntax region deaBlockComment start="/\*" end="\*/" contains=deaTodo,@Spell
syntax region deaDocComment start="/\*\*" end="\*/" contains=deaTodo,deaDocTag,@Spell
syntax match deaDocTag "@[A-Za-z_][A-Za-z0-9_]*" contained
syntax match deaLineComment "//.*$" contains=deaTodo,@Spell

syntax match deaEscape "\\\%([\"'\\ntr]\|[0-7]\{1,3}\|u[0-9A-Fa-f]\{4}\|U[0-9A-Fa-f]\{8}\|x[0-9A-Fa-f]\+\)" contained
syntax region deaString start=+"+ skip=+\\\\\|\\"+ end=+"+ oneline contains=deaEscape
syntax region deaByte start=+'+ skip=+\\\\\|\\'+ end=+'+ oneline contains=deaEscape

syntax match deaNumber "\<[0-9]\+\>"
syntax keyword deaBoolean true false
syntax keyword deaNull null
syntax match deaWildcard "\<_\>"

syntax keyword deaDeclaration module import func struct enum type extern
syntax keyword deaStorage let const
syntax keyword deaControl return match case if else while for break continue with cleanup
syntax keyword deaOperatorWord as new drop
syntax keyword deaReserved in
syntax keyword deaBuiltinType void bool string byte tiny short int long ushort uint ulong float double

syntax match deaQualifiedName "\<[A-Za-z_][A-Za-z0-9_.]*::[A-Za-z_][A-Za-z0-9_:]*\>"
syntax match deaFunction "\<[A-Za-z_][A-Za-z0-9_]*\>\ze\s*("
syntax match deaTypeName "\<[A-Z][A-Za-z0-9_]*\>"
syntax match deaOperator "->\|=>\|==\|!=\|<=\|>=\|&&\|||\|<<\|>>\|[=<>+\-*/%&|^~!?]"

highlight default link deaTodo Todo
highlight default link deaBlockComment Comment
highlight default link deaDocComment SpecialComment
highlight default link deaDocTag SpecialComment
highlight default link deaLineComment Comment
highlight default link deaEscape SpecialChar
highlight default link deaString String
highlight default link deaByte Character
highlight default link deaNumber Number
highlight default link deaBoolean Boolean
highlight default link deaNull Constant
highlight default link deaWildcard Constant
highlight default link deaDeclaration Keyword
highlight default link deaStorage StorageClass
highlight default link deaControl Conditional
highlight default link deaOperatorWord Operator
highlight default link deaReserved Keyword
highlight default link deaBuiltinType Type
highlight default link deaQualifiedName Identifier
highlight default link deaFunction Function
highlight default link deaTypeName Type
highlight default link deaOperator Operator

let b:current_syntax = "dea_l0"
