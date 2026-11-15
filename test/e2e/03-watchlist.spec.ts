import { expect, test } from "@playwright/test";
import { openApp } from "./helpers";

test.describe("watchlist", () => {
  test("add and remove a ticker", async ({ page }) => {
    await openApp(page);
    const rows = page.locator('[data-testid^="watchlist-row-"]');
    const initial = await rows.count();

    await page.getByTestId("watchlist-add-input").fill("PYPL");
    await page.getByTestId("watchlist-add-button").click();

    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
    await expect(rows).toHaveCount(initial + 1);
    await expect(page.getByTestId("watchlist-price-PYPL")).toHaveText(/\d+\.\d+/);

    await page.getByTestId("watchlist-remove-PYPL").click();
    await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
    await expect(rows).toHaveCount(initial);
  });
});
