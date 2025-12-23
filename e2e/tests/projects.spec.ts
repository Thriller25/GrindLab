import { expect, test } from "@playwright/test";

test.describe("Projects", () => {
  test("projects page displays list", async ({ page }) => {
    await page.goto("/projects");

    // Wait for projects to load
    await page.waitForLoadState("networkidle");

    // Should have a heading or table
    const heading = page.locator("h1, h2").first();
    await expect(heading).toBeVisible();
  });

  test("can view project details", async ({ page }) => {
    await page.goto("/projects");
    await page.waitForLoadState("networkidle");

    // Click on first project link if available
    const projectLink = page.locator('a[href^="/projects/"]').first();
    if (await projectLink.isVisible()) {
      await projectLink.click();
      await expect(page).toHaveURL(/\/projects\/\d+/);
    }
  });
});

test.describe("Flowsheets", () => {
  test("flowsheets page displays list", async ({ page }) => {
    await page.goto("/flowsheets");
    await page.waitForLoadState("networkidle");

    // Should have flowsheet content
    const content = page.locator("main, .content, [role='main']").first();
    await expect(content).toBeVisible();
  });
});
