"use client";

import { useEffect, useReducer, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { ConnectionStatus, PriceTick } from "@/lib/types";

/** Max points kept per ticker for sparklines and the main chart. */
export const HISTORY_LIMIT = 600;

export interface PricePoint {
  time: number;
  value: number;
}

export interface PriceState {
  prices: Record<string, PriceTick>;
  history: Record<string, PricePoint[]>;
}

export const initialPriceState: PriceState = { prices: {}, history: {} };

/** Merge an SSE snapshot, appending a history point only for tickers whose timestamp moved. */
export function applySnapshot(state: PriceState, snapshot: Record<string, PriceTick>): PriceState {
  const history = { ...state.history };
  for (const [ticker, tick] of Object.entries(snapshot)) {
    const prev = state.prices[ticker];
    if (prev && prev.timestamp === tick.timestamp) continue;
    const points = history[ticker] ?? [];
    history[ticker] = [...points, { time: tick.timestamp, value: tick.price }].slice(-HISTORY_LIMIT);
  }
  return { prices: { ...state.prices, ...snapshot }, history };
}

/** Subscribe to /api/stream/prices; returns latest prices, accumulated history and connection status. */
export function usePriceStream() {
  const [state, dispatch] = useReducer(applySnapshot, initialPriceState);
  const [status, setStatus] = useState<ConnectionStatus>("reconnecting");

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/api/stream/prices`);
    source.onopen = () => setStatus("connected");
    source.onmessage = (e) => dispatch(JSON.parse(e.data));
    source.onerror = () =>
      setStatus(source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting");
    return () => source.close();
  }, []);

  return { ...state, status };
}
