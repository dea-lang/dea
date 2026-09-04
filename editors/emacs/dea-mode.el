;;; dea-mode.el --- Major mode for Dea/L0 and Dea/L1 -*- lexical-binding: t; -*-

;; SPDX-License-Identifier: MIT OR Apache-2.0
;; Copyright (c) 2026 gwz

;; Author: gwz (googlielmo)
;; Version: 0.1.0
;; Package-Requires: ((emacs "27.1"))
;; Keywords: languages
;; URL: https://github.com/dea-lang/dea

;;; Commentary:

;; Lightweight regex-based editing support for Dea/L0 (`.l0') and Dea/L1
;; (`.l1').  The selected keyword and literal sets follow the file extension.

;;; Code:

(defgroup dea nil
  "Editing support for the Dea language family."
  :group 'languages)

(defvar-local dea-language-level 0
  "Language level selected for the current Dea buffer.")

(defconst dea--common-keywords
  '("as" "break" "case" "cleanup" "const" "continue" "drop" "else"
    "enum" "extern" "for" "func" "if" "import" "in" "let"
    "match" "module" "new" "return" "struct" "type"
    "while" "with"))

(defconst dea--l1-keywords
  '("export" "from" "opaque" "unsafe"))

(defconst dea--builtin-types
  '("bool" "byte" "double" "float" "int" "long" "short" "string"
    "tiny" "uint" "ulong" "ushort" "void"))

(defconst dea--syntax-table
  (let ((table (make-syntax-table)))
    (modify-syntax-entry ?_ "w" table)
    (modify-syntax-entry ?/ ". 124b" table)
    (modify-syntax-entry ?* ". 23" table)
    (modify-syntax-entry ?\n "> b" table)
    (modify-syntax-entry ?' "." table)
    table)
  "Syntax table shared by Dea/L0 and Dea/L1.")

(defun dea--font-lock-keywords ()
  "Build font-lock rules for the current Dea language level."
  (let ((keywords (append dea--common-keywords
                          (when (= dea-language-level 1)
                            dea--l1-keywords)))
        (number-pattern
         (if (= dea-language-level 1)
             (concat
              "\\_<\\(?:0[xX][0-9A-Fa-f]+\\|0[oO][0-7]+\\|0[bB][01]+"
              "\\|[0-9]+\\(?:\\.[0-9]+\\(?:[eE][+-]?[0-9]+\\)?[fF]?"
              "\\|[eE][+-]?[0-9]+[fF]?\\)?\\)\\_>")
           "\\_<[0-9]+\\_>")))
    `(("\\_<func\\_>\\s-+\\([A-Za-z_][A-Za-z0-9_]*\\)"
       (1 font-lock-function-name-face))
      ("\\_<\\(?:struct\\|enum\\|type\\)\\_>\\s-+\\([A-Za-z_][A-Za-z0-9_]*\\)"
       (1 font-lock-type-face))
      ("\\_<\\(?:module\\|import\\)\\_>\\s-+\\([A-Za-z_][A-Za-z0-9_.]*\\)"
       (1 font-lock-constant-face))
      ("\\_<const\\_>\\s-+\\([A-Za-z_][A-Za-z0-9_]*\\)"
       (1 font-lock-constant-face))
      (,(regexp-opt keywords 'symbols) . font-lock-keyword-face)
      (,(regexp-opt dea--builtin-types 'symbols) . font-lock-type-face)
      ("\\_<\\(?:true\\|false\\|null\\)\\_>" . font-lock-constant-face)
      ("\\_<_\\_>" . font-lock-constant-face)
      (,number-pattern . font-lock-constant-face)
      ("'\\(?:\\\\.\\|[^\\\\'\n]\\)'" . font-lock-constant-face)
      ("\\_<[A-Za-z_][A-Za-z0-9_.]*::[A-Za-z_][A-Za-z0-9_:]*\\_>"
       . font-lock-variable-name-face)
      ("\\_<[A-Z][A-Za-z0-9_]*\\_>" . font-lock-type-face)
      ("\\_<\\([A-Za-z_][A-Za-z0-9_]*\\)\\_>\\s-*("
       (1 font-lock-function-name-face keep))
      ,@(when (= dea-language-level 1)
          '(("\\_<[A-Za-z_][A-Za-z0-9_]*\\_>\\s-*:"
             (0 font-lock-variable-name-face keep)))))))

;;;###autoload
(define-derived-mode dea-mode prog-mode "Dea"
  "Major mode for Dea/L0 and Dea/L1 source files."
  :syntax-table dea--syntax-table
  (setq-local dea-language-level
              (if (and buffer-file-name
                       (string-match-p "\\.l1\\'" buffer-file-name))
                  1
                0))
  (setq-local font-lock-defaults (list (dea--font-lock-keywords)))
  (setq-local comment-start "// ")
  (setq-local comment-end "")
  (setq-local comment-start-skip "\\(?://+\\|/\\*+\\)\\s-*")
  (setq-local parse-sexp-ignore-comments t))

;;;###autoload
(add-to-list 'auto-mode-alist '("\\.l[01]\\'" . dea-mode))

(provide 'dea-mode)

;;; dea-mode.el ends here
