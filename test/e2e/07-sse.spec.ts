import { expect, test } from "@playwright/test";
import { openApp } from "./helpers";

test.describe("SSE resilience", () => {
  test("status leaves connected when the stream is blocked and recovers when unblocked", async ({ page }) => {
    await openApp(page);
    const status = page.getByTestId("connection-status");

    await page.route("**/api/stream/prices", (route) => route.abort());
    await page.reload();
    await expect(status).toHaveAttribute("data-status", /reconnecting|disconnected/);

    await page.unroute("**/api/stream/prices");
    await expect(status).toHaveAttribute("data-status", "connected", { timeout: 20_000 });

    const price = page.getByTestId("watchlist-price-AAPL");
    await expect(price).toHaveText(/\d+\.\d+/);
    const first = await price.textContent();
    await expect(price).not.toHaveText(first!);
  });
});
