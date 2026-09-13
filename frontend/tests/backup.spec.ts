import { test, expect } from "@playwright/test";

test("chunked backup restores through the settings interface", async ({ page }) => {
  test.skip(process.env.LIFE_OS_BACKUP_TEST_API !== "http://127.0.0.1:8001", "Requires the isolated local test API on port 8001");
  await page.addInitScript(() => localStorage.setItem("life-os-api", "http://127.0.0.1:8001"));
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("test-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("main h1")).toHaveText("Today");
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Backup & restore", exact: true }).click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export/ }).click();
  const download = await downloadEvent;
  const path = await download.path();
  expect(path).toBeTruthy();
  await expect(page.getByText("Backup downloaded: every table in JSON and CSV.")).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByLabel("Restore backup file").setInputFiles(path!);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  await page.getByLabel("Username", { exact: true }).fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("test-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("main h1")).toHaveText("Settings");
});
