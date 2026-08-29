import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const cli = path.join(root, "node_modules", ".bin", "tree-sitter");
const cache = path.join(root, ".cache");
const config = path.join(cache, "config.json");
const fixtures = [
  path.join(root, "test", "fixtures", "l0_surface.l0"),
  path.join(root, "test", "fixtures", "l1_surface.l1"),
];
const wildcardFixture = path.join(root, "test", "fixtures", "wildcards.l1");
const queryFixtures = [
  ...fixtures,
  path.join(root, "test", "fixtures", "incomplete.l1"),
  wildcardFixture,
];

mkdirSync(cache, { recursive: true });
writeFileSync(config, JSON.stringify({
  "parser-directories": [path.dirname(root)],
}));

function run(args) {
  return execFileSync(cli, args, {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      XDG_CACHE_HOME: cache,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
}

run(["parse", "-p", ".", "--config-path", config, "--quiet", ...fixtures]);

const queryExpectations = new Map([
  ["highlights.scm", /function|type|keyword/],
  ["indents.scm", /indent\.(begin|end)/],
  ["locals.scm", /local\.(scope|definition|reference)/],
  ["tags.scm", /definition\.(function|type)/],
]);

for (const [name, expectedCapture] of queryExpectations) {
  const output = run([
    "query",
    "-p",
    ".",
    "--config-path",
    config,
    "--captures",
    path.join("queries", name),
    ...queryFixtures,
  ]);

  if (!expectedCapture.test(output)) {
    throw new Error(`${name} did not produce the expected captures`);
  }
}

const wildcardHighlights = run([
  "query",
  "-p",
  ".",
  "--config-path",
  config,
  "--captures",
  path.join("queries", "highlights.scm"),
  wildcardFixture,
]);
const wildcardCaptures = wildcardHighlights.match(
  /capture: \d+ - constant\.builtin,[^\n]*text: `_`/g,
);
if (wildcardCaptures?.length !== 2) {
  throw new Error("highlights.scm did not capture both match and case wildcards");
}

run([
  "highlight",
  "-p",
  ".",
  "--config-path",
  config,
  "--query-paths",
  path.join("queries", "highlights.scm"),
  "--check",
  "--quiet",
  ...queryFixtures,
]);

const tags = run(["tags", "--config-path", config, ...fixtures]);
if (!/\|\s+(function|type)\s+def/.test(tags)) {
  throw new Error("tags.scm did not produce function or type definitions");
}
