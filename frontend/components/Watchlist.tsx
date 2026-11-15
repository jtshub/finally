"use client";

import { useState } from "react";
import type { PricePoint } from "@/hooks/usePriceStream";
import { pct, tone } from "@/lib/format";
import type { PriceTick } from "@/lib/types";
import { FlashPrice } from "./FlashPrice";
import { Sparkline } from "./Sparkline";

interface Props {
  tickers: string[];
  prices: Record<string, PriceTick>;
  history: Record<string, PricePoint[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}

/** Watched tickers with flashing prices, daily change, sparklines, and add/remove controls. */
export function Watchlist({ tickers, prices, history, selected, onSelect, onAdd, onRemove }: Props) {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (!ticker) return;
    try {
      await onAdd(ticker);
      setInput("");
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <h2 className="border-b border-line px-3 py-2 font-medium">Watchlist</h2>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {tickers.map((t) => {
          const tick = prices[t];
          const active = t === selected;
          return (
            <li
              key={t}
              data-testid={`watchlist-row-${t}`}
              onClick={() => onSelect(t)}
              className={`group grid cursor-pointer grid-cols-[3.5rem_1fr_4.5rem_auto] items-center gap-2 border-b border-line/50 py-1.5 pr-2 pl-3 hover:bg-raised ${
                active ? "bg-raised shadow-[inset_2px_0_0_var(--color-primary)]" : ""
              }`}
            >
              <span className="font-medium">{t}</span>
              <span className="text-right">
                <FlashPrice value={tick?.price ?? null} testId={`watchlist-price-${t}`} />
                <span className={`num block text-[11px] ${tone(tick?.day_change_percent)}`}>
                  {pct(tick?.day_change_percent)}
                </span>
              </span>
              <Sparkline points={history[t] ?? []} />
              <button
                data-testid={`watchlist-remove-${t}`}
                aria-label={`Remove ${t}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(t);
                }}
                className="w-4 text-muted opacity-40 group-hover:opacity-100 hover:text-down"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
      <form onSubmit={submit} className="flex gap-1 border-t border-line p-2">
        <input
          data-testid="watchlist-add-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker"
          className="num min-w-0 flex-1 border border-line bg-canvas px-2 py-1 uppercase placeholder:normal-case placeholder:text-muted"
        />
        <button data-testid="watchlist-add-button" className="border border-primary px-3 text-primary hover:bg-primary hover:text-canvas">
          Add
        </button>
      </form>
      {error && <p className="px-2 pb-2 text-xs text-down">{error}</p>}
    </section>
  );
}
