"""Research-terminal analytics over a frozen, closed-trade account.

The benchmark is an unlevered price reference. Trade statistics use trades;
calendar statistics use UTC daily account returns. Neither is substituted for
the other. All aggregation is causal with respect to the archived timestamps.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from .data import DataStore
from .metrics import calculate


def drawdown_episodes(curve: list[dict]) -> list[dict]:
    """Peak-to-recovery episodes, retaining the right-censored final episode."""
    peak = curve[0]
    episode = None
    episodes = []
    for row in curve[1:]:
        if row["equity"] >= peak["equity"]:
            if episode:
                episode.update(recovery=row["date"], recovered=True)
                episodes.append(episode)
                episode = None
            peak = row
        else:
            depth = 1 - row["equity"] / peak["equity"]
            if episode is None:
                episode = {"peak": peak["date"], "trough": row["date"], "depth": depth,
                           "recovery": None, "recovered": False}
            elif depth > episode["depth"]:
                episode.update(trough=row["date"], depth=depth)
    if episode:
        episodes.append(episode)
    for item in episodes:
        end = item["recovery"] or curve[-1]["date"]
        item["days"] = (pd.Timestamp(end) - pd.Timestamp(item["peak"])).total_seconds() / 86400
    return sorted(episodes, key=lambda item: item["depth"], reverse=True)


def portfolio_analytics(store: DataStore, start: str, end: str) -> dict:
    base = calculate(store, start, end)
    left, right = store.window(start, end)
    trades = store.trades.loc[(store.trades.close_date >= left) & (store.trades.close_date < right)].copy()
    opening = base["metrics"]["opening_equity"]
    days = pd.date_range(left.floor("D"), (right - pd.Timedelta(nanoseconds=1)).floor("D"), freq="D")
    daily_pnl = trades.groupby(trades.close_date.dt.floor("D")).profit_abs.sum().reindex(days, fill_value=0)
    equity = opening + daily_pnl.cumsum()
    returns = daily_pnl / equity.shift(1, fill_value=opening)
    roll_sigma = returns.rolling(126).std(ddof=1)
    rolling = returns.rolling(126).mean() / roll_sigma.replace(0, np.nan) * math.sqrt(365)
    monthly = []
    for month, frame in returns.groupby(returns.index.strftime("%Y-%m")):
        subset = trades[trades.close_date.dt.strftime("%Y-%m") == month]
        monthly.append({"month": month, "return": float((1 + frame).prod() - 1),
                        "trades": len(subset), "pnl": float(subset.profit_abs.sum())})
    market = store.market[(store.market.date >= left.ceil("D")) & (store.market.date + pd.Timedelta(days=1) <= right)]
    benchmark = []
    if not market.empty:
        first_open = float(market.iloc[0].open)
        start_equity = opening + float(trades.loc[trades.close_date < market.iloc[0].date, "profit_abs"].sum())
        for bar in market.itertuples():
            account = float(equity.loc[bar.date])
            benchmark.append({"date": bar.date.strftime("%Y-%m-%d"),
                              "strategy": account / start_equity * 100,
                              "benchmark": float(bar.close / first_open * (1 - .0005) / (1 + .0005) * 100)})
    trade_rows = []
    fills = pd.read_csv(store.directory / "fills.csv")
    fills_by_trade = {key: group for key, group in fills.groupby("trade_id")}
    for row in trades.itertuples():
        fs = fills_by_trade[row.trade_id]
        entries = fs[fs.is_entry]
        exits = fs[~fs.is_entry]
        trade_rows.append({"id": row.trade_id, "opened": row.open_date.isoformat(),
                           "closed": row.close_date.isoformat(), "pnl": float(row.profit_abs),
                           "duration_hours": (row.close_date - row.open_date).total_seconds() / 3600,
                           "entry_price": float(entries.notional_usdt.sum() / entries.amount.sum()),
                           "exit_price": float(exits.notional_usdt.sum() / exits.amount.sum()),
                           "entries": int(row.entry_count), "leverage": float(row.leverage),
                           "reason": row.exit_reason, "turnover": float(row.entry_notional_usdt + row.exit_notional_usdt),
                           "fills": fs.to_dict("records")})
    attribution = []
    for reason, group in trades.groupby("exit_reason"):
        attribution.append({"reason": reason, "count": len(group), "pnl": float(group.profit_abs.sum()),
                            "win_rate": float((group.profit_abs > 1e-7).mean())})
    winners = trades[trades.profit_abs > 1e-7].profit_abs
    losers = trades[trades.profit_abs < -1e-7].profit_abs
    losing_streak = longest = 0
    for value in trades.profit_abs:
        losing_streak = losing_streak + 1 if value < -1e-7 else 0
        longest = max(longest, losing_streak)
    var = float(returns.quantile(.05))
    risk = {"daily_volatility": float(returns.std(ddof=1) * math.sqrt(365)),
            "historical_var95": -var, "historical_es95": float(-returns[returns <= var].mean()),
            "max_losing_streak": longest,
            "payoff": float(winners.mean() / -losers.mean()) if len(winners) and len(losers) else None,
            "average_winner": float(winners.mean()) if len(winners) else None,
            "average_loser": float(losers.mean()) if len(losers) else None,
            "top10_pnl_share": float(trades.nlargest(10, "profit_abs").profit_abs.sum() / trades.profit_abs.sum()) if trades.profit_abs.sum() else None,
            "break_even_fee_bps": float(5 + trades.profit_abs.sum() / base["metrics"]["turnover_usdt"] * 10000) if len(trades) else None,
            "median_hold_hours": float(((trades.close_date - trades.open_date).dt.total_seconds() / 3600).median()) if len(trades) else None}
    return {"base": base, "monthly": monthly, "benchmark": benchmark,
            "benchmark_method": "Unlevered BTC price reference; first complete-day open to daily close; 5 bps entry and liquidation; strategy rebased on the identical complete-day window.",
            "daily": [{"date": day.strftime("%Y-%m-%d"), "equity": float(equity.loc[day]),
                       "return": float(returns.loc[day]), "rolling_sharpe": float(rolling.loc[day]) if pd.notna(rolling.loc[day]) else None} for day in days],
            "drawdowns": drawdown_episodes(base["curve"])[:10], "trades": trade_rows,
            "attribution": sorted(attribution, key=lambda item: item["pnl"], reverse=True), "risk": risk,
            "scenarios": [calculate(store, start, end, fee, 0) for fee in [5, 8, 12]]}
