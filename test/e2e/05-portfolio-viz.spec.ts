import { expect, test } from "@playwright/test";
import { openApp, waitForPrice } from "./helpers";

test.describe("portfolio visualizations", () => {
  test("heatmap and P&L chart render with data", async ({ page, request }) => {
    await waitForPrice(request, "META");
    await request.post("/api/portfolio/trade", { data: { ticker: "META", quantity: 1, side: "buy" } });
    const history = await (await request.get("/api/portfolio/history")).json();
    expect(history.length).toBeGreaterThan(0);

    await openApp(page);

    const heatmap = page.getByTestId("heatmap");
    await expect(heatmap).toBeVisible();
    await expect(heatmap).toContainText("META");
    const box = await heatmap.boundingBox();
    expect(box!.width).toBeGreaterThan(50);
    expect(box!.height).toBeGreaterThan(50);

    const pnl = page.getByTestId("pnl-chart");
    await expect(pnl).toBeVisible();
    await expect(pnl.locator("canvas, svg").first()).toBeVisible();
  });

  test("main chart shows the selected ticker", async ({ page }) => {
    await openApp(page);
    await page.getByTestId("watchlist-row-GOOGL").click();
    const chart = page.getByTestId("main-chart");
    await expect(chart).toBeVisible();
    await expect(chart).toContainText("GOOGL");
    await expect(chart.locator("canvas, svg").first()).toBeVisible();
  });
});
