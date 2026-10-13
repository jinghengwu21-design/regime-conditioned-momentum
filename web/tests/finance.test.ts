import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { stress, filterTrades, tradesCSV } from "../src/finance.ts";
import type { Terminal } from "../src/types.ts";
const data: Terminal = JSON.parse(
  fs.readFileSync(
    new URL("../public/data/terminal.json", import.meta.url),
    "utf8",
  ),
);

test("browser cost engine reconciles to Python across periods and fees", () => {
  for (const period of Object.values(data.periods)) {
    [5, 8, 12].forEach((fee, i) => {
      const result = stress(period, fee, 0),
        expected = period.scenarios[i].metrics;
      assert.ok(Math.abs(result.equity - expected.final_equity) < 1e-6);
      assert.ok(Math.abs(result.maxDrawdown - expected.max_drawdown) < 1e-10);
      assert.ok(Math.abs(result.totalCost - expected.added_fee_usdt) < 1e-6);
    });
  }
});
test("slippage is charged on every fill notional", () => {
  const p = data.periods.all;
  assert.ok(Math.abs(stress(p, 5, 3).equity - stress(p, 8, 0).equity) < 1e-8);
});
test("month and outcome filters intersect; export contains selected rows only", () => {
  const trades = filterTrades(data.periods.all.trades, "", "win", "2024-05");
  assert.ok(trades.length > 0);
  assert.ok(trades.every((t) => t.closed.startsWith("2024-05") && t.pnl > 0));
  assert.equal(tradesCSV(trades).split("\r\n").length, trades.length + 1);
  assert.equal(
    filterTrades(data.periods.all.trades, "not-a-trade", "all", "").length,
    0,
  );
});
