import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PriceTick } from "@/lib/types";
import { Watchlist } from "./Watchlist";

const tick = { price: 190.5, day_change_percent: 1.25 } as PriceTick;

function setup(onAdd = vi.fn().mockResolvedValue(undefined)) {
  const props = {
    tickers: ["AAPL", "MSFT"],
    prices: { AAPL: tick },
    history: {},
    selected: "AAPL",
    onSelect: vi.fn(),
    onAdd,
    onRemove: vi.fn().mockResolvedValue(undefined),
  };
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("renders rows with prices and placeholders", () => {
    setup();
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("190.50");
    expect(screen.getByTestId("watchlist-row-AAPL")).toHaveTextContent("+1.25%");
    expect(screen.getByTestId("watchlist-price-MSFT")).toHaveTextContent("—");
  });

  it("adds an uppercased ticker and clears the input", async () => {
    const props = setup();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));
    expect(props.onAdd).toHaveBeenCalledWith("PYPL");
    expect(screen.getByTestId("watchlist-add-input")).toHaveValue("");
  });

  it("shows the server error when add fails", async () => {
    setup(vi.fn().mockRejectedValue(new Error("Unknown ticker")));
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "zzzz");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));
    expect(await screen.findByText("Unknown ticker")).toBeInTheDocument();
  });

  it("removes without selecting the row", async () => {
    const props = setup();
    await userEvent.click(screen.getByTestId("watchlist-remove-MSFT"));
    expect(props.onRemove).toHaveBeenCalledWith("MSFT");
    expect(props.onSelect).not.toHaveBeenCalled();
  });

  it("selects a ticker on row click", async () => {
    const props = setup();
    await userEvent.click(screen.getByTestId("watchlist-row-MSFT"));
    expect(props.onSelect).toHaveBeenCalledWith("MSFT");
  });
});
