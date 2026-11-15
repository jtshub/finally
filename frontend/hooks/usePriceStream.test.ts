import { describe, expect, it } from "vitest";
import { applySnapshot, initialPriceState } from "./usePriceStream";
import type { PriceTick } from "@/lib/types";

const tick = (ticker: string, price: number, timestamp: number): PriceTick => ({
  ticker, price, timestamp, previous_price: price, change: 0, change_percent: 0,
  direction: "flat", prev_close: null, day_change_percent: null,
});

describe("applySnapshot", () => {
  it("records latest prices and appends history", () => {
    let s = applySnapshot(initialPriceState, { AAPL: tick("AAPL", 190, 1) });
    s = applySnapshot(s, { AAPL: tick("AAPL", 191, 2) });
    expect(s.prices.AAPL.price).toBe(191);
    expect(s.history.AAPL).toEqual([{ time: 1, value: 190 }, { time: 2, value: 191 }]);
  });

  it("skips history for unchanged timestamps", () => {
    let s = applySnapshot(initialPriceState, { AAPL: tick("AAPL", 190, 1) });
    s = applySnapshot(s, { AAPL: tick("AAPL", 190, 1), MSFT: tick("MSFT", 400, 1) });
    expect(s.history.AAPL).toHaveLength(1);
    expect(s.history.MSFT).toHaveLength(1);
  });
});
