export interface Metrics {
  trade_count: number;
  opening_equity: number;
  final_equity: number;
  total_return: number;
  cagr: number | null;
  max_drawdown: number;
  daily_sharpe: number | null;
  profit_factor: number | null;
  win_rate: number | null;
  added_fee_usdt: number;
  turnover_usdt: number;
  trades_with_add: number;
  solvent: boolean;
}
export interface CurvePoint {
  date: string;
  equity: number;
  drawdown: number;
}
export interface Base {
  metrics: Metrics;
  curve: CurvePoint[];
  yearly: {
    year: number;
    trades: number;
    return: number;
    profit_usdt: number;
  }[];
  scope: { start: string; end_exclusive: string; cagr_days: number };
}
export interface Fill {
  timestamp: string;
  side: string;
  is_entry: boolean;
  amount: number;
  price: number;
  notional_usdt: number;
}
export interface Trade {
  id: string;
  opened: string;
  closed: string;
  pnl: number;
  duration_hours: number;
  entry_price: number;
  exit_price: number;
  entries: number;
  leverage: number;
  reason: string;
  turnover: number;
  fills: Fill[];
}
export interface Period {
  base: Base;
  monthly: { month: string; return: number; trades: number; pnl: number }[];
  benchmark: { date: string; strategy: number; benchmark: number }[];
  daily: {
    date: string;
    equity: number;
    return: number;
    rolling_sharpe: number | null;
  }[];
  drawdowns: {
    peak: string;
    trough: string;
    depth: number;
    recovery: string | null;
    recovered: boolean;
    days: number;
  }[];
  trades: Trade[];
  attribution: {
    reason: string;
    count: number;
    pnl: number;
    win_rate: number;
  }[];
  risk: {
    daily_volatility: number;
    historical_var95: number;
    historical_es95: number;
    max_losing_streak: number;
    payoff: number | null;
    average_winner: number | null;
    average_loser: number | null;
    top10_pnl_share: number | null;
    break_even_fee_bps: number | null;
    median_hold_hours: number | null;
  };
  scenarios: Base[];
}
export interface Evidence {
  id: string;
  title: string;
  source: string;
  text: string;
}
export interface Terminal {
  version: string;
  asof: string;
  periods: Record<string, Period>;
  evidence: Evidence[];
  manifest: {
    dataset_id: string;
    files: Record<string, { bytes: number }>;
  };
}
export interface Trace {
  sequence: number;
  node: string;
  action: string;
  status: string;
  elapsed_ms: number;
  input: unknown;
  output: unknown;
  time_utc: string;
}
export interface Run {
  run_id: string;
  recorded_at_utc: string;
  mode: string;
  trace: Trace[];
  base: Base;
  request: {
    asset: string;
    start: string;
    end_exclusive: string;
    scenario: string;
    question: string;
    fee_bps: number;
    slippage_bps: number;
  };
  reviews: {
    passed: boolean;
    checked_claims: number;
    findings: unknown[];
    cost_scenarios_verified: number;
  }[];
  repaired: boolean;
  external: { quarantined: boolean };
  draft: {
    summary: string;
    findings: string[];
    claims: {
      metric: string;
      value: number;
      unit: string;
      evidence_id: string;
    }[];
  };
  original_draft: Run["draft"];
  market: { coverage: { missing_days: number; warnings: string[] } };
}
