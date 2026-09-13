import { test, expect } from "@playwright/test";
const password = process.env.LIFE_OS_TEST_PASSWORD;

test("hydration saves once, fills from persisted totals, and recovers uncertain requests", async ({ page }) => {
  test.skip(!password, "Set LIFE_OS_TEST_PASSWORD for the local owner.");
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your focus today", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add 250 ml of water" })).toHaveCount(0);
  await expect(page.getByText("Water today", { exact: true })).toHaveCount(0);
  const token = await page.evaluate(() => sessionStorage.getItem("life-os-token"));
  const headers = { Authorization: "Bearer " + token };
  const before = (await (await page.request.get("/api/dashboard", { headers })).json()).metrics.water || 0;
  const records: string[] = [];
  let mode = "hold";
  let release: (() => void) | undefined;
  let failRead = false;
  await page.route("**/api/ingest", async (route) => {
    const record = route.request().postDataJSON()[0];
    records.push(record.external_id);
    const response = await route.fetch();
    if (mode === "hold") await new Promise<void>((resolve) => { release = resolve; });
    if (mode === "lost") { mode = "normal"; await route.abort("failed"); return; }
    if (mode === "read-failure") { failRead = true; mode = "normal"; }
    await route.fulfill({ response });
  });
  await page.route("**/api/dashboard", async (route) => {
    if (failRead) {
      failRead = false;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Test read failure" }) });
    } else await route.continue();
  });
  async function totalIs(value: number) {
    await expect(page.locator(".water-amount strong")).toHaveText(value.toLocaleString());
  }
  try {
    await page.getByRole("button", { name: "Physical goals", exact: true }).click();
    const tank = page.getByRole("button", { name: "Add 250 ml of water", exact: true });
    await expect(tank).toBeEnabled();
    await totalIs(before);
    await tank.click();
    await expect(tank).toBeDisabled();
    await expect.poll(() => !!release).toBe(true);
    await tank.evaluate((el: HTMLButtonElement) => el.click());
    expect(records).toHaveLength(1);
    mode = "normal";
    release!();
    await totalIs(before + 250);
    await expect(page.locator(".water-wave")).toHaveClass(/pouring/);
    const offset = await page.locator(".water-liquid").evaluate((el) => (el as HTMLElement).style.getPropertyValue("--water-offset"));
    expect(parseFloat(offset)).toBeLessThan(100);
    await page.reload();
    await expect(tank).toBeEnabled();
    await totalIs(before + 250);

    // The database accepts this drink but the response is lost. The retry must dedupe.
    mode = "lost";
    await tank.click();
    await expect(page.getByRole("alert")).toContainText("won’t be counted twice");
    await totalIs(before + 250);
    await tank.click();
    await totalIs(before + 500);
    expect(records[1]).toBe(records[2]);

    // A confirmed save followed by a failed read offers only a read-only retry.
    mode = "read-failure";
    await tank.click();
    await expect(page.getByRole("alert")).toContainText("Your drink is saved");
    const postCount = records.length;
    await page.getByRole("button", { name: "Refresh water total", exact: true }).click();
    await totalIs(before + 750);
    expect(records).toHaveLength(postCount);

    await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
    await expect.poll(() => page.locator(".water-liquid").evaluate((el) => getComputedStyle(el).transitionDuration)).toBe("0s");
    await tank.click();
    await totalIs(before + 1000);
    await expect.poll(() => page.locator(".water-wave").evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
    await page.screenshot({ path: "/tmp/life-os-water-dark.png", fullPage: true });
    await page.emulateMedia({ reducedMotion: "no-preference", colorScheme: "light" });
    await page.screenshot({ path: "/tmp/life-os-water-light.png", fullPage: true, animations: "disabled" });
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await expect(tank).toBeVisible();
    }
    await page.evaluate(() => document.documentElement.style.fontSize = "200%");
    expect(await tank.locator(".water-content").evaluate((el) => el.scrollHeight <= el.clientHeight)).toBe(true);
    await page.evaluate(() => document.documentElement.style.fontSize = "");

    // A small test-only goal verifies a full tank never hides an above-goal total.
    await page.route("**/api/data/settings", async (route) => {
      const response = await route.fetch();
      const rows = await response.json();
      await route.fulfill({ response, json: rows.map((r: any) => r.key === "water_goal_ml" ? { ...r, value: 100 } : r) });
    });
    await page.reload();
    await expect(tank).toBeEnabled();
    await totalIs(before + 1000);
    expect(await page.locator(".water-liquid").evaluate((el) => (el as HTMLElement).style.getPropertyValue("--water-offset"))).toBe("0%");
  } finally {
    release?.();
    const rows = await (await page.request.get("/api/data/health_records", { headers })).json();
    for (const r of rows.filter((r: any) => records.includes(r.external_id))) {
      await page.request.delete("/api/data/health_records/" + r.id, { headers });
    }
  }
});
