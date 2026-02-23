import { spawnSync } from "node:child_process";

const cwd = process.cwd().replace(/\\/g, "/");
const args = [
  "run",
  "--rm",
  "-v",
  `${cwd}:/src`,
  "returntocorp/semgrep:1.152.0",
  "semgrep",
  "--config",
  "auto",
  "--error",
  "--exclude",
  "node_modules",
  "--exclude",
  ".next",
  "--exclude",
  "dist",
  "--exclude",
  "build",
  "--exclude",
  "coverage",
  "/src"
];

const result = spawnSync("docker", args, { stdio: "inherit" });
if (typeof result.status === "number") {
  process.exit(result.status);
}
process.exit(1);
