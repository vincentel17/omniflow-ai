import { defineConfig } from "@playwright/test";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  timeout: 60_000,
  testDir: "./tests/e2e",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100"
  },
  webServer: {
    timeout: 120_000,
    command: "pnpm exec next dev --port 3100",
    port: 3100,
    reuseExistingServer: false,
    cwd: __dirname,
    env: {
      PLAYWRIGHT: "1"
    }
  }
});
