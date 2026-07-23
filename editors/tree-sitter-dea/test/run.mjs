import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const cli = path.join(root, "node_modules", ".bin", "tree-sitter");
const cache = path.join(root, ".cache");
const env = {
  ...process.env,
  XDG_CACHE_HOME: cache,
};

function run(command, args) {
  execFileSync(command, args, {
    cwd: root,
    env,
    stdio: "inherit",
  });
}

run(cli, ["generate"]);
run(cli, ["test"]);
run(process.execPath, [path.join(root, "test", "query-smoke.mjs")]);
