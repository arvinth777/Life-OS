import { test, expect } from "@playwright/test";
const password = process.env.LIFE_OS_TEST_PASSWORD;

test("confirmed task, journal and concept-review feedback with safe busy and error states", async ({ page }) => {
  test.skip(!password, "Set LIFE_OS_TEST_PASSWORD for the local owner.");
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your focus today", exact: true })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("life-os-token"));
  const headers = { Authorization: "Bearer " + token };
  const created: [string, string][] = [];
  const suffix = Date.now();
  async function create(table: string, data: any) {
    const response = await page.request.post("/api/data/" + table, { headers, data });
    expect(response.ok()).toBeTruthy();
    const row = await response.json();
    created.push([table, row.id]);
    return row;
  }
  let release: (() => void) | undefined;
  try {
    const parent = await create("tasks", { title: "Motion task " + suffix, due_at: new Date().toISOString() });
    const child = await create("tasks", { title: "Motion child " + suffix, parent_id: parent.id });
    await page.reload();
    const complete = page.getByRole("button", { name: "Complete " + parent.title, exact: true });
    await complete.click();
    await expect(page.getByRole("alert")).toContainText("Complete the subtasks first");
    await expect(page.locator(".save-receipt")).toHaveCount(0);
    await expect(complete).toBeEnabled();
    await page.request.post("/api/tasks/" + child.id + "/complete", { headers });
    let requests = 0;
    await page.route("**/api/tasks/" + parent.id + "/complete", async (route) => {
      requests++;
      const response = await route.fetch();
      await new Promise<void>((resolve) => { release = resolve; });
      await route.fulfill({ response });
    });
    await complete.click();
    await expect(complete).toBeDisabled();
    await expect.poll(() => !!release).toBe(true);
    await expect(page.locator(".save-receipt")).toHaveCount(0);
    await complete.evaluate((el: HTMLButtonElement) => el.click());
    expect(requests).toBe(1);
    release!();
    await expect(page.locator(".save-receipt strong")).toHaveText("Task completed");
    await expect(complete).toHaveCount(0);
    await page.getByRole("button", { name: "Dismiss confirmation" }).click();

    await page.getByRole("button", { name: "Journal", exact: true }).click();
    await page.getByRole("button", { name: "New entry", exact: true }).click();
    await page.getByRole("dialog").getByLabel(/^Title/).fill("Motion journal " + suffix);
    await page.getByRole("dialog").getByLabel("Body", { exact: true }).fill("A saved thought, with a quiet confirmation.");
    await page.getByRole("dialog").getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.locator(".save-receipt strong")).toHaveText("Journal entry saved");
    const entries = await (await page.request.get("/api/data/journal_entries", { headers })).json();
    const entry = entries.find((r: any) => r.title === "Motion journal " + suffix);
    expect(entry).toBeTruthy(); created.push(["journal_entries", entry.id]);
    await page.getByRole("button", { name: "Dismiss confirmation" }).click();

    const note = await create("concept_notes", { title: "Motion concept " + suffix, front: "What does a pointer represent?", back: "A position in a sequence.", due_on: "2000-01-01" });
    await page.getByRole("button", { name: "DSA in Python", exact: true }).click();
    await page.getByRole("button", { name: "Two pointers", exact: true }).click();
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator(".step-caption")).toContainText("1 + 7 = 8");
    expect(await page.locator(".step-caption").evaluate((el) => getComputedStyle(el).animationName)).toBe("explanation-arrive");
    await expect(page.locator(".step-rail .reached")).toHaveCount(2);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: "/tmp/life-os-motion-dsa.png", fullPage: true, animations: "disabled" });
    await page.getByRole("button", { name: "Concept reviews", exact: true }).click();
    const card = page.locator(".review-card").filter({ hasText: note.title });
    await expect(card).toBeVisible();
    await expect(card.getByText(note.back)).toHaveCount(0);
    await card.getByRole("button", { name: "Reveal answer", exact: true }).click();
    await expect(card.getByText(note.back)).toBeVisible();
    expect(await card.locator(".review-answer").evaluate((el) => getComputedStyle(el).animationName)).toBe("answer-turn");
    let reviewRequests = 0;
    let next: any;
    release = undefined;
    await page.route("**/api/reviews/" + note.id, async (route) => {
      reviewRequests++;
      const response = await route.fetch();
      next = await response.json();
      await new Promise<void>((resolve) => { release = resolve; });
      await route.fulfill({ response });
    });
    await card.getByRole("button", { name: "4", exact: true }).click();
    await expect(card.getByRole("button", { name: "5", exact: true })).toBeDisabled();
    await expect.poll(() => !!release).toBe(true);
    await card.getByRole("button", { name: "5", exact: true }).evaluate((el: HTMLButtonElement) => el.click());
    expect(reviewRequests).toBe(1);
    await expect(page.locator(".save-receipt")).toHaveCount(0);
    release!();
    await expect(page.locator(".save-receipt strong")).toHaveText("Review saved");
    const shownDate = await page.evaluate((date) => new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(date + "T12:00:00Z")), next.due_on);
    await expect(page.locator(".save-receipt small")).toHaveText("Next review: " + shownDate);
    await expect(card).toHaveCount(0);
    await page.setViewportSize({ width: 375, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
    expect(await page.locator(".save-receipt").evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
    expect(await page.locator(".success-pixels i").first().evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
    await page.screenshot({ path: "/tmp/life-os-motion-review.png", fullPage: true });
  } finally {
    release?.();
    for (const [table, id] of created.reverse()) await page.request.delete("/api/data/" + table + "/" + id, { headers });
  }
});
