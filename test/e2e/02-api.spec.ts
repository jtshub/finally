import { expect, test } from "@playwright/test";
import { heldQuantity, waitForPrice } from "./helpers";

test.describe("REST API contract", { tag: "@api" }, () => {
  test("GET /api/health", async ({ request }) => {
    const res = await request.get("/api/health");
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
  });

  test("GET /api/portfolio shape", async ({ request }) => {
    const res = await request.get("/api/portfolio");
    expect(res.status()).toBe(200);
    const body = await res.json();
    for (const key of ["cash", "total_value", "positions_value", "unrealized_pnl"]) {
      expect(typeof body[key]).toBe("number");
    }
    expect(Array.isArray(body.positions)).toBe(true);
  });

  test("GET /api/watchlist lists the default tickers with prices", async ({ request }) => {
    await waitForPrice(request, "AAPL");
    const rows = await (await request.get("/api/watchlist")).json();
    expect(rows.length).toBeGreaterThanOrEqual(10);
    expect(rows[0]).toEqual(
      expect.objectContaining({
        ticker: expect.any(String),
        price: expect.any(Number),
        previous_price: expect.any(Number),
        change_percent: expect.any(Number),
        direction: expect.any(String),
      }),
    );
    expect(rows[0]).toHaveProperty("day_change_percent");
  });

  test("watchlist add, duplicate, remove, remove unknown", async ({ request }) => {
    const add = await request.post("/api/watchlist", { data: { ticker: "IBM" } });
    expect(add.status()).toBe(201);
    expect(await add.json()).toEqual({ ticker: "IBM" });

    const dup = await request.post("/api/watchlist", { data: { ticker: "IBM" } });
    expect(dup.status()).toBe(400);
    expect(await dup.json()).toHaveProperty("detail");

    await waitForPrice(request, "IBM");

    const del = await request.delete("/api/watchlist/IBM");
    expect(del.status()).toBe(200);
    expect(await del.json()).toEqual({ ticker: "IBM" });

    const missing = await request.delete("/api/watchlist/IBM");
    expect(missing.status()).toBe(404);
  });

  test("buy then sell updates cash and positions", async ({ request }) => {
    await waitForPrice(request, "JPM");
    const before = await (await request.get("/api/portfolio")).json();
    const held = await heldQuantity(request, "JPM");

    const buy = await request.post("/api/portfolio/trade", { data: { ticker: "JPM", quantity: 2, side: "buy" } });
    expect(buy.status()).toBe(200);
    const bought = await buy.json();
    expect(bought.trade).toEqual(
      expect.objectContaining({ id: expect.any(String), ticker: "JPM", side: "buy", quantity: 2, price: expect.any(Number), executed_at: expect.any(String) }),
    );
    expect(bought.portfolio.cash).toBeCloseTo(before.cash - 2 * bought.trade.price, 2);
    const position = bought.portfolio.positions.find((p: { ticker: string }) => p.ticker === "JPM");
    expect(position.quantity).toBeCloseTo(held + 2);
    for (const key of ["avg_cost", "current_price", "market_value", "unrealized_pnl", "pnl_percent"]) {
      expect(typeof position[key]).toBe("number");
    }

    const sell = await request.post("/api/portfolio/trade", { data: { ticker: "JPM", quantity: 2, side: "sell" } });
    expect(sell.status()).toBe(200);
    const sold = await sell.json();
    expect(sold.portfolio.cash).toBeCloseTo(bought.portfolio.cash + 2 * sold.trade.price, 2);
    expect(await heldQuantity(request, "JPM")).toBeCloseTo(held);
  });

  test("trade validation errors return 400", async ({ request }) => {
    await waitForPrice(request, "AAPL");
    const tooMuch = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", quantity: 1_000_000, side: "buy" } });
    expect(tooMuch.status()).toBe(400);
    expect(await tooMuch.json()).toHaveProperty("detail");

    const oversell = await request.post("/api/portfolio/trade", { data: { ticker: "V", quantity: 1_000_000, side: "sell" } });
    expect(oversell.status()).toBe(400);

    const unknown = await request.post("/api/portfolio/trade", { data: { ticker: "ZZZZ", quantity: 1, side: "buy" } });
    expect(unknown.status()).toBe(400);
  });

  test("GET /api/portfolio/history has snapshots after a trade", async ({ request }) => {
    const res = await request.get("/api/portfolio/history");
    expect(res.status()).toBe(200);
    const history = await res.json();
    expect(history.length).toBeGreaterThan(0);
    expect(history[0]).toEqual({ total_value: expect.any(Number), recorded_at: expect.any(String) });
  });

  test("chat (mock): default reply", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "hello there" } });
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({
      message: "Mock response: I can help with your portfolio.",
      trades: [],
      watchlist_changes: [],
    });
  });

  test("chat (mock): buy executes a trade", async ({ request }) => {
    await waitForPrice(request, "MSFT");
    const held = await heldQuantity(request, "MSFT");
    const body = await (await request.post("/api/chat", { data: { message: "buy 1 MSFT" } })).json();
    expect(body.message).toBe("Buying 1 MSFT.");
    expect(body.trades).toEqual([
      expect.objectContaining({ ticker: "MSFT", side: "buy", quantity: 1, status: "executed", price: expect.any(Number), error: null }),
    ]);
    expect(await heldQuantity(request, "MSFT")).toBeCloseTo(held + 1);
  });

  test("chat (mock): failed sell reports an error", async ({ request }) => {
    const body = await (await request.post("/api/chat", { data: { message: "sell 100000 NFLX" } })).json();
    expect(body.trades).toEqual([
      expect.objectContaining({ ticker: "NFLX", side: "sell", status: "failed", error: expect.any(String) }),
    ]);
  });

  test("chat (mock): watch and unwatch", async ({ request }) => {
    const watch = await (await request.post("/api/chat", { data: { message: "watch ORCL" } })).json();
    expect(watch.watchlist_changes).toEqual([expect.objectContaining({ ticker: "ORCL", action: "add", status: "executed" })]);
    let tickers = (await (await request.get("/api/watchlist")).json()).map((r: { ticker: string }) => r.ticker);
    expect(tickers).toContain("ORCL");

    const unwatch = await (await request.post("/api/chat", { data: { message: "unwatch ORCL" } })).json();
    expect(unwatch.watchlist_changes).toEqual([expect.objectContaining({ ticker: "ORCL", action: "remove", status: "executed" })]);
    tickers = (await (await request.get("/api/watchlist")).json()).map((r: { ticker: string }) => r.ticker);
    expect(tickers).not.toContain("ORCL");
  });

  test("GET /api/chat/history returns stored messages", async ({ request }) => {
    const history = await (await request.get("/api/chat/history")).json();
    expect(history.length).toBeGreaterThanOrEqual(2);
    expect(history.at(-1)).toEqual(
      expect.objectContaining({ role: "assistant", content: expect.any(String), created_at: expect.any(String) }),
    );
    expect(history.at(-1)).toHaveProperty("actions");
  });

  test("GET /api/stream/prices is an SSE stream", async () => {
    const res = await fetch(new URL("/api/stream/prices", test.info().project.use.baseURL));
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const reader = res.body!.getReader();
    let text = "";
    while (!text.includes("data: ")) text += new TextDecoder().decode((await reader.read()).value);
    await reader.cancel();
    expect(text).toContain("retry:");
  });
});
