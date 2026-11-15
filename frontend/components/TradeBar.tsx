"use client";

import { useState } from "react";
import type { Side } from "@/lib/types";

/** Ticker + quantity inputs with Buy/Sell market-order buttons. */
export function TradeBar({ ticker, onTrade }: { ticker: string | null; onTrade: (t: string, q: number, s: Side) => Promise<void> }) {
  const [symbol, setSymbol] = useState(ticker ?? "");
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [lastTicker, setLastTicker] = useState(ticker);
  if (ticker !== lastTicker) {
    setLastTicker(ticker);
    if (ticker) setSymbol(ticker);
  }

  async function trade(side: Side) {
    const t = symbol.trim().toUpperCase();
    const q = Number(quantity);
    if (!t || !(q > 0)) {
      setError("Enter a ticker and a quantity above zero.");
      return;
    }
    setBusy(true);
    try {
      await onTrade(t, q, side);
      setError(null);
      setQuantity("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const field = "num border border-line bg-canvas px-2 py-1.5 placeholder:font-sans placeholder:text-muted";
  return (
    <form onSubmit={(e) => e.preventDefault()} className="flex flex-wrap items-center gap-2 border-t border-line bg-panel px-3 py-2">
      <span className="text-muted">Market order</span>
      <input
        data-testid="trade-ticker-input"
        aria-label="Ticker"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        placeholder="Ticker"
        className={`${field} w-24 uppercase`}
      />
      <input
        data-testid="trade-quantity-input"
        aria-label="Quantity"
        type="number"
        min="0"
        step="any"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Shares"
        className={`${field} w-24`}
      />
      <button
        data-testid="trade-buy-button"
        disabled={busy}
        onClick={() => trade("buy")}
        className="bg-up px-4 py-1.5 font-medium text-canvas hover:brightness-110 disabled:opacity-50"
      >
        Buy
      </button>
      <button
        data-testid="trade-sell-button"
        disabled={busy}
        onClick={() => trade("sell")}
        className="bg-down px-4 py-1.5 font-medium text-canvas hover:brightness-110 disabled:opacity-50"
      >
        Sell
      </button>
      {error && (
        <span data-testid="trade-error" role="alert" className="text-down">
          {error}
        </span>
      )}
    </form>
  );
}
