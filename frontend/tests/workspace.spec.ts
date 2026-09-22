import { test, expect } from "@playwright/test";
const password = process.env.LIFE_OS_TEST_PASSWORD;
test("owner workflows, nine modules, responsive widths, and disabled integrations", async ({
  page,
}) => {
  test.skip(
    !password,
    "Set LIFE_OS_TEST_PASSWORD for the disposable local owner.",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Today", exact: true }),
  ).toBeVisible();
  const token = await page.evaluate(() =>
    sessionStorage.getItem("life-os-token"),
  );
  const created: [string, string][] = [];
  async function cleanup() {
    for (const [table, id] of created.reverse())
      await page.request.delete("/api/data/" + table + "/" + id, {
        headers: { Authorization: "Bearer " + token },
      });
  }
  async function remember(table: string, field: string, value: string) {
    const r = await page.request.get("/api/data/" + table, {
      headers: { Authorization: "Bearer " + token },
    });
    const row = (await r.json()).find((r: any) => r[field] === value);
    expect(row).toBeTruthy();
    created.push([table, row.id]);
    return row;
  }
  const suffix = Date.now();
  try {
    await page.getByRole("button", { name: "New task", exact: true }).click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Title/)
      .fill("QA task " + suffix);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await remember("tasks", "title", "QA task " + suffix);
    await page.getByRole("button", { name: "Journal", exact: true }).click();
    await page.getByRole("button", { name: "New entry" }).click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Title/)
      .fill("QA reflection " + suffix);
    await page
      .getByRole("dialog")
      .getByLabel("Body", { exact: true })
      .fill("A real entry saved through the interface.");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(
      page
        .locator("article .prose")
        .filter({ hasText: "A real entry saved through the interface." })
        .first(),
    ).toBeVisible();
    await remember("journal_entries", "title", "QA reflection " + suffix);
    await expect(
      page.getByRole("button", { name: "Get AI feedback" }),
    ).toBeDisabled();
    await page
      .getByRole("button", { name: "Personal growth", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Your traits", exact: true })
      .click();
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Name/)
      .fill("QA patience " + suffix);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await remember("traits", "name", "QA patience " + suffix);
    await page.getByRole("button", { name: "Academics", exact: true }).click();
    await page.getByRole("button", { name: "Terms", exact: true }).click();
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Name/)
      .fill("QA term " + suffix);
    await page.getByRole("dialog").getByLabel("Starts On").fill("2026-01-01");
    await page.getByRole("dialog").getByLabel("Ends On").fill("2026-12-31");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await remember("terms", "name", "QA term " + suffix);
    await page.getByRole("button", { name: "Work", exact: true }).click();
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Name/)
      .fill("QA project " + suffix);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await remember("projects", "name", "QA project " + suffix);
    await page
      .getByRole("button", { name: "DSA in Python", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Learning path", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Two pointers", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Two pointers", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.getByText(/1 \+ 7 = 8/)).toBeVisible();
    await page
      .locator("summary")
      .filter({ hasText: "Read a palindrome" })
      .click();
    await page.getByRole("button", { name: "Reveal hint 1" }).click();
    await expect(
      page.getByText("Compare the first and last unchecked characters."),
    ).toBeVisible();
    await page.getByText("Worked Python solution").first().click();
    await expect(page.locator("code").first()).toContainText(
      "def is_palindrome",
    );
    await page
      .getByRole("button", {
        name: "Stacks and queues Incomplete",
        exact: true,
      })
      .click();
    await expect(
      page.getByText(/This lesson is an incomplete outline/),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Physical goals", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Log workout", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Title/)
      .fill("QA session " + suffix);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    const workout = await remember("workouts", "title", "QA session " + suffix);
    await page.getByRole("button", { name: "Workouts", exact: true }).click();
    await page
      .getByRole("row")
      .filter({ hasText: "QA session " + suffix })
      .getByRole("button", { name: "Set", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByLabel("Exercise")
      .selectOption({ label: "Push-up" });
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("button", { name: "Today & training" }).click();
    await page.getByLabel("Training period").selectOption(workout.id);
    await expect(page.locator('g[data-muscle="chest"].active')).toHaveCount(1);
    await expect(page.locator('g[data-muscle="triceps"].active')).toHaveCount(
      1,
    );
    await expect(page.locator('g[data-muscle="shoulders"].active')).toHaveCount(
      2,
    );
    expect(await page.locator(".muscle.active path").first().evaluate((el) => getComputedStyle(el).animationName)).toBe("muscle-light");
    await expect(page.locator(".volume-row .value-bar")).toHaveCount(3);
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    await page.getByRole("button", { name: "Event", exact: true }).click();
    await page
      .getByRole("dialog")
      .getByLabel(/^Title/)
      .fill("QA event " + suffix);
    await page
      .getByRole("dialog")
      .getByLabel("Starts At")
      .fill("2026-09-13T09:00");
    await page
      .getByRole("dialog")
      .getByLabel("Ends At")
      .fill("2026-09-13T10:00");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await remember("calendar_events", "title", "QA event " + suffix);
    await page.getByRole("button", { name: "To-do list", exact: true }).click();
    await expect(
      page.getByText("QA task " + suffix, { exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByText("QA task " + suffix, { exact: true }),
    ).toBeVisible();
    for (const width of [320, 375, 414, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const route of [
        "home",
        "journal",
        "personality",
        "academics",
        "work",
        "dsa",
        "physical",
        "calendar",
        "tasks",
        "settings",
      ]) {
        const endpoints: any = {
          home: "/dashboard",
          journal: "/data/journal_entries",
          personality: "/data/reflection_prompts",
          academics: "/academics/summary",
          work: "/data/projects",
          dsa: "/data/problems",
          physical: "/physical/volume",
          calendar: "/calendar/agenda",
          tasks: "/data/tasks",
          settings: "/data/settings",
        };
        const response = page.waitForResponse(
          (r) =>
            r.url().includes("/api" + endpoints[route]) && r.status() === 200,
        );
        await page.goto("/#" + route);
        await response;
        const names: any = {
          home: "Today",
          journal: "Journal",
          personality: "Personal growth",
          academics: "Academics",
          work: "Work",
          dsa: "DSA in Python",
          physical: "Physical goals",
          calendar: "Calendar",
          tasks: "To-do list",
          settings: "Settings",
        };
        await expect(page.locator("main h1")).toHaveText(names[route]);
        await expect(
          page.getByText("Loading today…", { exact: true }),
        ).toHaveCount(0);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
          route + " width " + width,
        ).toBeTruthy();
      }
    }
    await page.goto("/#home");
    await expect(
      page.getByRole("heading", { name: "Your focus today", exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: process.env.LIFE_OS_SCREENSHOT || "/tmp/life-os-desktop.png",
      fullPage: true,
    });
    expect(errors).toEqual([]);
  } finally {
    test.setTimeout(180000);
    await cleanup();
  }
});
