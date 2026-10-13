import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/browser",
  workers: 1,
  timeout: 60000,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    viewport: { width: 360, height: 800 },
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
      args: ["--no-sandbox"],
    },
  },
  webServer: {
    command: "bash scripts/dev.sh",
    url: "http://localhost:3000/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
