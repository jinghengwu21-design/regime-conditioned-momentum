import type { Period, Trade, CurvePoint } from "./types.ts";

export const percent = (n: number | null, digits = 2) =>
  n == null ? "—" : `${(n * 100).toFixed(digits)}%`;
export const number = (n: number | null, digits = 2) =>
  n == null
    ? "—"
    : n.toLocaleString("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export const date = (s: string) => s.slice(0, 10).replaceAll("-", ".");
export const reasonName = (s: string) =>
  ({
    stop_loss: "初始止损",
    trailing_stop_loss: "跟踪退出",
    force_exit: "区间结束",
    max_hold_24h: "持仓到期",
    time_exit_24h: "持仓到期",
  })[s] || s;

export function stress(period: Period, fee: number, slip: number) {
  const opening = period.base.metrics.opening_equity;
  let equity = opening,
    peak = opening,
    maxDrawdown = 0,
    totalCost = 0;
  const curve: CurvePoint[] = [
    { date: period.base.scope.start, equity, drawdown: 0 },
  ];
  const groups = new Map<string, number>();
  for (const trade of period.trades) {
    const cost = (trade.turnover * (fee - 5 + slip)) / 10000;
    totalCost += cost;
    groups.set(
      trade.closed,
      (groups.get(trade.closed) || 0) + trade.pnl - cost,
    );
  }
  for (const [timestamp, pnl] of [...groups].sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    equity += pnl;
    peak = Math.max(peak, equity);
    const drawdown = Math.max(0, 1 - equity / peak);
    maxDrawdown = Math.max(maxDrawdown, drawdown);
    curve.push({ date: timestamp, equity, drawdown });
  }
  curve.push({
    date: period.base.scope.end_exclusive,
    equity,
    drawdown: curve.at(-1)!.drawdown,
  });
  return {
    equity,
    maxDrawdown,
    totalCost,
    totalReturn: equity / opening - 1,
    curve,
  };
}

export function filterTrades(
  trades: Trade[],
  query: string,
  outcome: string,
  month: string,
) {
  return trades.filter(
    (t) =>
      (!query ||
        `${t.id} ${t.closed} ${t.reason}`
          .toLowerCase()
          .includes(query.toLowerCase())) &&
      (!month || t.closed.startsWith(month)) &&
      (outcome === "all" ||
        (outcome === "win"
          ? t.pnl > 1e-7
          : outcome === "loss"
            ? t.pnl < -1e-7
            : t.entries > 1)),
  );
}

export function tradesCSV(trades: Trade[]) {
  const quote = (value: string | number) =>
    `"${String(value).replaceAll('"', '""')}"`;
  return (
    "\uFEFF" +
    [
      [
        "trade_id",
        "open_utc",
        "close_utc",
        "pnl_usdt",
        "duration_hours",
        "entries",
        "turnover_usdt",
      ],
      ...trades.map((t) => [
        t.id,
        t.opened,
        t.closed,
        t.pnl,
        t.duration_hours,
        t.entries,
        t.turnover,
      ]),
    ]
      .map((row) => row.map(quote).join(","))
      .join("\r\n")
  );
}

export function download(content: string, name: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
