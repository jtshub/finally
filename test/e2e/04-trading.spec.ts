import { expect, test, type Page } from "@playwright/test";
import { heldQuantity, openApp, readNumber, waitForPrice } from "./helpers";

async function trade(page: Page, ticker: string, quantity: number, side: "buy" | "sell") {
  await page.getByTestId("trade-ticker-input").fill(ticker);
  await page.getByTestId("trade-quantity-input").fill(String(quantity));
  await page.getByTestId(`trade-${side}-button`).click();
}

test.describe("trading", () => {
  test("buy shares: cash decreases and position appears", async ({ page, request }) => {
    await waitForPrice(request, "NVDA");
    await openApp(page);
    const cash = page.getByTestId("header-cash");
    const before = await readNumber(cash);

    await trade(page, "NVDA", 2, "buy");

    await expect.poll(() => readNumber(cash)).toBeLessThan(before);
    await expect(page.getByTestId("positions-table").getByTestId("position-row-NVDA")).toBeVisible();
    expect(await heldQuantity(request, "NVDA")).toBeGreaterThanOrEqual(2);
  });

  test("sell shares: cash increases, position updates then disappears", async ({ page, request }) => {
    await waitForPrice(request, "AMZN");
    const held = await heldQuantity(request, "AMZN");
    await request.post("/api/portfolio/trade", { data: { ticker: "AMZN", quantity: 3, side: "buy" } });
    await openApp(page);
    const cash = page.getByTestId("header-cash");
    const row = page.getByTestId("position-row-AMZN");
    await expect(row).toBeVisible();

    const before = await readNumber(cash);
    await trade(page, "AMZN", 1, "sell");
    await expect.poll(() => readNumber(cash)).toBeGreaterThan(before);
    await expect.poll(() => heldQuantity(request, "AMZN")).toBeCloseTo(held + 2);
    await expect(row).toBeVisible();

    await trade(page, "AMZN", held + 2, "sell");
    await expect(row).toHaveCount(0);
  });

  test("selling more than owned shows a trade error", async ({ page }) => {
    await openApp(page);
    const cash = page.getByTestId("header-cash");
    const before = await readNumber(cash);
    await trade(page, "TSLA", 100000, "sell");
    await expect(page.getByTestId("trade-error")).toBeVisible();
    expect(await readNumber(cash)).toBe(before);
  });
});
