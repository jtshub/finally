import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TradeBar } from "./TradeBar";

describe("TradeBar", () => {
  it("submits a buy with the selected ticker", async () => {
    const onTrade = vi.fn().mockResolvedValue(undefined);
    render(<TradeBar ticker="AAPL" onTrade={onTrade} />);
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "5");
    await userEvent.click(screen.getByTestId("trade-buy-button"));
    expect(onTrade).toHaveBeenCalledWith("AAPL", 5, "buy");
  });

  it("shows the server error on a failed sell", async () => {
    const onTrade = vi.fn().mockRejectedValue(new Error("Insufficient shares"));
    render(<TradeBar ticker="AAPL" onTrade={onTrade} />);
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "5");
    await userEvent.click(screen.getByTestId("trade-sell-button"));
    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Insufficient shares");
  });

  it("rejects an empty quantity without calling the API", async () => {
    const onTrade = vi.fn();
    render(<TradeBar ticker="AAPL" onTrade={onTrade} />);
    await userEvent.click(screen.getByTestId("trade-buy-button"));
    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toBeInTheDocument();
  });
});
