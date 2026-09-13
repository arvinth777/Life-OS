import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  workers: 1,
  timeout: 120000,
  use: {
    baseURL: process.env.LIFE_OS_UI_URL || "http://127.0.0.1:5173",
    browserName: "chromium",
    headless: true,
    actionTimeout: 10000,
  },
  reporter: "list",
});
