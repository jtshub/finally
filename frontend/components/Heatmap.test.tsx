import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Position } from "@/lib/types";
import { Heatmap, pnlColor } from "./Heatmap";

const pos = (ticker: string, market_value: number, pnl_percent: number) =>
  ({ ticker, market_value, pnl_percent }) as Position;

describe("Heatmap", () => {
  it("colors gains green and losses red", () => {
    expect(pnlColor(2)).toMatch(/^rgba\(38,194,129/);
    expect(pnlColor(-2)).toMatch(/^rgba\(239,83,80/);
  });

  it("renders one cell per held position", () => {
    render(<Heatmap positions={[pos("AAPL", 600, 3), pos("TSLA", 400, -1)]} />);
    expect(screen.getByTestId("heatmap-cell-AAPL")).toHaveTextContent("+3.00%");
    expect(screen.getByTestId("heatmap-cell-TSLA")).toHaveTextContent("-1.00%");
  });

  it("shows an empty state with no positions", () => {
    render(<Heatmap positions={[]} />);
    expect(screen.getByTestId("heatmap")).toHaveTextContent("Buy a stock");
  });
});
