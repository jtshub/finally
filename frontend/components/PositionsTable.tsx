import { money, pct, price, signedMoney, tone } from "@/lib/format";
import type { Position } from "@/lib/types";

const qty = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(4));

/** Tabular view of open positions with live P&L. */
export function PositionsTable({ positions, onSelect }: { positions: Position[]; onSelect: (t: string) => void }) {
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <h2 className="border-b border-line px-3 py-2 font-medium">Positions</h2>
      <div className="min-h-0 flex-1 overflow-auto">
        <table data-testid="positions-table" className="w-full text-right">
          <thead className="sticky top-0 bg-panel text-muted">
            <tr className="[&>th]:px-3 [&>th]:py-1.5 [&>th]:font-normal">
              <th className="text-left">Ticker</th>
              <th>Qty</th>
              <th>Avg cost</th>
              <th>Price</th>
              <th>Value</th>
              <th>Unrealized P&amp;L</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody className="num">
            {positions.map((p) => (
              <tr
                key={p.ticker}
                data-testid={`position-row-${p.ticker}`}
                onClick={() => onSelect(p.ticker)}
                className="cursor-pointer border-t border-line/50 hover:bg-raised [&>td]:px-3 [&>td]:py-1.5"
              >
                <td className="text-left font-sans font-medium">{p.ticker}</td>
                <td>{qty(p.quantity)}</td>
                <td>{price(p.avg_cost)}</td>
                <td>{price(p.current_price)}</td>
                <td>{money(p.market_value)}</td>
                <td className={tone(p.unrealized_pnl)}>{signedMoney(p.unrealized_pnl)}</td>
                <td className={tone(p.pnl_percent)}>{pct(p.pnl_percent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!positions.length && <p className="p-3 text-muted">No positions yet. Use the trade bar to buy your first shares.</p>}
      </div>
    </section>
  );
}
