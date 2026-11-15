"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, TradeResult, WatchlistChangeResult } from "@/lib/types";

function describeTrade(t: TradeResult) {
  const verb = t.side === "buy" ? "Bought" : "Sold";
  return t.status === "executed"
    ? `${verb} ${t.quantity} ${t.ticker}${t.price != null ? ` at ${t.price.toFixed(2)}` : ""}`
    : `Could not ${t.side} ${t.quantity} ${t.ticker}: ${t.error}`;
}

function describeChange(c: WatchlistChangeResult) {
  const verb = c.action === "add" ? "Added" : "Removed";
  const place = c.action === "add" ? "to" : "from";
  return c.status === "executed"
    ? `${verb} ${c.ticker} ${place} watchlist`
    : `Could not ${c.action} ${c.ticker}: ${c.error}`;
}

function Action({ ok, text }: { ok: boolean; text: string }) {
  return (
    <li
      data-testid="chat-action"
      data-status={ok ? "executed" : "failed"}
      className={`num border-l-2 px-2 py-0.5 text-xs ${ok ? "border-up text-up" : "border-down text-down"}`}
    >
      {text}
    </li>
  );
}

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (text: string) => void;
}

/** Collapsible AI assistant sidebar with conversation, inline action confirmations and loading state. */
export function ChatPanel({ messages, loading, onSend }: Props) {
  const [open, setOpen] = useState(true);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages, loading]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || loading) return;
    onSend(msg);
    setText("");
  }

  if (!open) {
    return (
      <aside data-testid="chat-panel" data-open="false" className="border-l border-line bg-panel">
        <button onClick={() => setOpen(true)} className="h-full px-2 text-muted [writing-mode:vertical-rl] hover:text-accent">
          Open assistant
        </button>
      </aside>
    );
  }

  return (
    <aside data-testid="chat-panel" data-open="true" className="flex w-[340px] min-h-0 flex-col border-l border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <h2 className="font-medium">Assistant</h2>
        <button aria-label="Collapse assistant" onClick={() => setOpen(false)} className="text-muted hover:text-ink">
          »
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {!messages.length && (
          <p className="text-muted">FinAlly can analyze your holdings, place trades and manage your watchlist.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} data-testid="chat-message" data-role={m.role} className={m.role === "user" ? "ml-8" : "mr-4"}>
            <div
              className={`whitespace-pre-wrap px-3 py-2 leading-relaxed ${
                m.role === "user" ? "bg-raised text-ink" : "border-l-2 border-accent bg-canvas/60"
              }`}
            >
              {m.content}
            </div>
            {(m.trades?.length || m.watchlist_changes?.length) ? (
              <ul className="mt-1 space-y-1">
                {m.trades?.map((t, k) => <Action key={`t${k}`} ok={t.status === "executed"} text={describeTrade(t)} />)}
                {m.watchlist_changes?.map((c, k) => (
                  <Action key={`w${k}`} ok={c.status === "executed"} text={describeChange(c)} />
                ))}
              </ul>
            ) : null}
          </div>
        ))}
        {loading && (
          <div data-testid="chat-loading" className="flex items-center gap-1 text-muted" aria-live="polite">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent [animation-delay:300ms]" />
            <span className="ml-1">Thinking</span>
          </div>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="flex gap-1 border-t border-line p-2">
        <input
          data-testid="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask, or say “buy 5 AAPL”"
          className="min-w-0 flex-1 border border-line bg-canvas px-2 py-1.5 placeholder:text-muted"
        />
        <button
          data-testid="chat-send-button"
          disabled={loading}
          className="bg-secondary px-4 font-medium text-white hover:brightness-110 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </aside>
  );
}
