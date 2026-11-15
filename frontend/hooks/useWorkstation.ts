"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChatMessage, Portfolio, Side, Snapshot } from "@/lib/types";

const HISTORY_REFRESH_MS = 30_000;

/** Server-backed app state (portfolio, P&L history, watchlist, chat) plus the actions that change it. */
export function useWorkstation() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [tickers, setTickers] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const refreshPortfolio = useCallback(async () => {
    const [p, h] = await Promise.all([api.portfolio(), api.history()]);
    setPortfolio(p);
    setSnapshots(h);
  }, []);

  const refreshWatchlist = useCallback(async () => {
    setTickers((await api.watchlist()).map((w) => w.ticker));
  }, []);

  useEffect(() => {
    refreshPortfolio();
    refreshWatchlist();
    api.chatHistory().then((items) =>
      setMessages(items.map((m) => ({ role: m.role, content: m.content, ...m.actions }))),
    );
    const id = setInterval(() => api.history().then(setSnapshots), HISTORY_REFRESH_MS);
    return () => clearInterval(id);
  }, [refreshPortfolio, refreshWatchlist]);

  const trade = useCallback(
    async (ticker: string, quantity: number, side: Side) => {
      const res = await api.trade(ticker, quantity, side);
      setPortfolio(res.portfolio);
      setSnapshots(await api.history());
    },
    [],
  );

  const addTicker = useCallback(async (ticker: string) => {
    await api.addTicker(ticker);
    await refreshWatchlist();
  }, [refreshWatchlist]);

  const removeTicker = useCallback(async (ticker: string) => {
    await api.removeTicker(ticker);
    await refreshWatchlist();
  }, [refreshWatchlist]);

  const sendChat = useCallback(
    async (text: string) => {
      setMessages((m) => [...m, { role: "user", content: text }]);
      setChatLoading(true);
      try {
        const res = await api.chat(text);
        setMessages((m) => [...m, { role: "assistant", ...res, content: res.message }]);
        if (res.trades.length) await refreshPortfolio();
        if (res.watchlist_changes.length) await refreshWatchlist();
      } catch (err) {
        setMessages((m) => [...m, { role: "assistant", content: `Request failed: ${(err as Error).message}` }]);
      } finally {
        setChatLoading(false);
      }
    },
    [refreshPortfolio, refreshWatchlist],
  );

  return { portfolio, snapshots, tickers, messages, chatLoading, trade, addTicker, removeTicker, sendChat };
}
