" SPDX-License-Identifier: MIT OR Apache-2.0
" Copyright (c) 2026 gwz

augroup dea_filetypes
  autocmd!
  autocmd BufRead,BufNewFile *.l0 setfiletype dea_l0
  autocmd BufRead,BufNewFile *.l1 setfiletype dea_l1
augroup END
