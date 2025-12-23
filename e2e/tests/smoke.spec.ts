import { expect, test } from "@playwright/test";

test.describe("Health Check", () => {
  test("frontend loads successfully", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/GrindLab/i);
  });

  test("backend health endpoint is accessible", async ({ request }) => {
    const response = await request.get(
      process.env.E2E_API_URL || "http://localhost:8000/health"
    );
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.status).toBe("ok");
  });
});

test.describe("Navigation", () => {
  test("can navigate to projects page", async ({ page }) => {
    await page.goto("/");

    // Look for projects link or navigate directly
    await page.goto("/projects");
    await expect(page).toHaveURL(/.*projects/);
  });

  test("can navigate to flowsheets page", async ({ page }) => {
    await page.goto("/flowsheets");
    await expect(page).toHaveURL(/.*flowsheets/);
  });
});
