import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ChatMessage } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";

const messages: ChatMessage[] = [
  { role: "user", content: "buy 5 AAPL" },
  {
    role: "assistant",
    content: "Buying 5 AAPL.",
    trades: [{ ticker: "AAPL", side: "buy", quantity: 5, status: "executed", price: 190.5, error: null }],
    watchlist_changes: [{ ticker: "PYPL", action: "add", status: "failed", error: "Already watched" }],
  },
];

describe("ChatPanel", () => {
  it("renders messages and inline action confirmations", () => {
    render(<ChatPanel messages={messages} loading={false} onSend={vi.fn()} />);
    expect(screen.getAllByTestId("chat-message")).toHaveLength(2);
    const actions = screen.getAllByTestId("chat-action");
    expect(actions[0]).toHaveTextContent("Bought 5 AAPL at 190.50");
    expect(actions[1]).toHaveTextContent("Could not add PYPL: Already watched");
    expect(actions[1]).toHaveAttribute("data-status", "failed");
  });

  it("shows loading indicator and disables send while waiting", () => {
    render(<ChatPanel messages={[]} loading onSend={vi.fn()} />);
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send-button")).toBeDisabled();
  });

  it("sends trimmed text and clears input", async () => {
    const onSend = vi.fn();
    render(<ChatPanel messages={[]} loading={false} onSend={onSend} />);
    await userEvent.type(screen.getByTestId("chat-input"), "  hello  ");
    await userEvent.click(screen.getByTestId("chat-send-button"));
    expect(onSend).toHaveBeenCalledWith("hello");
    expect(screen.getByTestId("chat-input")).toHaveValue("");
  });

  it("collapses and reopens", async () => {
    render(<ChatPanel messages={[]} loading={false} onSend={vi.fn()} />);
    await userEvent.click(screen.getByLabelText("Collapse assistant"));
    expect(screen.getByTestId("chat-panel")).toHaveAttribute("data-open", "false");
    await userEvent.click(screen.getByText("Open assistant"));
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
  });
});
