" Vim syntax file
" Language: Dea/L1
" SPDX-License-Identifier: MIT OR Apache-2.0
" Copyright (c) 2026 gwz

if exists("b:current_syntax")
  finish
endif

runtime! syntax/dea_l0.vim
unlet! b:current_syntax

syntax keyword deaL1Declaration export from unsafe opaque
syntax match deaL1Float "\<[0-9]\+\%(\.[0-9]\+\%([eE][+-]\=[0-9]\+\)\=[fF]\=\|[eE][+-]\=[0-9]\+[fF]\=\)\>"
syntax match deaL1Binary "\<0[bB][01]\+\>"
syntax match deaL1Octal "\<0[oO][0-7]\+\>"
syntax match deaL1Hex "\<0[xX][0-9A-Fa-f]\+\>"
syntax match deaL1Variadic "\.\.\."
syntax match deaL1Label "\<[A-Za-z_][A-Za-z0-9_]*\>\ze\s*:"

highlight default link deaL1Declaration Keyword
highlight default link deaL1Float Float
highlight default link deaL1Binary Number
highlight default link deaL1Octal Number
highlight default link deaL1Hex Number
highlight default link deaL1Variadic Operator
highlight default link deaL1Label Identifier

let b:current_syntax = "dea_l1"
