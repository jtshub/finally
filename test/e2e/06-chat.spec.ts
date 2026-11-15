import { expect, test } from "@playwright/test";
import { openApp, waitForPrice } from "./helpers";

test.describe("AI chat (LLM_MOCK=true)", () => {
  test("default reply is shown", async ({ page }) => {
    await openApp(page);
    await page.getByTestId("chat-input").fill("how is my portfolio?");
    await page.getByTestId("chat-send-button").click();
    await expect(page.getByTestId("chat-message").filter({ hasText: "Mock response: I can help with your portfolio." }).last()).toBeVisible();
    await expect(page.getByTestId("chat-loading")).toHaveCount(0);
  });

  test("buy 1 AAPL executes a trade shown inline", async ({ page, request }) => {
    await waitForPrice(request, "AAPL");
    await openApp(page);
    await page.getByTestId("chat-input").fill("buy 1 AAPL");
    await page.getByTestId("chat-send-button").click();

    await expect(page.getByTestId("chat-message").filter({ hasText: "Buying 1 AAPL." }).last()).toBeVisible();
    await expect(page.getByTestId("chat-action").filter({ hasText: "AAPL" }).last()).toBeVisible();
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  });
});
