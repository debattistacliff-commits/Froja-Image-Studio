import { spawnSync } from "node:child_process";

const candidates = process.platform === "win32"
  ? [[".venv\\Scripts\\python.exe", []], ["python", []], ["py", ["-3"]]]
  : [[".venv/bin/python", []], ["python3", []], ["python", []]];

for (const [command, prefix] of candidates) {
  const check = spawnSync(command, [...prefix, "--version"], { stdio: "ignore" });
  if (check.status !== 0) continue;
  const result = spawnSync(
    command,
    [...prefix, "-m", "unittest", "discover", "-s", "tests", "-p", "backend_workflows_test.py"],
    { stdio: "inherit" },
  );
  process.exit(result.status ?? 1);
}

console.error("Froja tests require Python 3.10 or newer.");
process.exit(1);
