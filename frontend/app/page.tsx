"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { usePriceStream } from "@/hooks/usePriceStream";
import { useWorkstation } from "@/hooks/useWorkstation";
import { revalue } from "@/lib/portfolio";

const MainChart = dynamic(() => import("@/components/MainChart"), { ssr: false });
const PnlChart = dynamic(() => import("@/components/PnlChart"), { ssr: false });

export default function Home() {
  const { prices, history, status } = usePriceStream();
  const ws = useWorkstation();
  const [picked, setPicked] = useState<string | null>(null);
  const selected = picked ?? ws.tickers[0] ?? null;
  const live = useMemo(() => (ws.portfolio ? revalue(ws.portfolio, prices) : null), [ws.portfolio, prices]);

  return (
    <div className="flex h-screen flex-col">
      <Header portfolio={live} status={status} />
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[300px] shrink-0 flex-col border-r border-line bg-panel">
          <Watchlist
            tickers={ws.tickers}
            prices={prices}
            history={history}
            selected={selected}
            onSelect={setPicked}
            onAdd={ws.addTicker}
            onRemove={ws.removeTicker}
          />
        </aside>
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(220px,1.2fr)_minmax(180px,1fr)_minmax(140px,0.8fr)] lg:grid-cols-2 [&>*]:border-line">
            <div className="flex min-h-0 flex-col border-b lg:col-span-2">
              <MainChart ticker={selected} points={selected ? history[selected] ?? [] : []} tick={selected ? prices[selected] : undefined} />
            </div>
            <div className="flex min-h-0 flex-col border-b lg:border-r">
              <Heatmap positions={live?.positions ?? []} />
            </div>
            <div className="flex min-h-0 flex-col border-b">
              <PnlChart snapshots={ws.snapshots} />
            </div>
            <div className="flex min-h-0 flex-col lg:col-span-2">
              <PositionsTable positions={live?.positions ?? []} onSelect={setPicked} />
            </div>
          </div>
          <TradeBar ticker={selected} onTrade={ws.trade} />
        </main>
        <ChatPanel messages={ws.messages} loading={ws.chatLoading} onSend={ws.sendChat} />
      </div>
    </div>
  );
}
