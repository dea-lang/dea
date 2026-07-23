// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 gwz

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const extensionRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function readJson(relativePath) {
  return JSON.parse(await readFile(path.join(extensionRoot, relativePath), "utf8"));
}

test("manifest keeps distinct L0 and L1 language identities", async () => {
  const manifest = await readJson("package.json");
  const languages = new Map(
    manifest.contributes.languages.map((language) => [language.id, language]),
  );
  const grammars = new Map(
    manifest.contributes.grammars.map((grammar) => [grammar.language, grammar]),
  );

  assert.deepEqual([...languages.keys()].sort(), ["dea-l0", "dea-l1"]);
  assert.deepEqual(languages.get("dea-l0").extensions, [".l0"]);
  assert.deepEqual(languages.get("dea-l1").extensions, [".l1"]);
  assert.equal(grammars.get("dea-l0").scopeName, "source.dea.l0");
  assert.equal(grammars.get("dea-l1").scopeName, "source.dea.l1");
  assert.equal(
    (await readJson(grammars.get("dea-l0").path)).scopeName,
    "source.dea.l0",
  );
  assert.equal(
    (await readJson(grammars.get("dea-l1").path)).scopeName,
    "source.dea.l1",
  );
});

test("manifest contributes only declarative language support", async () => {
  const manifest = await readJson("package.json");

  assert.deepEqual(Object.keys(manifest.contributes).sort(), ["grammars", "languages"]);
  assert.equal(manifest.main, undefined);
  assert.equal(manifest.browser, undefined);
  assert.equal(manifest.activationEvents, undefined);
});

test("shared language configuration covers comments and pairs", async () => {
  const configuration = await readJson("language-configuration.json");

  assert.equal(configuration.comments.lineComment, "//");
  assert.deepEqual(configuration.comments.blockComment, ["/*", "*/"]);
  assert.deepEqual(configuration.brackets, [
    ["{", "}"],
    ["[", "]"],
    ["(", ")"],
  ]);

  const autoClosingPairs = configuration.autoClosingPairs.map(
    ({ open, close }) => `${open}${close}`,
  );
  const surroundingPairs = configuration.surroundingPairs.map(
    ([open, close]) => `${open}${close}`,
  );
  for (const pair of ["{}", "[]", "()", '""', "''"]) {
    assert.ok(autoClosingPairs.includes(pair), `missing auto-closing pair ${pair}`);
    assert.ok(surroundingPairs.includes(pair), `missing surrounding pair ${pair}`);
  }
});
