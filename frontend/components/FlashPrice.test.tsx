import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FLASH_HOLD_MS, FlashPrice } from "./FlashPrice";

describe("FlashPrice", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("does not flash on first render", () => {
    render(<FlashPrice value={100} testId="p" />);
    expect(screen.getByTestId("p")).not.toHaveAttribute("data-flash");
    expect(screen.getByTestId("p")).toHaveTextContent("100.00");
  });

  it("flashes up on uptick then fades", () => {
    const { rerender } = render(<FlashPrice value={100} testId="p" />);
    rerender(<FlashPrice value={101} testId="p" />);
    expect(screen.getByTestId("p")).toHaveClass("flash-up");
    act(() => vi.advanceTimersByTime(FLASH_HOLD_MS));
    expect(screen.getByTestId("p")).toHaveClass("flash-fade");
  });

  it("flashes down on downtick", () => {
    const { rerender } = render(<FlashPrice value={100} testId="p" />);
    rerender(<FlashPrice value={99} testId="p" />);
    expect(screen.getByTestId("p")).toHaveClass("flash-down");
  });
});
