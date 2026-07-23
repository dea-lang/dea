// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 gwz

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import oniguruma from "vscode-oniguruma";
import textmate from "vscode-textmate";

const require = createRequire(import.meta.url);
const extensionRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixtureRoot = path.join(extensionRoot, "test", "fixtures");
const grammarPaths = new Map([
  ["source.dea.l0", path.join(extensionRoot, "syntaxes", "dea-l0.tmLanguage.json")],
  ["source.dea.l1", path.join(extensionRoot, "syntaxes", "dea-l1.tmLanguage.json")],
]);

const wasmBytes = fs.readFileSync(
  require.resolve("vscode-oniguruma/release/onig.wasm"),
);
const wasmArrayBuffer = wasmBytes.buffer.slice(
  wasmBytes.byteOffset,
  wasmBytes.byteOffset + wasmBytes.byteLength,
);
await oniguruma.loadWASM(wasmArrayBuffer);

const registry = new textmate.Registry({
  onigLib: Promise.resolve({
    createOnigScanner(patterns) {
      return new oniguruma.OnigScanner(patterns);
    },
    createOnigString(value) {
      return new oniguruma.OnigString(value);
    },
  }),
  async loadGrammar(scopeName) {
    const grammarPath = grammarPaths.get(scopeName);
    if (grammarPath === undefined) {
      return null;
    }
    return JSON.parse(fs.readFileSync(grammarPath, "utf8"));
  },
});

async function tokenizeFixture(scopeName, fixtureName) {
  const grammar = await registry.loadGrammar(scopeName);
  assert.notEqual(grammar, null, `grammar ${scopeName} did not load`);

  const source = fs.readFileSync(path.join(fixtureRoot, fixtureName), "utf8");
  const lines = source.split(/\r?\n/);
  let ruleStack = textmate.INITIAL;
  const tokenLines = [];

  for (const line of lines) {
    const result = grammar.tokenizeLine(line, ruleStack);
    ruleStack = result.ruleStack;
    tokenLines.push(
      result.tokens.map((token) => ({
        startIndex: token.startIndex,
        endIndex: token.endIndex,
        scopes: token.scopes,
        text: line.slice(token.startIndex, token.endIndex),
      })),
    );
  }
  return { lines, tokenLines };
}

function tokenAt(tokenized, lineFragment, lexeme, occurrence = 0) {
  const lineIndex = tokenized.lines.findIndex((line) => line.includes(lineFragment));
  assert.notEqual(lineIndex, -1, `missing line containing ${JSON.stringify(lineFragment)}`);

  let characterIndex = -1;
  let searchFrom = 0;
  for (let index = 0; index <= occurrence; index += 1) {
    characterIndex = tokenized.lines[lineIndex].indexOf(lexeme, searchFrom);
    assert.notEqual(
      characterIndex,
      -1,
      `missing ${JSON.stringify(lexeme)} in ${JSON.stringify(lineFragment)}`,
    );
    searchFrom = characterIndex + lexeme.length;
  }

  const token = tokenized.tokenLines[lineIndex].find(
    (candidate) =>
      candidate.startIndex <= characterIndex && candidate.endIndex > characterIndex,
  );
  assert.notEqual(token, undefined, `no token covers ${JSON.stringify(lexeme)}`);
  return token;
}

function assertScope(tokenized, lineFragment, lexeme, expectedScope, occurrence = 0) {
  const token = tokenAt(tokenized, lineFragment, lexeme, occurrence);
  assert.ok(
    token.scopes.includes(expectedScope),
    `${JSON.stringify(lexeme)} had scopes ${token.scopes.join(", ")}, expected ${expectedScope}`,
  );
}

test("L0 grammar tokenizes representative language surfaces", async () => {
  const tokenized = await tokenizeFixture("source.dea.l0", "l0_surface.l0");

  assertScope(
    tokenized,
    "module l0_surface;",
    "module",
    "keyword.declaration.module.dea",
  );
  assertScope(
    tokenized,
    "module l0_surface;",
    "l0_surface",
    "entity.name.namespace.dea",
  );
  assertScope(
    tokenized,
    "func parse(cursor:",
    "parse",
    "entity.name.function.dea",
  );
  assertScope(
    tokenized,
    "position: int;",
    "int",
    "support.type.builtin.dea",
  );
  assertScope(
    tokenized,
    "std.io::printl_s",
    "std.io::printl_s",
    "variable.other.qualified.dea",
  );
  assertScope(
    tokenized,
    "* Exercise module-qualified",
    "Exercise",
    "comment.block.documentation.dea",
  );
  assertScope(
    tokenized,
    '"parsing…"',
    "parsing…",
    "string.quoted.double.dea",
  );
  assertScope(tokenized, "with (let parsed:", "with", "keyword.control.dea");
  assertScope(tokenized, "} cleanup {", "cleanup", "keyword.control.dea");
  assertScope(tokenized, "parsed == null", "null", "constant.language.null.dea");
  assertScope(tokenized, "Value(number) =>", "=>", "keyword.operator.arrow.dea");
  assertScope(tokenized, "ParseResult? =", "?", "keyword.operator.dea");
});

test("L1 grammar adds superset keywords, literals, labels, and variadics", async () => {
  const tokenized = await tokenizeFixture("source.dea.l1", "l1_surface.l1");

  assertScope(tokenized, "export opaque", "export", "keyword.declaration.dea");
  assertScope(tokenized, "export opaque", "opaque", "keyword.declaration.dea");
  assertScope(
    tokenized,
    "const ratio:",
    "ratio",
    "entity.name.constant.dea",
  );
  assertScope(tokenized, "1.25e+2", "1.25e+2", "constant.numeric.float.dea");
  assertScope(
    tokenized,
    "const mask:",
    "0xFF",
    "constant.numeric.integer.hexadecimal.dea",
  );
  assertScope(
    tokenized,
    "const binary_flag:",
    "0b01",
    "constant.numeric.integer.binary.dea",
  );
  assertScope(
    tokenized,
    "unsafe func first",
    "unsafe",
    "keyword.declaration.dea",
  );
  assertScope(
    tokenized,
    "values: int...",
    "...",
    "keyword.operator.variadic.dea",
  );
  assertScope(
    tokenized,
    "choose(right:",
    "right",
    "variable.other.label.dea",
  );
  assertScope(
    tokenized,
    "io::printl_s",
    "io::printl_s",
    "variable.other.qualified.dea",
  );
  assertScope(tokenized, "ratio: double", "double", "support.type.builtin.dea");
});

test("grammars remain useful on incomplete input", async () => {
  const l0 = await tokenizeFixture("source.dea.l0", "l0_incomplete.l0");
  const l1 = await tokenizeFixture("source.dea.l1", "l1_incomplete.l1");

  assertScope(
    l0,
    "func unfinished",
    "unfinished",
    "entity.name.function.dea",
  );
  assertScope(
    l0,
    '"unterminated string',
    "unterminated",
    "string.quoted.double.dea",
  );
  assertScope(l0, "match (value)", "match", "keyword.control.dea");
  assertScope(
    l0,
    "unterminated block comment",
    "unterminated",
    "comment.block.dea",
  );

  assertScope(l1, "export opaque", "opaque", "keyword.declaration.dea");
  assertScope(
    l1,
    '"unterminated string',
    "unterminated",
    "string.quoted.double.dea",
  );
  assertScope(l1, "match (value)", "match", "keyword.control.dea");
  assertScope(
    l1,
    "unterminated documentation comment",
    "unterminated",
    "comment.block.documentation.dea",
  );
});
