import { pct } from "@/lib/format";
import { squarify } from "@/lib/treemap";
import type { Position } from "@/lib/types";

/** Background color for a P&L percent: green for gains, red for losses, saturating at ±5%. */
export function pnlColor(pnlPercent: number) {
  const a = 0.18 + Math.min(Math.abs(pnlPercent) / 5, 1) * 0.62;
  return pnlPercent >= 0 ? `rgba(38,194,129,${a.toFixed(2)})` : `rgba(239,83,80,${a.toFixed(2)})`;
}

/** Treemap of positions sized by market value and colored by unrealized P&L. */
export function Heatmap({ positions }: { positions: Position[] }) {
  const held = positions.filter((p) => p.market_value > 0);
  const rects = squarify(held.map((p) => p.market_value), { x: 0, y: 0, w: 100, h: 100 });
  return (
    <section data-testid="heatmap" className="flex min-h-0 flex-1 flex-col">
      <h2 className="border-b border-line px-3 py-2 font-medium">Holdings by weight</h2>
      <div className="relative m-2 min-h-0 flex-1">
        {!held.length && (
          <p className="absolute inset-0 grid place-items-center text-muted">Buy a stock to see it here.</p>
        )}
        {held.map((p, i) => {
          const r = rects[i];
          return (
            <div
              key={p.ticker}
              data-testid={`heatmap-cell-${p.ticker}`}
              title={`${p.ticker} ${pct(p.pnl_percent)}`}
              className="absolute overflow-hidden border border-canvas p-1 leading-tight"
              style={{ left: `${r.x}%`, top: `${r.y}%`, width: `${r.w}%`, height: `${r.h}%`, background: pnlColor(p.pnl_percent) }}
            >
              <div className="font-medium">{p.ticker}</div>
              <div className="num text-[11px]">{pct(p.pnl_percent)}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
