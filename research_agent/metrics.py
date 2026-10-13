"""Deterministic calculations, using the archived closed-trade ledger."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import DataStore

CALC_VERSION = "ledger-metrics-v1.0.0"
CASH_EPSILON = 1e-7  # USDT; avoid classifying float cancellation as a win/loss.


def calculate(store: DataStore, start: str, end: str, fee_bps: float = 5, slippage_bps: float = 0) -> dict:
    left, right = store.window(start, end)
    source = store.trades
    prior = source.loc[source.close_date < left]
    opening = float(store.manifest["starting_balance"] + prior.profit_abs.sum())
    part = source.loc[(source.close_date >= left) & (source.close_date < right)].copy()
    turnover = part.entry_notional_usdt + part.exit_notional_usdt
    incremental_rate = (fee_bps - store.manifest["base_fee_bps_per_side"] + slippage_bps) / 10000
    part["added_cost"] = turnover * incremental_rate
    part["net_pnl"] = part.profit_abs - part.added_cost
    part.loc[part.net_pnl.abs() < CASH_EPSILON, "net_pnl"] = 0.0
    pnl = part.groupby("close_date").net_pnl.sum()
    curve = pd.concat([pd.Series([opening], index=[left]), opening + pnl.cumsum(), pd.Series([opening + pnl.sum()], index=[right])]).sort_index().groupby(level=0).last()
    # Include pre-event opening capital when a trade closes exactly on the left boundary.
    peaks = curve.cummax().clip(lower=opening)
    dd = (1 - curve / peaks).clip(lower=0)
    daily_pnl = pnl.resample("D").sum().reindex(pd.date_range(left.floor("D"), (right - pd.Timedelta(nanoseconds=1)).floor("D"), freq="D"), fill_value=0.0)
    balances = opening + daily_pnl.cumsum()
    daily_returns = daily_pnl / balances.shift(1, fill_value=opening)
    solvency = bool((curve > 0).all()) and opening > 0
    sigma = float(daily_returns.std(ddof=1))
    native_left = max(left, pd.Timestamp(store.manifest["metric_start"]))
    native_right = min(right, pd.Timestamp(store.manifest["metric_end"]))
    days = (native_right - native_left).days
    final = float(curve.iloc[-1])
    gains = float(part.loc[part.net_pnl > 0, "net_pnl"].sum())
    losses = float(-part.loc[part.net_pnl < 0, "net_pnl"].sum())
    metrics = {
        "trade_count": len(part), "opening_equity": opening, "final_equity": final,
        "total_return": final / opening - 1,
        "cagr": (final / opening) ** (365 / days) - 1 if solvency and days > 0 else None,
        "max_drawdown": float(dd.max()),
        "daily_sharpe": float(daily_returns.mean() / sigma * np.sqrt(365)) if solvency and sigma > 0 and np.isfinite(sigma) else None,
        "profit_factor": gains / losses if losses else None,
        "win_rate": float((part.net_pnl > 0).mean()) if len(part) else None,
        "added_fee_usdt": float(part.added_cost.sum()), "turnover_usdt": float(turnover.sum()),
        "trades_with_add": int((part.entry_count > 1).sum()), "solvent": solvency,
    }
    curve_rows = [{"date": d.isoformat(), "equity": float(e), "drawdown": float(dd.loc[d])} for d, e in curve.items()]
    years = []
    balance = opening
    for year, frame in part.groupby(part.close_date.dt.year):
        gain = float(frame.net_pnl.sum())
        years.append({"year": int(year), "trades": len(frame), "return": gain / balance if balance > 0 else None, "profit_usdt": gain})
        balance += gain
    return {"metrics": metrics, "curve": curve_rows, "yearly": years, "scope": {"start": left.isoformat(), "end_exclusive": right.isoformat(), "metric_start": native_left.isoformat(), "metric_end": native_right.isoformat(), "cagr_days": days, "fee_bps_per_side": fee_bps, "slippage_bps_per_fill": slippage_bps, "subperiod_opening": "archived account balance before selected period", "cost_model": "fixed fill notional; extra cost recognized on trade close; no resizing or funding"}, "calc_version": CALC_VERSION}


def market_snapshot(store: DataStore, start: str, end: str) -> dict:
    left, right = pd.Timestamp(start), pd.Timestamp(end)
    frame = store.market.loc[(store.market.date >= left) & (store.market.date + pd.Timedelta(days=1) <= right)].copy()
    expected_start = left.ceil("D")
    expected_end = right.floor("D")
    expected = pd.date_range(expected_start, expected_end, freq="D", inclusive="left")
    complete_dates = pd.DatetimeIndex(frame.loc[frame.candle_count == 288, "date"])
    missing = expected.difference(complete_dates)
    warnings = []
    if left < pd.Timestamp(store.manifest["start"]) or right > pd.Timestamp(store.manifest["end_exclusive"]):
        warnings.append("请求超出回测覆盖范围；回测统计使用覆盖区间的交集，并保留请求原始日期。")
    if right > pd.Timestamp(store.manifest["market_end_exclusive"]):
        warnings.append("行情附件截至 2026-10-03 00:00 UTC；回测账本截至当日 12:05 UTC，末尾半日行情未打包。")
    if left != left.floor("D") or right != right.floor("D"):
        warnings.append("行情视图仅显示区间内完整 UTC 日；交易指标按原始时间边界计算。")
    if len(missing):
        warnings.append(f"行情缺失或不完整：{len(missing)} 个 UTC 日；不进行插值。")
    valid = frame.loc[frame.date.isin(complete_dates)]
    return {"asset": store.manifest["asset"], "asset_class": store.manifest["asset_class"], "source": "OKX; archived 5m OHLCV → UTC daily bars", "bars": [{**r, "date": r["date"].isoformat()} for r in valid.to_dict("records")], "coverage": {"requested_start": start, "requested_end_exclusive": end, "first": valid.date.min().isoformat() if len(valid) else None, "last": valid.date.max().isoformat() if len(valid) else None, "complete_days": len(valid), "missing_days": len(missing), "missing_examples": [x.isoformat() for x in missing[:8]], "warnings": warnings}}
