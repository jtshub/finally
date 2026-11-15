import { expect, test } from "@playwright/test";
import { openApp, readNumber } from "./helpers";

const DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"];

test.describe("fresh start", () => {
  test("shows default watchlist, $10k cash and streaming prices", async ({ page }) => {
    await openApp(page);

    await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(10);
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }

    expect(await readNumber(page.getByTestId("header-cash"))).toBe(10000);
    expect(await readNumber(page.getByTestId("header-total-value"))).toBe(10000);

    const price = page.getByTestId("watchlist-price-AAPL");
    await expect(price).toHaveText(/\d+\.\d+/);
    const first = await price.textContent();
    await expect(price).not.toHaveText(first!);
  });
});
