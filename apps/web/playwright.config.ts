import { defineConfig } from "@playwright/test";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 120_000,
  testDir: "./tests/e2e",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
    navigationTimeout: 120_000
  },
  webServer: {
    timeout: 240_000,
    command: "pnpm exec next build && pnpm exec next start --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: false,
    cwd: __dirname,
    env: {
      CI: "1",
      PLAYWRIGHT: "1"
    }
  }
});
