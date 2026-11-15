import { money, signedMoney, tone } from "@/lib/format";
import type { ConnectionStatus, Portfolio } from "@/lib/types";

const DOT: Record<ConnectionStatus, string> = {
  connected: "bg-up",
  reconnecting: "bg-accent",
  disconnected: "bg-down",
};

const LABEL: Record<ConnectionStatus, string> = {
  connected: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Offline",
};

/** Top bar: brand, live portfolio value, cash and stream status. */
export function Header({ portfolio, status }: { portfolio: Portfolio | null; status: ConnectionStatus }) {
  return (
    <header className="flex items-center gap-8 border-b border-line bg-panel px-4 py-2">
      <div className="flex items-baseline gap-1 text-[15px] font-semibold tracking-tight">
        <span className="text-accent">Fin</span>
        <span>Ally</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-muted">Portfolio</span>
        <span data-testid="header-total-value" className="num text-xl font-medium text-ink">
          {portfolio ? money(portfolio.total_value) : "—"}
        </span>
        {portfolio && (
          <span className={`num text-xs ${tone(portfolio.unrealized_pnl)}`}>
            {signedMoney(portfolio.unrealized_pnl)}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-muted">Cash</span>
        <span data-testid="header-cash" className="num text-ink">
          {portfolio ? money(portfolio.cash) : "—"}
        </span>
      </div>
      <div
        data-testid="connection-status"
        data-status={status}
        title={`Price stream: ${status}`}
        className="ml-auto flex items-center gap-2 text-xs text-muted"
      >
        <span className={`h-2 w-2 rounded-full ${DOT[status]}`} />
        {LABEL[status]}
      </div>
    </header>
  );
}
