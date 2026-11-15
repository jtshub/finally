import { expect, type APIRequestContext, type Locator, type Page } from "@playwright/test";

/** Parse a displayed money/number string like "$10,000.00" or "-1.5" into a number. */
export function parseNumber(text: string | null): number {
  return Number((text ?? "").replace(/[^0-9.\-]/g, ""));
}

/** Read the numeric value shown in an element. */
export async function readNumber(locator: Locator): Promise<number> {
  return parseNumber(await locator.textContent());
}

/** Wait until the backend has a live price for `ticker` and return it. */
export async function waitForPrice(request: APIRequestContext, ticker: string): Promise<number> {
  let price = 0;
  await expect
    .poll(async () => {
      const rows = await (await request.get("/api/watchlist")).json();
      price = rows.find((r: { ticker: string }) => r.ticker === ticker)?.price ?? 0;
      return price;
    })
    .toBeGreaterThan(0);
  return price;
}

/** Current quantity held for `ticker` (0 if no position). */
export async function heldQuantity(request: APIRequestContext, ticker: string): Promise<number> {
  const portfolio = await (await request.get("/api/portfolio")).json();
  return portfolio.positions.find((p: { ticker: string }) => p.ticker === ticker)?.quantity ?? 0;
}

/** Open the app and wait for the SSE connection to report connected. */
export async function openApp(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
}
